import logging
import time

import serial

from serial_receiver.decoding.errors.crc_mismatch_error import CrcMismatchError
from serial_receiver.decoding.errors.packet_error import PacketError
from serial_receiver.decoding.errors.unknown_packet_type_error import UnknownPacketTypeError
from serial_receiver.decoding.packet_decoder import PacketDecoder
from serial_receiver.handlers.packet_dispatcher import PacketDispatcher
from serial_receiver.protocol import cobs
from serial_receiver.protocol.cobs_decode_error import CobsDecodeError
from serial_receiver.protocol.frame_splitter import FrameSplitter
from serial_receiver.receiver.receiver_stats import ReceiverStats
from serial_receiver.receiver.serial_port import open_serial_port

log = logging.getLogger(__name__)

RECONNECT_DELAY_S = 2.0


class Receiver:
    """Reads the serial port, decodes every frame and hands each packet to the dispatcher.

    What a packet is decoded into, and what happens to it, is entirely up to the
    two injected collaborators. The Receiver itself knows no packet type:

        decoder     PacketDecoder, built on a DtoRegistry (packet type -> DTO class)
        dispatcher  PacketDispatcher (packet type -> PacketHandler callbacks)

    Usually wired from receiver.toml by config.receiver_factory.build_receiver().

    Call chain, all on the calling thread (there are no threads of its own):

        run_forever()                    open the port, reopen it after errors
          _read_loop(ser)                read chunks, log stats periodically
            FrameSplitter.feed(chunk)    -> complete frames
            _handle_frame(frame)
              cobs.decode(frame)         -> payload
              decoder.decode(payload)    -> Packet
              dispatcher.dispatch(pkt)   -> PacketHandler.handle(pkt) per bound handler
            or, if any step raised:
              _on_discard(frame, exc)    -> ReceiverStats / log

    Handlers therefore run synchronously inside the read loop, and a slow handler
    slows down reading (bytes queue up in the OS buffer meanwhile).
    """

    def __init__(
        self,
        port: str,
        baudrate: int,
        decoder: PacketDecoder,
        dispatcher: PacketDispatcher,
        stats_interval_s: float = 5.0,
    ) -> None:
        self._port = port
        self._baudrate = baudrate
        self._decoder = decoder
        self._dispatcher = dispatcher
        self._stats_interval_s = stats_interval_s  # <= 0 disables the periodic "Stats:" line
        self.stats = ReceiverStats()  # cumulative over the whole run, across reconnects
        self._synced = False  # becomes True on the first valid packet of each connection

    def run_forever(self) -> None:
        """Reads until interrupted (KeyboardInterrupt propagates to the caller).

        If the port fails (device unplugged, reset while being flashed, port taken
        by another process), it logs the error and retries every
        RECONNECT_DELAY_S. Each reconnection starts unsynced again.
        """
        while True:
            try:
                with open_serial_port(self._port, self._baudrate) as ser:
                    log.info("Listening on %s @ %d baud", self._port, self._baudrate)
                    self._read_loop(ser)
            except serial.SerialException as exc:
                log.error("Serial error on %s: %s - retrying in %.0fs", self._port, exc, RECONNECT_DELAY_S)
                time.sleep(RECONNECT_DELAY_S)

    def _read_loop(self, ser: serial.Serial) -> None:
        """Reads and processes bytes for one open connection, until a SerialException."""
        splitter = FrameSplitter()  # fresh per connection: starts unsynced, overflow count from 0
        self._synced = False
        last_stats_at = time.monotonic()
        packets_at_last_stats = self.stats.packets

        while True:
            # Read whatever is buffered, or block for 1 byte up to the port's
            # read timeout (0.1 s), so the stats timer below keeps ticking even
            # when the line is silent.
            chunk = ser.read(ser.in_waiting or 1)
            for frame in splitter.feed(chunk):
                self._handle_frame(frame)

            now = time.monotonic()
            if self._stats_interval_s > 0 and now - last_stats_at >= self._stats_interval_s:
                rate = (self.stats.packets - packets_at_last_stats) / (now - last_stats_at)
                self._log_stats(rate, splitter.overflows)
                last_stats_at = now
                packets_at_last_stats = self.stats.packets

    def _handle_frame(self, frame: bytes) -> None:
        """Decodes one frame and dispatches the packet, or records why it was discarded.

        cobs.decode raises CobsDecodeError, and decoder.decode raises PacketError
        subclasses (CRC, unknown type, length). Exceptions raised by handlers
        never reach here: PacketDispatcher catches them.
        """
        try:
            packet = self._decoder.decode(cobs.decode(frame))
        except (CobsDecodeError, PacketError) as exc:
            self._on_discard(frame, exc)
        else:
            if not self._synced:
                self._synced = True
                log.info("In sync: first valid packet received")
            self.stats.packets += 1
            self._dispatcher.dispatch(packet)

    def _on_discard(self, frame: bytes, exc: Exception) -> None:
        """Counts and logs a frame that didn't decode, by cause."""
        # Until the first valid packet, garbage is expected rather than a link
        # error: we may have joined mid-frame, and devices that reset when the
        # port opens may print a boot log at another baud rate, which reads as
        # noise. Keep it out of the stats, and out of sight unless --log-level DEBUG.
        if not self._synced:
            self.stats.discarded_while_syncing += 1
            log.debug("Discarded while syncing (%s): %s", exc, frame.hex(" "))
            return

        match exc:
            case CobsDecodeError():
                self.stats.cobs_errors += 1
            case CrcMismatchError():
                self.stats.crc_errors += 1
            case UnknownPacketTypeError():
                self.stats.unknown_type += 1
            case _:
                self.stats.other_errors += 1  # PacketLengthError
        log.warning("Discarded frame (%s): %s", exc, frame.hex(" "))

    def _log_stats(self, rate_hz: float, overflows: int) -> None:
        """One summary line. rate_hz covers the last interval; the counters are
        cumulative, except `overflows`, which is per connection."""
        s = self.stats
        total = s.packets + s.errors
        error_pct = 100.0 * s.errors / total if total else 0.0
        log.info(
            "Stats: %.1f pkt/s | ok=%d errors=%d (%.2f%%: cobs=%d crc=%d unknown_type=%d other=%d) overflows=%d",
            rate_hz, s.packets, s.errors, error_pct,
            s.cobs_errors, s.crc_errors, s.unknown_type, s.other_errors, overflows,
        )
