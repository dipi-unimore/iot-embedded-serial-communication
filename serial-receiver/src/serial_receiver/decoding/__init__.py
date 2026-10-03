"""Payload <-> Packet: CRC check, packet type lookup, DTO deserialization.

Every COBS-decoded payload is laid out as:

    [type: u8] [DTO fields...] [crc16: u16]

with crc16 (CRC-16/CCITT-FALSE) covering every byte before it, type included.
"""

from serial_receiver.decoding.dto_registry import DtoRegistry
from serial_receiver.decoding.packet import Packet
from serial_receiver.decoding.packet_decoder import PacketDecoder

__all__ = ["DtoRegistry", "Packet", "PacketDecoder"]
