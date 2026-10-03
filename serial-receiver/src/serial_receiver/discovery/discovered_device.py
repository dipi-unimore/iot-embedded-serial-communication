from dataclasses import dataclass

from serial_receiver.discovery.probe_result import ProbeResult


@dataclass(frozen=True)
class DiscoveredDevice:
    """A serial port the OS exposes, with what was heard on it once probed.

    port_discovery.list_devices() creates it unprobed, and port_discovery.discover()
    returns a copy with `probe` filled in. It's frozen, so the copy is made with
    dataclasses.replace().

    The descriptive fields are whatever the OS reports, shown in the --discover
    report for the user's benefit only. Nothing is decided based on them: whether
    a port is "found" depends only on `probe`.
    """

    device: str  # e.g. /dev/ttyUSB0, /dev/cu.usbserial-XXXX, COM3: what gets passed to open_serial_port
    description: str
    usb_id: str | None  # "VID:PID" for USB devices, None otherwise
    manufacturer: str | None
    serial_number: str | None
    probe: ProbeResult | None = None  # None = not probed

    @property
    def speaks_protocol(self) -> bool:
        """Probed, and at least one CRC-valid packet was heard."""
        return self.probe is not None and self.probe.speaks_protocol
