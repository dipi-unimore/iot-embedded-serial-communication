import pytest

from serial_receiver.decoding.dto_registry import DtoRegistry
from serial_receiver.dto.imu_dto import ImuDto


def test_register_and_get():
    registry = DtoRegistry()
    registry.register(0x01, ImuDto)
    registry.register(0x02, ImuDto)  # the same DTO can serve several packet types
    assert registry.get(0x01) is ImuDto
    assert registry.get(0x02) is ImuDto
    assert registry.get(0x03) is None
    assert len(registry) == 2


def test_rejects_duplicate_type():
    registry = DtoRegistry()
    registry.register(0x01, ImuDto)
    with pytest.raises(ValueError, match="already bound"):
        registry.register(0x01, ImuDto)


@pytest.mark.parametrize("packet_type", [-1, 0x100])
def test_rejects_type_outside_one_byte(packet_type):
    with pytest.raises(ValueError):
        DtoRegistry().register(packet_type, ImuDto)


def test_rejects_non_dto():
    with pytest.raises(TypeError):
        DtoRegistry().register(0x01, dict)
