import pytest

from serial_receiver.decoding.dto_registry import DtoRegistry
from serial_receiver.decoding.packet import Packet
from serial_receiver.decoding.packet_decoder import PacketDecoder
from serial_receiver.dto.imu_dto import ImuDto
from serial_receiver.serialization.binary_payload_encoder import HEADER, BinaryPayloadEncoder
from serial_receiver.serialization.json_payload_encoder import JsonPayloadEncoder
from serial_receiver.serialization.payload_encoder_factory import create_payload_encoder

IMU = Packet(0x01, ImuDto(1000, 0.5, -0.25, 9.8100004196167), number=42, received_at_ms=1791042044608)


def test_layout_header_then_serial_packet():
    payload = BinaryPayloadEncoder().encode(IMU)

    assert len(payload) == 12 + 19
    assert HEADER.unpack(payload[:12]) == (42, 1791042044608)
    # The rest is exactly the serial packet (type | fields | crc16), as on the wire minus COBS.
    assert payload[12:] == bytes.fromhex("01 E8 03 00 00 00 00 00 3F 00 00 80 BE C3 F5 1C 41 22 80")


def test_consumer_can_decode_it_like_the_receiver():
    registry = DtoRegistry()
    registry.register(0x01, ImuDto)
    payload = BinaryPayloadEncoder().encode(IMU)
    assert PacketDecoder(registry).decode(payload[12:]) == IMU


def test_packet_number_wraps_at_u32():
    payload = BinaryPayloadEncoder().encode(Packet(0x01, IMU.dto, number=2**32 + 5, received_at_ms=0))
    assert HEADER.unpack(payload[:12]) == (5, 0)


def test_factory():
    assert isinstance(create_payload_encoder("json"), JsonPayloadEncoder)
    assert isinstance(create_payload_encoder("binary"), BinaryPayloadEncoder)
    with pytest.raises(ValueError, match="unknown payload format"):
        create_payload_encoder("xml")
