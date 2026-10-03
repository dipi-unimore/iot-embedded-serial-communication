import struct

from serial_receiver.decoding.packet import Packet
from serial_receiver.decoding.packet_decoder import PacketDecoder
from serial_receiver.serialization.payload_encoder import PayloadEncoder

# packet_number (u32) + received_timestamp (u64, ms since epoch), little-endian.
HEADER = struct.Struct("<IQ")


class BinaryPayloadEncoder(PayloadEncoder):
    """Encodes a packet as a fixed binary header followed by the serial packet:

        offset 0   packet_number       u32 LE   (wraps after 2^32 - 1)
        offset 4   received_timestamp  u64 LE   ms since the Unix epoch
        offset 12  packet              type | fields | crc16, exactly as received on
                                       the serial line, minus the COBS framing (an
                                       MQTT message is already delimited)

    For an IMU packet that's 12 + 19 = 31 bytes. A consumer unpacks the header
    with "<IQ" and decodes the rest exactly like the receiver does, with the same
    DTO layout, and can check the CRC end to end.
    """

    FORMAT = "binary"

    def encode(self, packet: Packet) -> bytes:
        header = HEADER.pack((packet.number or 0) % 2**32, packet.received_at_ms or 0)
        return header + PacketDecoder.encode(packet)
