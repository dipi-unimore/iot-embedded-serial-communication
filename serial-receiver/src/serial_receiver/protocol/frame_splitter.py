from collections.abc import Iterator

# Far bigger than any packet: a longer run without a delimiter is line noise or
# non-protocol output (e.g. a device's boot log), not a real frame.
DEFAULT_MAX_FRAME_LEN = 256


class FrameSplitter:
    """Splits the raw serial byte stream into COBS frames on the 0x00 delimiter.

    Serial reads return arbitrary chunks: half a frame, three frames and a bit,
    and so on. The splitter keeps the partial frame between calls, so the caller
    can feed whatever it read and get back only complete frames, without the
    delimiter:

        splitter = FrameSplitter()
        for frame in splitter.feed(ser.read(n)):   # zero, one or many frames per call
            ...

    It's a small state machine with three states:

        UNSYNCED     initial. The port may have been opened mid-frame, so the bytes
                     before the first 0x00 belong to a frame whose start we never
                     saw. They're dropped silently, not reported as a corrupt frame.
        COLLECTING   bytes accumulate in the buffer. A 0x00 yields the buffer as a
                     frame (empty frames, i.e. consecutive 0x00s, are skipped).
        OVERFLOWING  the buffer grew past max_frame_len without a delimiter: noise,
                     or the wrong baud rate. Bytes are dropped until the next 0x00,
                     which returns to COLLECTING. Each such run counts in `overflows`.

    It only finds frame boundaries. Whether a frame is valid COBS, or a valid
    packet, is checked further down by protocol.cobs and decoding.PacketDecoder.
    """

    def __init__(self, max_frame_len: int = DEFAULT_MAX_FRAME_LEN) -> None:
        self._max_frame_len = max_frame_len
        self._buffer = bytearray()  # the frame being collected, across feed() calls
        self._synced = False  # False = UNSYNCED
        self._overflowing = False  # True = OVERFLOWING
        self.overflows = 0  # frames dropped for exceeding max_frame_len, read by Receiver/DeviceProber stats

    def feed(self, data: bytes) -> Iterator[bytes]:
        """Consumes `data` and yields every frame it completes.

        It's a generator, so the input is processed while the caller iterates.
        Iterate it fully (a for loop does), or the rest of `data` is never consumed.
        """
        for byte in data:
            if byte == 0:
                # Delimiter: the end of a frame, and in any case a known-good
                # boundary to (re)start from.
                if self._synced and not self._overflowing and self._buffer:
                    yield bytes(self._buffer)
                self._buffer.clear()
                self._synced = True
                self._overflowing = False
            elif self._synced and not self._overflowing:
                self._buffer.append(byte)
                if len(self._buffer) > self._max_frame_len:
                    self.overflows += 1
                    self._overflowing = True
                    self._buffer.clear()
            # else: UNSYNCED or OVERFLOWING, so the byte is dropped until the next 0x00.
