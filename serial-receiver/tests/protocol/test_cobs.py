import pytest

from serial_receiver.protocol import cobs
from serial_receiver.protocol.cobs_decode_error import CobsDecodeError


@pytest.mark.parametrize(
    "data",
    [b"", b"\x00", b"\x00\x00", b"\x11\x22\x00\x33", bytes(range(1, 255)), bytes(range(256)) * 3, b"\x01" * 600],
)
def test_roundtrip_never_contains_zero(data):
    encoded = cobs.encode(data)
    assert 0 not in encoded
    assert cobs.decode(encoded) == data


def test_known_vector():
    assert cobs.encode(b"\x11\x22\x00\x33") == b"\x03\x11\x22\x02\x33"


@pytest.mark.parametrize("frame", [b"\x05\x11\x22", b"\x02\x11\x00\x01"])
def test_rejects_malformed(frame):
    with pytest.raises(CobsDecodeError):
        cobs.decode(frame)
