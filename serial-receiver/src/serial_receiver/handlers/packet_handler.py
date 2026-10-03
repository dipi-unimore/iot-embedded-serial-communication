from abc import ABC, abstractmethod

from serial_receiver.decoding.packet import Packet


class PacketHandler(ABC):
    """Callback that does something with a decoded packet: log it, store it, forward it...

    This is the extension point for "what happens to the data". The rest of the
    pipeline is generic: once a packet decodes, PacketDispatcher calls handle()
    on every handler bound to its type, in the order they were registered.

    Binding:
        - receiver.toml: list the class in a [[packets]] block's `handlers`, as
          "package.module:Class" or { class = "...", options = {...} }. The config
          loader instantiates it once at startup, passing `options` to __init__
          as keyword arguments.
        - in code: PacketDispatcher.register(packet_type, MyHandler(...)).

    One instance serves all the packet types it's bound to, so handle() should
    check packet.packet_type (or the DTO's class) if it treats them differently.

    Contract for handle():
        - It runs on the Receiver's read thread, so it should be quick. Anything slow
          (network, disk flushes) delays the reading of the next bytes. Hand off to
          a queue or a thread if needed.
        - An exception doesn't stop the receiver: PacketDispatcher logs it and
          moves on to the next handler and the next packet.
        - The Packet and its DTO are frozen. Treat them as read-only.
        - packet.number and packet.received_at_ms are set by the Receiver
          (per-type sequence number, receive time in ms since the epoch).

    Override close() if the handler holds resources (see MqttPacketHandler).
    """

    @abstractmethod
    def handle(self, packet: Packet) -> None: ...

    def close(self) -> None:
        """Releases resources (connections, files) at shutdown. Default: nothing to do.

        Called once per instance by PacketDispatcher.close(), even if the instance
        is bound to several packet types. No handle() call follows it.
        """
