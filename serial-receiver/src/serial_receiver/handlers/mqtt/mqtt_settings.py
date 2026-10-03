import os
from dataclasses import dataclass

from serial_receiver.serialization.payload_encoder_factory import FORMATS


@dataclass(frozen=True)
class MqttSettings:
    """MqttPacketHandler's options, validated: one field per key of its `options`
    table in receiver.toml.

    Every check runs in __post_init__, so a bad value raises ValueError while the
    config is loaded (the loader turns it into a ConfigError), before any
    connection is attempted. An unknown key raises TypeError from the dataclass
    constructor, which the loader reports the same way.
    """

    client_id: str  # MQTT client identifier: must be unique per broker connection
    broker_host: str
    topic: str  # template, see TopicTemplate
    broker_port: int = 1883
    format: str = "json"  # "json" | "binary", see the serialization package
    qos: int = 0  # 0 at most once, 1 at least once, 2 exactly once
    retain: bool = False
    keepalive_s: int = 60
    username: str | None = None
    password_env: str | None = None  # name of the environment variable holding the password
    max_queued_messages: int = 1000  # QoS 1/2 messages kept while disconnected; 0 = unlimited
    float_digits: int | None = 7  # JSON only, see JsonPayloadEncoder

    def __post_init__(self) -> None:
        for name in ("client_id", "broker_host", "topic"):
            if not isinstance(getattr(self, name), str) or not getattr(self, name).strip():
                raise ValueError(f"'{name}' must be a non-empty string")
        if not 1 <= self.broker_port <= 65535:
            raise ValueError(f"broker_port must be 1-65535, got {self.broker_port}")
        if self.format not in FORMATS:
            raise ValueError(f"format must be one of {', '.join(FORMATS)}, got {self.format!r}")
        if self.qos not in (0, 1, 2):
            raise ValueError(f"qos must be 0, 1 or 2, got {self.qos}")
        if self.keepalive_s <= 0:
            raise ValueError(f"keepalive_s must be positive, got {self.keepalive_s}")
        if self.max_queued_messages < 0:
            raise ValueError(f"max_queued_messages must be >= 0, got {self.max_queued_messages}")
        if self.password_env is not None and self.username is None:
            raise ValueError("password_env needs a username")
        if self.password_env is not None and self.password_env not in os.environ:
            raise ValueError(f"environment variable {self.password_env!r} (password_env) is not set")

    @property
    def password(self) -> str | None:
        """Read from the environment on demand, so it never sits in the config file."""
        return os.environ[self.password_env] if self.password_env else None
