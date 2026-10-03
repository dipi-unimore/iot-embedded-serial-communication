import logging

from serial_receiver.decoding.packet import Packet
from serial_receiver.handlers.packet_handler import PacketHandler

log = logging.getLogger(__name__)


class PacketDispatcher:
    """Routes each decoded packet to the handlers bound to its type, in order.

    This is the "what to do with it" half of the configuration (packet type ->
    handlers). The other half, packet type -> DTO, is decoding.DtoRegistry.

        dispatcher = PacketDispatcher()
        dispatcher.register(0x01, LoggingPacketHandler())
        dispatcher.register(0x01, MyCsvWriter())      # several handlers per type, called in this order
        ...
        dispatcher.dispatch(packet)                   # called by Receiver for every decoded packet

    A decoded packet whose type has no handlers is simply dropped: it was still
    validated and counted. That's how an empty `handlers = []` in receiver.toml works.
    """

    def __init__(self) -> None:
        self._handlers: dict[int, list[PacketHandler]] = {}

    def register(self, packet_type: int, handler: PacketHandler) -> None:
        """Appends `handler` to the handlers of `packet_type`. The same instance can
        be registered for several types."""
        if not isinstance(handler, PacketHandler):
            raise TypeError(f"{handler!r} is not a PacketHandler")
        self._handlers.setdefault(packet_type, []).append(handler)

    def handlers_for(self, packet_type: int) -> list[PacketHandler]:
        """A copy of the handlers bound to `packet_type`, in call order."""
        return list(self._handlers.get(packet_type, ()))

    def dispatch(self, packet: Packet) -> None:
        """Calls handle(packet) on each handler bound to packet.packet_type,
        synchronously, on the caller's thread (the Receiver's read loop)."""
        for handler in self._handlers.get(packet.packet_type, ()):
            try:
                handler.handle(packet)
            except Exception:
                # One broken handler must not stop the stream or the other handlers.
                log.exception("%s failed on packet type 0x%02X", type(handler).__name__, packet.packet_type)
