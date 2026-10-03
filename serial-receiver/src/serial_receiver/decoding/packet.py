from dataclasses import dataclass

from serial_receiver.dto.packet_dto import PacketDto


@dataclass(frozen=True, slots=True)
class Packet:
    """A decoded packet: its type byte plus the DTO its fields were deserialized into.

    PacketDecoder.decode() produces it, and PacketDispatcher.dispatch() routes it to
    every PacketHandler bound to `packet_type`. The type travels alongside the DTO
    because a DTO doesn't know its own type byte: the same DTO class can be
    bound to several types.
    """

    packet_type: int
    dto: PacketDto
