from pathlib import Path

import pytest

from serial_receiver.config.config_error import ConfigError
from serial_receiver.config.config_loader import load_config
from serial_receiver.config.receiver_factory import build_receiver
from serial_receiver.dto.imu_dto import ImuDto
from serial_receiver.handlers.logging_packet_handler import LoggingPacketHandler

PROJECT_CONFIG = Path(__file__).parents[2] / "receiver.toml"

IMU_DTO = "serial_receiver.dto.imu_dto:ImuDto"
LOGGING_HANDLER = "serial_receiver.handlers.logging_packet_handler:LoggingPacketHandler"


def write(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "receiver.toml"
    path.write_text(text)
    return path


def test_project_config_loads_and_builds_a_receiver():
    config = load_config(PROJECT_CONFIG)
    assert config.baudrate == 921600
    [binding] = config.packets
    assert binding.packet_type == 0x01
    assert binding.dto_cls is ImuDto
    assert [type(h) for h in binding.handlers] == [LoggingPacketHandler]
    build_receiver(config, "/dev/null")


def test_defaults_and_both_handler_forms(tmp_path):
    config = load_config(write(tmp_path, f"""
[[packets]]
type = 0x02
dto = "{IMU_DTO}"
handlers = ["{LOGGING_HANDLER}", {{ class = "{LOGGING_HANDLER}", options = {{ level = "DEBUG" }} }}]
"""))
    assert config.port is None
    assert config.baudrate == 921600
    assert config.stats_interval_s == 5.0
    assert len(config.packets[0].handlers) == 2


@pytest.mark.parametrize(
    ("body", "message"),
    [
        ("", "no \\[\\[packets\\]\\]"),
        (f'[[packets]]\ndto = "{IMU_DTO}"', "missing 'type'"),
        (f'[[packets]]\ntype = 256\ndto = "{IMU_DTO}"', "0x00-0xFF"),
        ('[[packets]]\ntype = 1\ndto = "serial_receiver.dto.imu_dto"', "package.module:ClassName"),
        ('[[packets]]\ntype = 1\ndto = "no_such_module:X"', "can't import"),
        ('[[packets]]\ntype = 1\ndto = "serial_receiver.dto.imu_dto:Nope"', "has no 'Nope'"),
        ('[[packets]]\ntype = 1\ndto = "pathlib:Path"', "not a PacketDto"),
        (f'[[packets]]\ntype = 1\ndto = "{IMU_DTO}"\nhandlers = ["pathlib:Path"]', "not a PacketHandler"),
        (
            f'[[packets]]\ntype = 1\ndto = "{IMU_DTO}"\n'
            f'handlers = [{{ class = "{LOGGING_HANDLER}", options = {{ colour = "red" }} }}]',
            "can't create",
        ),
        (f'[[packets]]\ntype = 1\ndto = "{IMU_DTO}"\n[[packets]]\ntype = 1\ndto = "{IMU_DTO}"', "more than once"),
        ("not = valid = toml", "invalid TOML"),
    ],
)
def test_invalid_configs(tmp_path, body, message):
    with pytest.raises(ConfigError, match=message):
        load_config(write(tmp_path, body))


def test_missing_file(tmp_path):
    with pytest.raises(ConfigError, match="not found"):
        load_config(tmp_path / "nope.toml")
