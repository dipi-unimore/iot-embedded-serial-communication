from serial_receiver.decoding.errors.packet_error import PacketError


class CrcMismatchError(PacketError):
    """The payload's CRC doesn't match its content: corrupted on the wire."""
