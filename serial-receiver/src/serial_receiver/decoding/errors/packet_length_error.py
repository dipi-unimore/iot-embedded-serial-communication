from serial_receiver.decoding.errors.packet_error import PacketError


class PacketLengthError(PacketError):
    """The payload is too short, or its size doesn't match the DTO bound to its type."""
