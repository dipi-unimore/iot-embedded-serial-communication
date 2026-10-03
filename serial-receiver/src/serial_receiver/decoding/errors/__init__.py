"""Reasons a COBS-valid payload is rejected. All subclass PacketError."""

from serial_receiver.decoding.errors.crc_mismatch_error import CrcMismatchError
from serial_receiver.decoding.errors.packet_error import PacketError
from serial_receiver.decoding.errors.packet_length_error import PacketLengthError
from serial_receiver.decoding.errors.unknown_packet_type_error import UnknownPacketTypeError

__all__ = ["CrcMismatchError", "PacketError", "PacketLengthError", "UnknownPacketTypeError"]
