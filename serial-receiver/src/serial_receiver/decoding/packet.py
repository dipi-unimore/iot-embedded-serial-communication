from dataclasses import dataclass, field

from serial_receiver.dto.packet_dto import PacketDto


@dataclass(frozen=True, slots=True)
class Packet:
    """A decoded packet: its type byte, the DTO its fields were deserialized into,
    and the receive metadata the Receiver adds.

    PacketDecoder.decode() produces it with packet_type and dto only. The Receiver
    then stamps `number` and `received_at_ms` (via dataclasses.replace) before
    PacketDispatcher.dispatch() routes it to every PacketHandler bound to
    `packet_type`. The type travels alongside the DTO because a DTO doesn't know
    its own type byte: the same DTO class can be bound to several types.

    The metadata fields are excluded from equality: two packets with the same type
    and content compare equal whenever they were received.
    """

    packet_type: int
    dto: PacketDto
    # Per-type sequence number assigned by the Receiver: the n-th packet of this
    # type since the receiver started (1, 2, 3...). None if not received through a Receiver.
    number: int | None = field(default=None, compare=False)
    # Wall-clock time the Receiver decoded it, in ms since the Unix epoch.
    received_at_ms: int | None = field(default=None, compare=False)
