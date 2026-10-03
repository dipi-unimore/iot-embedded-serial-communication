"""Packet -> bytes for publishing elsewhere (MQTT today; files, HTTP... later).

Every encoder produces the same logical envelope, in its own format:

    packet_number       Packet.number: per-type sequence number assigned by the Receiver
    received_timestamp  Packet.received_at_ms: ms since the Unix epoch
    packet_type, dto    what `data` is
    data                the packet as received on the serial line

    JsonPayloadEncoder    {"packet_number": .., "received_timestamp": .., "packet_type": ..,
                           "dto": "ImuDto", "data": {<dto.to_dict()>}}
    BinaryPayloadEncoder  packet_number u32 | received_timestamp u64 | type | fields | crc16

create_payload_encoder("json" | "binary", ...) picks one by name, as configured.
"""

from serial_receiver.serialization.binary_payload_encoder import BinaryPayloadEncoder
from serial_receiver.serialization.json_payload_encoder import JsonPayloadEncoder
from serial_receiver.serialization.payload_encoder import PayloadEncoder
from serial_receiver.serialization.payload_encoder_factory import create_payload_encoder

__all__ = ["BinaryPayloadEncoder", "JsonPayloadEncoder", "PayloadEncoder", "create_payload_encoder"]
