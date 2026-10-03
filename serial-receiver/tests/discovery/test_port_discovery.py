import threading
from types import SimpleNamespace

import pytest

from serial_receiver.discovery import port_discovery
from serial_receiver.discovery.discovery_report import format_report
from serial_receiver.discovery.port_discovery_error import PortDiscoveryError
from serial_receiver.discovery.probe_result import ProbeResult


def port(device, vid=None, pid=None, description="n/a"):
    return SimpleNamespace(
        device=device, vid=vid, pid=pid, description=description, serial_number=None, manufacturer=None
    )


NON_USB = port("/dev/ttyS0")
USB_A = port("/dev/ttyUSB0", 0x1234, 0x5678, "USB serial A")
USB_B = port("/dev/ttyUSB1", 0xABCD, 0x0001, "USB serial B")

STREAMING = ProbeResult(921600, 1.0, decoded={1: 100}, dto_names={1: "ImuDto"})
SILENT = ProbeResult(921600, 1.0, rejected_frames=3)


class FakeProber:
    baudrate = 921600

    def __init__(self, results: dict[str, ProbeResult]) -> None:
        self._results = results
        self.probed: list[str] = []

    def probe(self, device: str, duration_s: float) -> ProbeResult:
        self.probed.append(device)
        return self._results.get(device, SILENT)


@pytest.fixture
def ports(monkeypatch):
    def set_ports(*items):
        monkeypatch.setattr(port_discovery.list_ports, "comports", lambda: list(items))

    return set_ports


def test_list_devices_reports_os_info_without_judging_it(ports):
    ports(USB_A, NON_USB)
    devices = port_discovery.list_devices()
    assert [d.device for d in devices] == ["/dev/ttyS0", "/dev/ttyUSB0"]
    assert devices[0].usb_id is None
    assert devices[1].usb_id == "1234:5678"
    assert all(d.probe is None for d in devices)


def test_discover_probes_every_port_and_lists_speakers_first(ports):
    ports(NON_USB, USB_A, USB_B)
    prober = FakeProber({"/dev/ttyUSB1": STREAMING})

    devices = port_discovery.discover(prober, 1.0)

    assert sorted(prober.probed) == ["/dev/ttyS0", "/dev/ttyUSB0", "/dev/ttyUSB1"]
    assert [d.device for d in devices] == ["/dev/ttyUSB1", "/dev/ttyS0", "/dev/ttyUSB0"]
    assert [d.speaks_protocol for d in devices] == [True, False, False]


def test_discover_with_zero_seconds_opens_nothing(ports):
    ports(USB_A)
    prober = FakeProber({})
    devices = port_discovery.discover(prober, 0)
    assert prober.probed == []
    assert devices[0].probe is None


def test_hanging_port_is_reported_not_waited_for(ports, monkeypatch):
    monkeypatch.setattr(port_discovery, "PROBE_GRACE_S", 0.1)
    ports(USB_A, USB_B)
    release = threading.Event()

    class HangingProber(FakeProber):
        def probe(self, device, duration_s):
            if device == "/dev/ttyUSB0":
                release.wait(5)  # simulates an open() that never returns
            return super().probe(device, duration_s)

    try:
        devices = {d.device: d for d in port_discovery.discover(HangingProber({"/dev/ttyUSB1": STREAMING}), 0.05)}
    finally:
        release.set()

    assert "blocked" in devices["/dev/ttyUSB0"].probe.error
    assert devices["/dev/ttyUSB1"].speaks_protocol


def test_find_protocol_device(ports):
    ports(USB_A, USB_B)
    assert port_discovery.find_protocol_device(FakeProber({"/dev/ttyUSB1": STREAMING}), 1.0).device == "/dev/ttyUSB1"

    with pytest.raises(PortDiscoveryError, match="No serial port carries decodable packets at 921600 baud"):
        port_discovery.find_protocol_device(FakeProber({}), 1.0)

    with pytest.raises(PortDiscoveryError, match="Several"):
        port_discovery.find_protocol_device(FakeProber({"/dev/ttyUSB0": STREAMING, "/dev/ttyUSB1": STREAMING}), 1.0)


def test_report(ports):
    ports(NON_USB, USB_A, USB_B)
    prober = FakeProber({
        "/dev/ttyUSB0": ProbeResult(921600, 3.0, decoded={1: 300}, dto_names={1: "ImuDto"}, rejected_frames=2),
        "/dev/ttyS0": ProbeResult(921600, 3.0, error="Resource busy"),
    })

    report = format_report(port_discovery.discover(prober, 3.0))

    assert report.startswith("3 serial port(s), 1 speaking the protocol:")
    assert "* /dev/ttyUSB0" in report
    assert "STREAMING ~100.0 pkt/s | 0x01 ImuDto x300 | rejected: 2" in report
    assert "ERROR - Resource busy" in report
    assert "no valid packets (rejected frames: 3)" in report


def test_report_list_only(ports):
    ports(USB_A)
    report = format_report(port_discovery.discover(FakeProber({}), 0))
    assert report.startswith("1 serial port(s):")
    assert "probe @" not in report
