import struct

import pytest
import serial

from serial_receiver.decoding.dto_registry import DtoRegistry
from serial_receiver.decoding.packet import Packet
from serial_receiver.decoding.packet_decoder import PacketDecoder
from serial_receiver.discovery import device_prober
from serial_receiver.discovery.device_prober import DeviceProber
from serial_receiver.dto.imu_dto import ImuDto
from serial_receiver.protocol import cobs
from serial_receiver.protocol.crc import crc16_ccitt


class FakeSerial:
    """Serves a fixed byte stream, then nothing (like an idle port)."""

    def __init__(self, data: bytes) -> None:
        self._data = data

    @property
    def in_waiting(self) -> int:
        return len(self._data)

    def read(self, size: int) -> bytes:
        chunk, self._data = self._data[:size], self._data[size:]
        return chunk

    def __enter__(self) -> "FakeSerial":
        return self

    def __exit__(self, *exc) -> None:
        pass


@pytest.fixture
def decoder() -> PacketDecoder:
    registry = DtoRegistry()
    registry.register(0x01, ImuDto)
    return PacketDecoder(registry)


def frame(payload: bytes) -> bytes:
    return cobs.encode(payload) + b"\x00"


def test_reports_decoded_unconfigured_and_rejected(monkeypatch, decoder):
    imu = frame(decoder.encode(Packet(0x01, ImuDto(1, 0.0, 0.0, 9.81))))
    unconfigured_body = b"\x02\xaa\xbb"
    unconfigured = frame(unconfigured_body + struct.pack("<H", crc16_ccitt(unconfigured_body)))
    corrupted = frame(b"\x01" + bytes(18))  # bad CRC

    stream = b"boot noise\x00" + imu * 3 + unconfigured + corrupted
    monkeypatch.setattr(device_prober, "open_serial_port", lambda port, baud: FakeSerial(stream))

    result = DeviceProber(decoder, 921600).probe("/dev/fake", duration_s=0.05)

    assert result.error is None
    assert result.decoded == {0x01: 3}
    assert result.dto_names == {0x01: "ImuDto"}
    assert result.unconfigured == {0x02: 1}
    assert result.rejected_frames == 1  # "boot noise" is dropped by the initial resync, not counted
    assert result.speaks_protocol


def test_silent_port_does_not_speak_protocol(monkeypatch, decoder):
    monkeypatch.setattr(device_prober, "open_serial_port", lambda port, baud: FakeSerial(b""))
    result = DeviceProber(decoder, 921600).probe("/dev/fake", duration_s=0.05)
    assert not result.speaks_protocol
    assert result.rate_hz == 0.0


def test_open_failure_is_reported_not_raised(monkeypatch, decoder):
    def fail(port, baud):
        raise serial.SerialException("[Errno 16] Resource busy")

    monkeypatch.setattr(device_prober, "open_serial_port", fail)
    result = DeviceProber(decoder, 921600).probe("/dev/fake", duration_s=0.05)
    assert result.error == "[Errno 16] Resource busy"
    assert not result.speaks_protocol
