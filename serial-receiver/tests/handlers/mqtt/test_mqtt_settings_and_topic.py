import pytest

from serial_receiver.decoding.packet import Packet
from serial_receiver.dto.imu_dto import ImuDto
from serial_receiver.handlers.mqtt.mqtt_settings import MqttSettings
from serial_receiver.handlers.mqtt.topic_template import TopicTemplate

REQUIRED = {"client_id": "rx-1", "broker_host": "localhost", "topic": "iot/{dto}"}


def test_defaults():
    s = MqttSettings(**REQUIRED)
    assert (s.broker_port, s.format, s.qos, s.retain, s.password) == (1883, "json", 0, False, None)


@pytest.mark.parametrize(
    ("override", "message"),
    [
        ({"client_id": ""}, "client_id"),
        ({"broker_port": 0}, "broker_port"),
        ({"format": "xml"}, "format"),
        ({"qos": 3}, "qos"),
        ({"keepalive_s": 0}, "keepalive_s"),
        ({"max_queued_messages": -1}, "max_queued_messages"),
        ({"password_env": "X"}, "needs a username"),
        ({"username": "u", "password_env": "SERIAL_RECEIVER_TEST_UNSET"}, "is not set"),
    ],
)
def test_invalid(override, message):
    with pytest.raises(ValueError, match=message):
        MqttSettings(**{**REQUIRED, **override})


def test_unknown_option_is_a_type_error():
    with pytest.raises(TypeError):
        MqttSettings(**REQUIRED, colour="red")


def test_password_comes_from_the_environment(monkeypatch):
    monkeypatch.setenv("SERIAL_RECEIVER_TEST_PW", "s3cret")
    assert MqttSettings(**REQUIRED, username="u", password_env="SERIAL_RECEIVER_TEST_PW").password == "s3cret"


PACKET = Packet(0x01, ImuDto(1, 0.0, 0.0, 9.81))


@pytest.mark.parametrize(
    ("template", "topic"),
    [
        ("iot/serial/{dto}", "iot/serial/imu"),
        ("iot/{client_id}/{packet_type}", "iot/rx-1/01"),
        ("fixed/topic", "fixed/topic"),
    ],
)
def test_topic_render(template, topic):
    assert TopicTemplate(template, "rx-1").render(PACKET) == topic


@pytest.mark.parametrize(
    ("template", "message"),
    [("iot/{device}", "unknown placeholder"), ("iot/+/x", "wildcard"), ("iot/#", "wildcard"), ("iot/{dto", "not a valid")],
)
def test_topic_rejected_at_startup(template, message):
    with pytest.raises(ValueError, match=message):
        TopicTemplate(template, "rx-1")
