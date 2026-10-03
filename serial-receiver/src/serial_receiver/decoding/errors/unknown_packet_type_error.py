from serial_receiver.decoding.errors.packet_error import PacketError


class UnknownPacketTypeError(PacketError):
    """Valid CRC, but no DTO is configured for the packet's type byte."""
