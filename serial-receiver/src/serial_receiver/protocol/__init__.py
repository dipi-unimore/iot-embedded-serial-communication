"""Wire level: raw byte stream -> COBS frames -> CRC-protected payloads.

Knows nothing about what a payload means - that's the decoding package's job.
"""

from serial_receiver.protocol.cobs_decode_error import CobsDecodeError
from serial_receiver.protocol.frame_splitter import FrameSplitter

__all__ = ["CobsDecodeError", "FrameSplitter"]
