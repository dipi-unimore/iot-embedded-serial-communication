import json
import logging
from types import SimpleNamespace

import paho.mqtt.client as mqtt
import pytest

from serial_receiver.decoding.packet import Packet
from serial_receiver.dto.imu_dto import ImuDto
from serial_receiver.handlers.mqtt.mqtt_packet_handler import MqttPacketHandler

OPTIONS = {"client_id": "rx-1", "broker_host": "broker.local", "broker_port": 1884, "topic": "iot/{dto}"}
PACKET = Packet(0x01, ImuDto(94, 0.5, -0.25, 9.81), number=7, received_at_ms=1791042044608)


class FakeClient:
    """Stands in for paho's Client: records every call, publish() returns a configurable rc."""

    def __init__(self, callback_api_version, client_id):
        self.client_id = client_id
        self.calls: list[tuple] = []
        self.published: list[tuple] = []
        self.publish_rc = mqtt.MQTT_ERR_SUCCESS

    def __getattr__(self, name):  # username_pw_set, reconnect_delay_set, connect_async, loop_start...
        return lambda *args: self.calls.append((name, *args))

    def publish(self, topic, payload, qos, retain):
        self.published.append((topic, payload, qos, retain))
        return SimpleNamespace(rc=self.publish_rc)


@pytest.fixture
def make_handler(monkeypatch):
    monkeypatch.setattr(MqttPacketHandler, "_client_factory", FakeClient)
    return lambda **overrides: MqttPacketHandler(**{**OPTIONS, **overrides})


def call_names(handler):
    return [c[0] for c in handler._client.calls]


def test_connects_in_the_background_at_startup(make_handler):
    handler = make_handler()
    assert handler._client.client_id == "rx-1"
    assert ("connect_async", "broker.local", 1884, 60) in handler._client.calls
    assert call_names(handler)[-1] == "loop_start"


def test_publishes_json_envelope(make_handler):
    handler = make_handler(qos=1, retain=True)
    handler.handle(PACKET)

    [(topic, payload, qos, retain)] = handler._client.published
    assert (topic, qos, retain) == ("iot/imu", 1, True)
    envelope = json.loads(payload)
    assert (envelope["packet_number"], envelope["received_timestamp"], envelope["dto"]) == (7, 1791042044608, "ImuDto")
    assert handler.published == 1


def test_publishes_binary(make_handler):
    handler = make_handler(format="binary")
    handler.handle(PACKET)
    [(_, payload, _, _)] = handler._client.published
    assert len(payload) == 31


def test_qos0_while_disconnected_counts_as_dropped_and_warns_once(make_handler, caplog):
    handler = make_handler(qos=0)
    handler._client.publish_rc = mqtt.MQTT_ERR_NO_CONN
    with caplog.at_level(logging.WARNING):
        for _ in range(5):
            handler.handle(PACKET)  # never raises
    assert (handler.dropped, handler.published) == (5, 0)
    assert len([r for r in caplog.records if "dropped" in r.getMessage()]) == 1  # rate-limited


def test_qos1_while_disconnected_is_queued_not_dropped(make_handler):
    handler = make_handler(qos=1)
    handler._client.publish_rc = mqtt.MQTT_ERR_NO_CONN  # paho keeps QoS 1/2 messages for resend
    handler.handle(PACKET)
    assert (handler.dropped, handler.published) == (0, 1)


def test_queue_full_is_dropped(make_handler):
    handler = make_handler(qos=1)
    handler._client.publish_rc = mqtt.MQTT_ERR_QUEUE_SIZE
    handler.handle(PACKET)
    assert handler.dropped == 1


def test_credentials_from_environment(make_handler, monkeypatch):
    monkeypatch.setenv("SERIAL_RECEIVER_TEST_PW", "s3cret")
    handler = make_handler(username="user", password_env="SERIAL_RECEIVER_TEST_PW")
    assert ("username_pw_set", "user", "s3cret") in handler._client.calls


def test_close_disconnects_and_stops_the_network_thread(make_handler):
    handler = make_handler()
    handler.close()
    assert call_names(handler)[-2:] == ["disconnect", "loop_stop"]
