import logging
import time
from typing import Any

import paho.mqtt.client as mqtt

from serial_receiver.decoding.packet import Packet
from serial_receiver.handlers.mqtt.mqtt_settings import MqttSettings
from serial_receiver.handlers.mqtt.topic_template import TopicTemplate
from serial_receiver.handlers.packet_handler import PacketHandler
from serial_receiver.serialization.payload_encoder_factory import create_payload_encoder

log = logging.getLogger(__name__)

RECONNECT_MIN_DELAY_S = 1
RECONNECT_MAX_DELAY_S = 30
DROP_WARNING_INTERVAL_S = 10.0  # at most one "messages dropped" warning per interval


class MqttPacketHandler(PacketHandler):
    """Publishes every packet it receives to an MQTT broker.

    Configured in receiver.toml, typically as a named handler so that every packet
    type shares one connection:

        [handlers.mqtt]
        class = "serial_receiver.handlers.mqtt.mqtt_packet_handler:MqttPacketHandler"
        [handlers.mqtt.options]
        client_id = "serial-receiver-1"
        broker_host = "192.168.1.10"
        topic = "iot/serial/{dto}"
        format = "json"

    The options are the fields of MqttSettings. Per packet:

        topic   = TopicTemplate.render(packet)       e.g. iot/serial/imu
        payload = PayloadEncoder.encode(packet)      JSON envelope or binary header + packet
        client.publish(topic, payload, qos, retain)

    Threads: paho's network loop runs in its own background thread (loop_start).
    handle() runs on the Receiver's read thread and only calls publish(), which is
    thread-safe and doesn't wait for the network, so a slow or absent broker never
    stalls serial reading.

    Connection: connect_async() at construction, so startup doesn't block or fail
    when the broker is down. paho reconnects automatically, waiting
    RECONNECT_MIN_DELAY_S up to RECONNECT_MAX_DELAY_S between attempts.

    Delivery while disconnected (paho 2.x behavior):
        qos 0    the message is dropped: counted, and logged as a periodic WARNING.
        qos 1/2  the message is queued in memory and sent after reconnecting, up to
                 max_queued_messages; beyond that, new messages are dropped (counted, logged).
    """

    # Replaced by a fake in the tests.
    _client_factory = mqtt.Client

    def __init__(self, **options: Any) -> None:
        self._settings = MqttSettings(**options)
        self._encoder = create_payload_encoder(self._settings.format, self._settings.float_digits)
        self._topic = TopicTemplate(self._settings.topic, self._settings.client_id)
        self.published = 0  # publish() calls accepted by paho (sent or queued)
        self.dropped = 0  # messages paho refused: see "Delivery while disconnected"
        self._dropped_since_warning = 0
        self._last_drop_warning = 0.0
        self._unreachable_reported = False  # log "broker unreachable" once per outage, not per retry

        s = self._settings
        self._client = self._client_factory(callback_api_version=mqtt.CallbackAPIVersion.VERSION2, client_id=s.client_id)
        if s.username is not None:
            self._client.username_pw_set(s.username, s.password)
        self._client.reconnect_delay_set(RECONNECT_MIN_DELAY_S, RECONNECT_MAX_DELAY_S)
        self._client.max_queued_messages_set(s.max_queued_messages)
        self._client.on_connect = self._on_connect
        self._client.on_disconnect = self._on_disconnect
        self._client.on_connect_fail = self._on_connect_fail
        self._client.connect_async(s.broker_host, s.broker_port, s.keepalive_s)
        self._client.loop_start()
        log.info(
            "MQTT %s -> %s:%d, topic %r, format %s, qos %d",
            s.client_id, s.broker_host, s.broker_port, s.topic, s.format, s.qos,
        )

    def handle(self, packet: Packet) -> None:
        info = self._client.publish(
            self._topic.render(packet), self._encoder.encode(packet), self._settings.qos, self._settings.retain
        )
        if self._was_dropped(info.rc):
            self._on_dropped(info.rc)
        else:
            self.published += 1

    def close(self) -> None:
        """Disconnects cleanly and stops paho's network thread."""
        self._client.disconnect()
        self._client.loop_stop()
        log.info("MQTT %s closed: %d published, %d dropped", self._settings.client_id, self.published, self.dropped)

    def _was_dropped(self, rc: int) -> bool:
        # NO_CONN means "not sent now". paho keeps QoS 1/2 messages to resend
        # after reconnecting, but discards QoS 0 ones. QUEUE_SIZE always means discarded.
        if rc == mqtt.MQTT_ERR_SUCCESS:
            return False
        if rc == mqtt.MQTT_ERR_NO_CONN:
            return self._settings.qos == 0
        return True

    def _on_dropped(self, rc: int) -> None:
        self.dropped += 1
        self._dropped_since_warning += 1
        now = time.monotonic()
        if now - self._last_drop_warning >= DROP_WARNING_INTERVAL_S:
            log.warning(
                "MQTT %s: %d message(s) dropped (%s)",
                self._settings.client_id, self._dropped_since_warning, mqtt.error_string(rc),
            )
            self._dropped_since_warning = 0
            self._last_drop_warning = now

    # paho callbacks: they run on paho's network thread.

    def _on_connect(self, client, userdata, flags, reason_code, properties) -> None:
        s = self._settings
        if reason_code.is_failure:
            log.error("MQTT %s: connection to %s:%d refused: %s", s.client_id, s.broker_host, s.broker_port, reason_code)
        else:
            self._unreachable_reported = False
            log.info("MQTT %s: connected to %s:%d", s.client_id, s.broker_host, s.broker_port)

    def _on_connect_fail(self, client, userdata) -> None:
        # The TCP connection itself failed (broker down, wrong host). paho retries on its own.
        if not self._unreachable_reported:
            self._unreachable_reported = True
            s = self._settings
            log.warning("MQTT %s: broker %s:%d unreachable, retrying in the background", s.client_id, s.broker_host, s.broker_port)

    def _on_disconnect(self, client, userdata, flags, reason_code, properties) -> None:
        if reason_code != 0:
            log.warning("MQTT %s: disconnected (%s), reconnecting...", self._settings.client_id, reason_code)
