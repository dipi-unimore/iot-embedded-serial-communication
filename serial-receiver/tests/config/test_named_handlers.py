import logging
from pathlib import Path

import pytest

from serial_receiver.config.config_error import ConfigError
from serial_receiver.config.config_loader import load_config
from serial_receiver.config.receiver_factory import build_receiver
from serial_receiver.decoding.packet import Packet
from serial_receiver.handlers.packet_handler import PacketHandler

IMU_DTO = "serial_receiver.dto.imu_dto:ImuDto"
LOGGING_HANDLER = "serial_receiver.handlers.logging_packet_handler:LoggingPacketHandler"
COUNTING_HANDLER = f"{__name__}:CountingHandler"


class CountingHandler(PacketHandler):
    instances = 0

    def __init__(self, label: str = "") -> None:
        CountingHandler.instances += 1
        self.label = label
        self.closed = 0

    def handle(self, packet: Packet) -> None:
        pass

    def close(self) -> None:
        self.closed += 1


@pytest.fixture(autouse=True)
def reset_counter():
    CountingHandler.instances = 0


def write(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "receiver.toml"
    path.write_text(text)
    return path


def test_named_handler_is_one_instance_shared_by_packet_types(tmp_path):
    config = load_config(write(tmp_path, f"""
[handlers.shared]
class = "{COUNTING_HANDLER}"
[handlers.shared.options]
label = "mqtt-like"

[[packets]]
type = 0x01
dto = "{IMU_DTO}"
handlers = ["shared", "{LOGGING_HANDLER}"]

[[packets]]
type = 0x02
dto = "{IMU_DTO}"
handlers = ["shared"]
"""))
    first, second = config.packets
    assert first.handlers[0] is second.handlers[0]
    assert first.handlers[0].label == "mqtt-like"
    assert CountingHandler.instances == 1

    receiver = build_receiver(config, "/dev/null")
    receiver.close()
    assert first.handlers[0].closed == 1  # closed once, although bound to two types


def test_unused_named_handler_is_not_created(tmp_path, caplog):
    with caplog.at_level(logging.WARNING):
        load_config(write(tmp_path, f"""
[handlers.unused]
class = "{COUNTING_HANDLER}"

[[packets]]
type = 0x01
dto = "{IMU_DTO}"
"""))
    assert CountingHandler.instances == 0
    assert "[handlers.unused] is defined but no [[packets]] block uses it" in caplog.text


def test_class_paths_still_create_one_instance_per_block(tmp_path):
    config = load_config(write(tmp_path, f"""
[[packets]]
type = 0x01
dto = "{IMU_DTO}"
handlers = ["{COUNTING_HANDLER}"]

[[packets]]
type = 0x02
dto = "{IMU_DTO}"
handlers = ["{COUNTING_HANDLER}"]
"""))
    assert config.packets[0].handlers[0] is not config.packets[1].handlers[0]


@pytest.mark.parametrize(
    ("body", "message"),
    [
        (f'[[packets]]\ntype = 1\ndto = "{IMU_DTO}"\nhandlers = ["nope"]', "unknown handler name 'nope'"),
        (f'[handlers."a:b"]\nclass = "{COUNTING_HANDLER}"\n[[packets]]\ntype = 1\ndto = "{IMU_DTO}"', "can't contain ':'"),
        (f'[handlers.x]\noptions = {{}}\n[[packets]]\ntype = 1\ndto = "{IMU_DTO}"', "needs a 'class' key"),
        (
            f'[handlers.x]\nclass = "{COUNTING_HANDLER}"\n[handlers.x.options]\ncolour = 1\n'
            f'[[packets]]\ntype = 1\ndto = "{IMU_DTO}"\nhandlers = ["x"]',
            r"\[handlers.x\]: can't create",
        ),
    ],
)
def test_invalid_named_handlers(tmp_path, body, message):
    with pytest.raises(ConfigError, match=message):
        load_config(write(tmp_path, body))
