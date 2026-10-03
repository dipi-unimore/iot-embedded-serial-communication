import time
from collections import Counter

import serial

from serial_receiver.decoding.errors.packet_error import PacketError
from serial_receiver.decoding.errors.unknown_packet_type_error import UnknownPacketTypeError
from serial_receiver.decoding.packet_decoder import PacketDecoder
from serial_receiver.discovery.probe_result import ProbeResult
from serial_receiver.protocol import cobs
from serial_receiver.protocol.cobs_decode_error import CobsDecodeError
from serial_receiver.protocol.frame_splitter import FrameSplitter
from serial_receiver.receiver.serial_port import open_serial_port


class DeviceProber:
    """Listens to a port for a short while and reports which packets it carries.

    It runs the same front half of the pipeline as Receiver (FrameSplitter ->
    cobs.decode -> PacketDecoder.decode), but only counts the results: nothing is
    dispatched to handlers. It uses the same decoder as the Receiver, built from
    the same config, so "decoded" means the packet would be handled by the current
    configuration. CRC-valid packets of an unconfigured type are still reported:
    the sender speaks the protocol, the config just doesn't know that type yet.

    port_discovery calls probe() on several ports at once, one thread each. That's
    safe because probe() keeps all its state in local variables. The decoder is
    stateless and shared read-only.

    Some devices reset when their port is opened (see open_serial_port), so the
    start of a probe may be their boot time.
    """

    def __init__(self, decoder: PacketDecoder, baudrate: int) -> None:
        self._decoder = decoder
        self.baudrate = baudrate  # public: port_discovery reads it for messages and timed-out results

    def probe(self, port: str, duration_s: float) -> ProbeResult:
        """Opens `port`, listens for duration_s and classifies every frame.

        Never raises for port problems: a port that can't be opened or read is
        reported in ProbeResult.error, so one bad port doesn't abort discovery.
        """
        decoded: Counter[int] = Counter()
        dto_names: dict[int, str] = {}
        unconfigured: Counter[int] = Counter()
        rejected = 0
        splitter = FrameSplitter()

        try:
            with open_serial_port(port, self.baudrate) as ser:
                deadline = time.monotonic() + duration_s
                while time.monotonic() < deadline:
                    # read() returns within the port timeout even when silent, so the deadline is honored.
                    for frame in splitter.feed(ser.read(ser.in_waiting or 1)):
                        try:
                            payload = cobs.decode(frame)
                            packet = self._decoder.decode(payload)
                        except UnknownPacketTypeError:
                            # The CRC passed, so payload[0] is a genuine type byte.
                            unconfigured[payload[0]] += 1
                        except (CobsDecodeError, PacketError):
                            rejected += 1
                        else:
                            decoded[packet.packet_type] += 1
                            dto_names[packet.packet_type] = type(packet.dto).__name__
        except (serial.SerialException, OSError) as exc:
            return ProbeResult(self.baudrate, duration_s, error=str(exc))

        return ProbeResult(
            self.baudrate,
            duration_s,
            decoded=dict(decoded),
            dto_names=dto_names,
            unconfigured=dict(unconfigured),
            rejected_frames=rejected + splitter.overflows,
        )
