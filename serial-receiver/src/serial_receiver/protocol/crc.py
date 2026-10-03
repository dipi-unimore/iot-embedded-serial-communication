"""CRC-16/CCITT-FALSE, the checksum appended to every packet by the sender.

The sender computes it over every byte of the packet before the CRC field (type
byte and fields) and stores it as a little-endian uint16 in the last two bytes.
decoding.PacketDecoder recomputes it over the same bytes and drops the packet if
the two differ.
"""


def crc16_ccitt(data: bytes) -> int:
    """Poly 0x1021, init 0xFFFF, no reflection, no final XOR (check value 0x29B1).

    Plain bitwise version, most significant bit first. At the packet rates
    involved (hundreds per second, ~20 bytes each), a lookup table isn't worth it.
    """
    crc = 0xFFFF
    for byte in data:
        crc ^= byte << 8  # bring the next byte into the top half of the register
        for _ in range(8):
            # Shift one bit out; if it was a 1, "subtract" (XOR) the polynomial.
            crc = ((crc << 1) ^ 0x1021) & 0xFFFF if crc & 0x8000 else (crc << 1) & 0xFFFF
    return crc
