import json
import struct
from dataclasses import dataclass
from typing import ClassVar

import pytest

from serial_receiver.decoding.packet import Packet
from serial_receiver.dto.imu_dto import ImuDto
from serial_receiver.dto.packet_dto import PacketDto
from serial_receiver.serialization.json_payload_encoder import JsonPayloadEncoder


def float32(x: float) -> float:
    """x as it comes back from a float32 field (e.g. 0.146 -> 0.14600000083446503)."""
    return struct.unpack("<f", struct.pack("<f", x))[0]


IMU = Packet(
    0x01, ImuDto(94, float32(0.146), float32(0.478), float32(9.81)), number=42, received_at_ms=1791042044608
)


def test_envelope():
    assert json.loads(JsonPayloadEncoder().encode(IMU)) == {
        "packet_number": 42,
        "received_timestamp": 1791042044608,
        "packet_type": 1,
        "dto": "ImuDto",
        "data": {"timestamp_ms": 94, "ax": 0.146, "ay": 0.478, "az": 9.81},
    }


def test_compact_utf8():
    payload = JsonPayloadEncoder().encode(IMU)
    assert b" " not in payload
    payload.decode("utf-8")


def test_float_digits_none_keeps_full_float32_value():
    data = json.loads(JsonPayloadEncoder(float_digits=None).encode(IMU))["data"]
    assert data["ax"] == float32(0.146) != 0.146


def test_dto_can_customize_its_data():
    @dataclass(frozen=True)
    class TempDto(PacketDto):
        LAYOUT: ClassVar[struct.Struct] = struct.Struct("<f")
        celsius: float

        def to_dict(self) -> dict[str, object]:
            return {"celsius": self.celsius, "fahrenheit": self.celsius * 9 / 5 + 32, "history": [self.celsius]}

    payload = JsonPayloadEncoder(float_digits=3).encode(Packet(0x05, TempDto(float32(21.5)), 1, 0))
    assert json.loads(payload)["data"] == {"celsius": 21.5, "fahrenheit": 70.7, "history": [21.5]}


@pytest.mark.parametrize("digits", [0, 18])
def test_rejects_bad_float_digits(digits):
    with pytest.raises(ValueError):
        JsonPayloadEncoder(float_digits=digits)
