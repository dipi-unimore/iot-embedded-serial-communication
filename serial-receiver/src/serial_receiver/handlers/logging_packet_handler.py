import logging

from serial_receiver.decoding.packet import Packet
from serial_receiver.handlers.packet_handler import PacketHandler

log = logging.getLogger(__name__)


class LoggingPacketHandler(PacketHandler):
    """Logs every packet's DTO (its __str__) at the given level.

    The default handler in receiver.toml. Its only option is `level`, a level
    name ("DEBUG", "INFO"...) or number:

        { class = "serial_receiver.handlers.logging_packet_handler:LoggingPacketHandler",
          options = { level = "DEBUG" } }

    The output format is up to each DTO's __str__ (see ImuDto), so this handler
    works unchanged for any packet type.
    """

    def __init__(self, level: str | int = "INFO") -> None:
        # Validated here, so a typo in receiver.toml fails at startup (the config
        # loader turns the ValueError into a ConfigError), not on the first packet.
        if isinstance(level, str):
            levels = logging.getLevelNamesMapping()
            if level.upper() not in levels:
                raise ValueError(f"unknown log level {level!r}")
            level = levels[level.upper()]
        self._level = level

    def handle(self, packet: Packet) -> None:
        log.log(self._level, "%s", packet.dto)
