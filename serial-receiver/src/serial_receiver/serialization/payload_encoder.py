from abc import ABC, abstractmethod

from serial_receiver.decoding.packet import Packet


class PayloadEncoder(ABC):
    """Turns a decoded Packet into the bytes a handler publishes (e.g. an MQTT payload).

    Implementations are stateless and thread-safe: one instance can serve every
    packet type a handler is bound to. They expect a Packet that went through the
    Receiver, i.e. with `number` and `received_at_ms` set.
    """

    #: Short format name, as used in configuration ("json", "binary").
    FORMAT: str

    @abstractmethod
    def encode(self, packet: Packet) -> bytes: ...
