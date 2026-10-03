import struct

from serial_receiver.decoding.dto_registry import DtoRegistry
from serial_receiver.decoding.errors.crc_mismatch_error import CrcMismatchError
from serial_receiver.decoding.errors.packet_length_error import PacketLengthError
from serial_receiver.decoding.errors.unknown_packet_type_error import UnknownPacketTypeError
from serial_receiver.decoding.packet import Packet
from serial_receiver.protocol.crc import crc16_ccitt

_CRC = struct.Struct("<H")  # the trailing CRC: uint16, little-endian


class PacketDecoder:
    """Turns a COBS-decoded payload into a Packet, using the DTO the registry
    binds to its type byte (and back, for building packets to send).

    Payload layout:  [type: u8] [DTO fields: dto.LAYOUT.size bytes] [crc16: u16 LE]

    It's stateless: one call per payload, no memory of previous packets. The
    Receiver and the DeviceProber call decode() and handle the exceptions it
    raises (all subclasses of PacketError).
    """

    def __init__(self, registry: DtoRegistry) -> None:
        self._registry = registry

    def decode(self, payload: bytes) -> Packet:
        """Validates and deserializes one payload.

        The checks run in this order, and each raises a different PacketError:

        1. Minimum size (type + CRC) -> PacketLengthError.
        2. CRC over everything but the last 2 bytes -> CrcMismatchError. This comes
           before reading the type byte: if the data is corrupted, the type byte
           can't be trusted either.
        3. Type byte bound to a DTO? -> UnknownPacketTypeError. The packet is
           genuine (its CRC is valid), so the sender knows a type the config doesn't.
        4. Field bytes == DTO.LAYOUT.size? -> PacketLengthError. The sender and the
           DTO disagree on the layout of this type.

        Only then is the DTO built.
        """
        if len(payload) < 1 + _CRC.size:
            raise PacketLengthError(f"payload too short ({len(payload)} bytes)")

        body, (crc_received,) = payload[: -_CRC.size], _CRC.unpack(payload[-_CRC.size :])
        crc_computed = crc16_ccitt(body)
        if crc_computed != crc_received:
            raise CrcMismatchError(f"CRC mismatch: received 0x{crc_received:04X}, computed 0x{crc_computed:04X}")

        packet_type = body[0]
        dto_cls = self._registry.get(packet_type)
        if dto_cls is None:
            raise UnknownPacketTypeError(f"no DTO configured for packet type 0x{packet_type:02X}")

        fields = body[1:]
        if len(fields) != dto_cls.LAYOUT.size:
            raise PacketLengthError(
                f"packet type 0x{packet_type:02X} ({dto_cls.__name__}) has {len(fields)} field bytes, "
                f"expected {dto_cls.LAYOUT.size}"
            )
        return Packet(packet_type, dto_cls.from_bytes(fields))

    @staticmethod
    def encode(packet: Packet) -> bytes:
        """Builds the payload (before COBS) with its CRC: the inverse of decode().

        Static because it needs no registry: the DTO carries its own layout. Used by
        the tests, by serialization.BinaryPayloadEncoder, and the basis for a future
        PC -> device sender: cobs.encode(PacketDecoder.encode(packet)) + b"\\x00" is
        a complete wire frame.
        """
        body = bytes([packet.packet_type]) + packet.dto.to_bytes()
        return body + _CRC.pack(crc16_ccitt(body))
