"""COBS (Consistent Overhead Byte Stuffing), compatible with the PacketSerial library.

COBS rewrites a byte string so that it contains no 0x00, so a single 0x00 can
mark the end of each frame on the wire. The data is cut at every zero. Each
chunk is prefixed by a code byte = chunk length + 1, and the zero itself is
dropped. A code of 0xFF means "254 data bytes and no zero after them" (needed for
long zero-free runs).

    data      11 22 00 33
    encoded   03 11 22 02 33       (then 00 on the wire as the delimiter)

Frames passed in/out here never include the trailing delimiter: splitting the
stream on 0x00 is protocol.FrameSplitter's job.
"""

from serial_receiver.protocol.cobs_decode_error import CobsDecodeError


def encode(data: bytes) -> bytes:
    """Inverse of decode(). The receiver itself only decodes: this is used by the
    tests, and by any future PC -> device sender."""
    out = bytearray()
    block = bytearray()  # current chunk: non-zero bytes since the last zero
    for byte in data:
        if byte == 0:
            out.append(len(block) + 1)
            out += block
            block.clear()
        else:
            block.append(byte)
            if len(block) == 254:
                # A full block has no implicit zero after it (code 0xFF).
                out.append(0xFF)
                out += block
                block.clear()
    out.append(len(block) + 1)  # the last chunk, possibly empty
    out += block
    return bytes(out)


def decode(frame: bytes) -> bytes:
    """Decodes one frame, raising CobsDecodeError if it isn't valid COBS.

    Invalid COBS means the frame was corrupted on the wire, or it isn't protocol
    traffic at all (e.g. noise before sync). The checks are what make this safe
    to run on garbage: a code byte pointing past the end of the frame, or a 0x00
    inside it, is rejected instead of silently producing a wrong payload.
    """
    out = bytearray()
    i = 0
    n = len(frame)
    while i < n:
        code = frame[i]
        if code == 0:
            raise CobsDecodeError(f"unexpected 0x00 at offset {i}")
        end = i + code
        if end > n:
            raise CobsDecodeError(f"block at offset {i} claims {code - 1} bytes, only {n - i - 1} left")
        out += frame[i + 1 : end]
        i = end
        # Every chunk except the last was followed by a zero in the original data,
        # unless it was a full 254-byte chunk (code 0xFF).
        if code != 0xFF and i < n:
            out.append(0)
    return bytes(out)
