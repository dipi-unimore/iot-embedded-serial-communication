import struct

import pytest

from serial_receiver.decoding.dto_registry import DtoRegistry
from serial_receiver.decoding.errors.crc_mismatch_error import CrcMismatchError
from serial_receiver.decoding.errors.packet_length_error import PacketLengthError
from serial_receiver.decoding.errors.unknown_packet_type_error import UnknownPacketTypeError
from serial_receiver.decoding.packet import Packet
from serial_receiver.decoding.packet_decoder import PacketDecoder
from serial_receiver.dto.imu_dto import ImuDto
from serial_receiver.protocol.crc import crc16_ccitt


@pytest.fixture
def decoder() -> PacketDecoder:
    registry = DtoRegistry()
    registry.register(0x01, ImuDto)
    return PacketDecoder(registry)


def with_crc(body: bytes) -> bytes:
    return body + struct.pack("<H", crc16_ccitt(body))


def test_roundtrip(decoder):
    packet = Packet(0x01, ImuDto(123456, 0.5, -0.25, 9.8100004196167))
    payload = decoder.encode(packet)
    assert len(payload) == 19  # type (1) + LAYOUT (16) + crc (2)
    assert decoder.decode(payload) == packet


def test_sender_wire_layout(decoder):
    # The bytes a sender's packed struct produces: type, u32 timestamp,
    # 3x float32, crc16 - all little-endian.
    payload = with_crc(struct.pack("<BIfff", 0x01, 1000, 1.0, 2.0, 3.0))
    assert decoder.decode(payload) == Packet(0x01, ImuDto(1000, 1.0, 2.0, 3.0))


def test_corrupted_byte_fails_crc(decoder):
    payload = bytearray(decoder.encode(Packet(0x01, ImuDto(1, 1.0, 2.0, 3.0))))
    payload[5] ^= 0x40
    with pytest.raises(CrcMismatchError):
        decoder.decode(bytes(payload))


def test_unconfigured_type(decoder):
    with pytest.raises(UnknownPacketTypeError):
        decoder.decode(with_crc(b"\x7f\x01\x02"))


def test_wrong_length_for_type(decoder):
    with pytest.raises(PacketLengthError):
        decoder.decode(with_crc(b"\x01\x01\x02\x03"))


def test_too_short(decoder):
    with pytest.raises(PacketLengthError):
        decoder.decode(b"\x01\x02")
