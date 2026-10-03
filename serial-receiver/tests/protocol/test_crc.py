from serial_receiver.protocol.crc import crc16_ccitt


def test_crc16_ccitt_false_check_value():
    # Standard check value for CRC-16/CCITT-FALSE.
    assert crc16_ccitt(b"123456789") == 0x29B1
