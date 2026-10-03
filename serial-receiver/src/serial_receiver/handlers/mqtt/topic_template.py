import string

from serial_receiver.decoding.packet import Packet

PLACEHOLDERS = ("packet_type", "dto", "client_id")


class TopicTemplate:
    """The MQTT topic each packet is published to, from a template:

        "iot/serial/{dto}"        -> iot/serial/imu
        "iot/{client_id}/{packet_type}" -> iot/serial-receiver-1/01

    Placeholders:
        {packet_type}  the type byte as two hex digits: "01"
        {dto}          the DTO class name, lowercased, without a "Dto" suffix: ImuDto -> "imu"
        {client_id}    the handler's MQTT client id

    Validated at construction: an unknown placeholder, or an MQTT wildcard (+ #),
    raises ValueError at startup instead of on the first packet. Rendering is
    cached per packet type, so steady-state publishing does no string formatting.
    """

    def __init__(self, template: str, client_id: str) -> None:
        if "+" in template or "#" in template:
            raise ValueError(f"topic {template!r} contains an MQTT wildcard (+ or #), not allowed when publishing")
        try:
            fields = {name for _, name, _, _ in string.Formatter().parse(template) if name is not None}
        except ValueError as exc:
            raise ValueError(f"topic {template!r} is not a valid template: {exc}") from None
        unknown = fields - set(PLACEHOLDERS)
        if unknown:
            raise ValueError(
                f"topic {template!r} has unknown placeholder(s) {sorted(unknown)}, allowed: {list(PLACEHOLDERS)}"
            )
        self._template = template
        self._client_id = client_id
        self._cache: dict[tuple[int, type], str] = {}

    def render(self, packet: Packet) -> str:
        key = (packet.packet_type, type(packet.dto))
        topic = self._cache.get(key)
        if topic is None:
            topic = self._template.format(
                packet_type=f"{packet.packet_type:02x}",
                dto=_dto_slug(type(packet.dto).__name__),
                client_id=self._client_id,
            )
            self._cache[key] = topic
        return topic


def _dto_slug(class_name: str) -> str:
    """ImuDto -> "imu", EnvDto -> "env", Weather -> "weather"."""
    if class_name.endswith("Dto") and len(class_name) > 3:
        class_name = class_name[:-3]
    return class_name.lower()
