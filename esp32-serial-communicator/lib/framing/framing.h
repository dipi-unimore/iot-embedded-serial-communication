#pragma once

#include <stddef.h>
#include <stdint.h>

// Wire protocol shared by every firmware target. The Python side mirrors these
// layouts in serial-receiver/src/serial_receiver/packets.py - change both together.
//
// Every packet is a packed, little-endian struct laid out as:
//
//     [type: u8] [fields...] [crc16: u16]
//
// crc16 is a CRC-16/CCITT-FALSE over every byte before it (type included).
// PacketSerial then COBS-encodes the whole struct and appends the 0x00 delimiter,
// so on the wire it's: [COBS(packet)] [0x00].
//
// The leading type byte lets several payloads share one link: each PacketType
// maps to exactly one fixed struct layout on both ends.

enum PacketType : uint8_t {
    PACKET_TYPE_IMU = 0x01,
};

struct ImuPacket {
    uint8_t type;        // always PACKET_TYPE_IMU
    uint32_t timestamp;  // ms since boot, taken when the sample was read
    float ax, ay, az;    // acceleration, m/s^2
    uint16_t crc;
} __attribute__((packed));
static_assert(sizeof(ImuPacket) == 19, "ImuPacket layout must match the Python receiver");

// CRC-16/CCITT-FALSE: poly 0x1021, init 0xFFFF, no reflection, no final XOR.
uint16_t crc16_ccitt(const uint8_t *data, size_t len);

// Computes and stores pkt.crc over every byte that precedes it. Every packet
// struct must end with a uint16_t crc field.
template <typename T>
void framing_seal(T &pkt) {
    pkt.crc = crc16_ccitt(reinterpret_cast<const uint8_t *>(&pkt), sizeof(T) - sizeof(pkt.crc));
}
