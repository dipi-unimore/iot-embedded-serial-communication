import struct
from dataclasses import dataclass
from typing import ClassVar

import pytest

from serial_receiver.dto.imu_dto import ImuDto
from serial_receiver.dto.packet_dto import PacketDto


def test_imu_dto_roundtrip():
    dto = ImuDto(timestamp_ms=123456, ax=0.5, ay=-0.25, az=9.8100004196167)
    assert len(dto.to_bytes()) == ImuDto.LAYOUT.size == 16
    assert ImuDto.from_bytes(dto.to_bytes()) == dto


def test_imu_dto_definition_is_valid():
    ImuDto.check_definition()


def test_layout_and_fields_must_agree():
    @dataclass(frozen=True)
    class BrokenDto(PacketDto):
        LAYOUT: ClassVar[struct.Struct] = struct.Struct("<Iff")
        timestamp_ms: int
        value: float

    with pytest.raises(TypeError, match="3 values but the class has 2 fields"):
        BrokenDto.check_definition()


def test_must_be_a_dataclass():
    class NotADataclass(PacketDto):
        LAYOUT: ClassVar[struct.Struct] = struct.Struct("<I")

    with pytest.raises(TypeError, match="must be a @dataclass"):
        NotADataclass.check_definition()
