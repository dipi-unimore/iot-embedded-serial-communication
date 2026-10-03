"""Picks a PayloadEncoder by its configured format name."""

from serial_receiver.serialization.binary_payload_encoder import BinaryPayloadEncoder
from serial_receiver.serialization.json_payload_encoder import JsonPayloadEncoder
from serial_receiver.serialization.payload_encoder import PayloadEncoder

FORMATS = (JsonPayloadEncoder.FORMAT, BinaryPayloadEncoder.FORMAT)


def create_payload_encoder(format: str, float_digits: int | None = 7) -> PayloadEncoder:
    """"json" -> JsonPayloadEncoder(float_digits), "binary" -> BinaryPayloadEncoder.

    Raises ValueError for any other name. float_digits only applies to JSON
    (binary carries the exact float32 bytes).
    """
    if format == JsonPayloadEncoder.FORMAT:
        return JsonPayloadEncoder(float_digits)
    if format == BinaryPayloadEncoder.FORMAT:
        return BinaryPayloadEncoder()
    raise ValueError(f"unknown payload format {format!r}, expected one of {', '.join(FORMATS)}")
