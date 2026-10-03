from collections.abc import Iterator

from serial_receiver.dto.packet_dto import PacketDto


class DtoRegistry:
    """Which DTO class each packet type byte is deserialized into.

    This is the "what" half of the configuration: packet type -> DTO class. The
    "what to do with it" half (packet type -> handlers) lives in
    handlers.PacketDispatcher. Both are filled from receiver.toml by
    config.receiver_factory, or by hand:

        registry = DtoRegistry()
        registry.register(0x01, ImuDto)
        decoder = PacketDecoder(registry)   # the decoder looks types up here

    Everything is validated in register(), at startup, so the hot path
    (PacketDecoder.decode -> get) can assume every entry is usable.
    """

    def __init__(self) -> None:
        self._dto_by_type: dict[int, type[PacketDto]] = {}

    def register(self, packet_type: int, dto_cls: type[PacketDto]) -> None:
        """Binds a type byte to a DTO class.

        Raises ValueError for a type outside 0x00-0xFF or already bound, and
        TypeError for a class that isn't a well-formed PacketDto (see
        PacketDto.check_definition). The same DTO class may be bound to
        several types.
        """
        if not 0 <= packet_type <= 0xFF:
            raise ValueError(f"packet type must fit in one byte (0x00-0xFF), got {packet_type}")
        if packet_type in self._dto_by_type:
            raise ValueError(
                f"packet type 0x{packet_type:02X} is already bound to {self._dto_by_type[packet_type].__name__}"
            )
        if not (isinstance(dto_cls, type) and issubclass(dto_cls, PacketDto)):
            raise TypeError(f"{dto_cls!r} is not a PacketDto subclass")
        dto_cls.check_definition()
        self._dto_by_type[packet_type] = dto_cls

    def get(self, packet_type: int) -> type[PacketDto] | None:
        """The DTO class bound to `packet_type`, or None (PacketDecoder turns that
        into UnknownPacketTypeError)."""
        return self._dto_by_type.get(packet_type)

    def __iter__(self) -> Iterator[tuple[int, type[PacketDto]]]:
        """Yields (packet_type, dto_cls) pairs."""
        return iter(self._dto_by_type.items())

    def __len__(self) -> int:
        return len(self._dto_by_type)
