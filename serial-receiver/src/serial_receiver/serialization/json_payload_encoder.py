import json
from typing import Any

from serial_receiver.decoding.packet import Packet
from serial_receiver.serialization.payload_encoder import PayloadEncoder


class JsonPayloadEncoder(PayloadEncoder):
    """Encodes a packet as a compact UTF-8 JSON object:

        {"packet_number": 42, "received_timestamp": 1791042044608, "packet_type": 1,
         "dto": "ImuDto", "data": {"timestamp_ms": 94, "ax": 0.146, "ay": 0.478, "az": 9.81}}

    `data` is packet.dto.to_dict(), so a DTO controls its own JSON by overriding
    to_dict() (field names, units, derived values).

    float_digits: floats are rounded to this many significant digits. Packet
    fields are float32 on the wire, and a float32 widened to a Python float
    prints as 0.14600000083446503. 7 digits is what float32 actually carries,
    so 0.146 comes out as 0.146. None keeps the full value.
    """

    FORMAT = "json"

    def __init__(self, float_digits: int | None = 7) -> None:
        if float_digits is not None and not 1 <= float_digits <= 17:
            raise ValueError(f"float_digits must be between 1 and 17 (or None), got {float_digits}")
        self._float_digits = float_digits

    def encode(self, packet: Packet) -> bytes:
        envelope = {
            "packet_number": packet.number,
            "received_timestamp": packet.received_at_ms,
            "packet_type": packet.packet_type,
            "dto": type(packet.dto).__name__,
            "data": self._round_floats(packet.dto.to_dict()),
        }
        return json.dumps(envelope, separators=(",", ":"), ensure_ascii=False).encode("utf-8")

    def _round_floats(self, value: Any) -> Any:
        """Rounds every float in a (possibly nested) to_dict() result."""
        if self._float_digits is None:
            return value
        if isinstance(value, float):
            return float(f"{value:.{self._float_digits}g}")
        if isinstance(value, dict):
            return {k: self._round_floats(v) for k, v in value.items()}
        if isinstance(value, (list, tuple)):
            return [self._round_floats(v) for v in value]
        return value
