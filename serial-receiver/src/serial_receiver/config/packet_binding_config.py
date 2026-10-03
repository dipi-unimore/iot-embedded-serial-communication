from dataclasses import dataclass

from serial_receiver.dto.packet_dto import PacketDto
from serial_receiver.handlers.packet_handler import PacketHandler


@dataclass(frozen=True)
class PacketBindingConfig:
    """One [[packets]] block, resolved: which DTO a packet type is deserialized
    into, and which handlers (already instantiated) receive it.

    The config loader produces it, holding real classes and objects rather than
    strings. receiver_factory then splits it across DtoRegistry
    (packet_type -> dto_cls) and PacketDispatcher (packet_type -> handlers).
    """

    packet_type: int
    dto_cls: type[PacketDto]
    handlers: tuple[PacketHandler, ...]  # called in this order; may be empty
