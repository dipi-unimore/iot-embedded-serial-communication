import dataclasses
import struct
from typing import ClassVar, Self


class PacketDto:
    """Base class for every DTO a packet payload can be deserialized into.

    A packet on the wire is [type: u8][fields...][crc16: u16]. A DTO describes
    only the middle part: the type byte and the CRC belong to the protocol and
    are handled by decoding.PacketDecoder.

    A subclass must be a dataclass declaring LAYOUT, a struct.Struct describing
    those field bytes. LAYOUT's values map 1:1, in order, onto the dataclass fields:

        @dataclass(frozen=True, slots=True)
        class EnvDto(PacketDto):
            LAYOUT: ClassVar[struct.Struct] = struct.Struct("<Iff")
            timestamp_ms: int     # I  uint32
            temperature: float    # f  float32
            humidity: float       # f  float32

    The layout must match the packed struct the sender uses for that packet type:
    "<" (little-endian, no padding), then one format character per field.

    A DTO doesn't know its own type byte. The binding type -> DTO lives in
    receiver.toml (or a DtoRegistry), so the same DTO can serve several packet
    types, e.g. two identical sensors.

    How it's used:
        - decoding.DtoRegistry.register() calls check_definition() once, at startup.
        - decoding.PacketDecoder.decode() calls from_bytes() for every packet of a
          bound type, after the CRC and length checks have passed.
        - decoding.PacketDecoder.encode() calls to_bytes() to build a payload.
        - serialization.JsonPayloadEncoder calls to_dict() for the published "data".
        - handlers receive the instance in Packet.dto. Overriding __str__ gives
          LoggingPacketHandler a readable line.
    """

    LAYOUT: ClassVar[struct.Struct]

    @classmethod
    def from_bytes(cls, data: bytes) -> Self:
        """Builds an instance from exactly LAYOUT.size bytes (PacketDecoder checks the size first)."""
        return cls(*cls.LAYOUT.unpack(data))

    def to_bytes(self) -> bytes:
        """The field bytes, in dataclass field order: inverse of from_bytes()."""
        return self.LAYOUT.pack(*dataclasses.astuple(self))

    def to_dict(self) -> dict[str, object]:
        """The fields as a plain dict, for text formats (e.g. the "data" object of the
        JSON payload published by the MQTT handler).

        Default: every dataclass field under its own name. Override it to rename
        fields, convert units or add derived values in the published data, without
        touching the binary layout.
        """
        return dataclasses.asdict(self)

    @classmethod
    def check_definition(cls) -> None:
        """Raises TypeError if the subclass can't work: not a dataclass, missing
        LAYOUT, or LAYOUT and fields disagreeing on how many values there are.

        Catching these at startup turns a typo in a DTO into a clear config error,
        instead of a struct.error (or silently shifted fields) on the first packet.
        """
        if not dataclasses.is_dataclass(cls):
            raise TypeError(f"{cls.__name__} must be a @dataclass")
        layout = getattr(cls, "LAYOUT", None)
        if not isinstance(layout, struct.Struct):
            raise TypeError(f"{cls.__name__}.LAYOUT must be a struct.Struct")
        # Count the values LAYOUT produces by unpacking a zero-filled buffer.
        n_values = len(layout.unpack(bytes(layout.size)))
        n_fields = len(dataclasses.fields(cls))
        if n_values != n_fields:
            raise TypeError(
                f"{cls.__name__}.LAYOUT {layout.format!r} has {n_values} values but the class has {n_fields} fields"
            )
