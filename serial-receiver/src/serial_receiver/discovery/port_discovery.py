"""Enumerating serial ports and probing them for decodable protocol traffic.

Entry points:
    list_devices()            every port the OS exposes, unprobed (--discover --probe-seconds 0)
    discover(prober, s)       every port, probed in parallel for s seconds (--discover)
    find_protocol_device(...) the only port that speaks the protocol (receiver started without a port)

A port is "found" only if DeviceProber decodes CRC-valid packets from it.
Nothing about the hardware on the other end (USB IDs, names) is taken into account.
"""

import dataclasses
import threading
import time

from serial.tools import list_ports

from serial_receiver.discovery.device_prober import DeviceProber
from serial_receiver.discovery.discovered_device import DiscoveredDevice
from serial_receiver.discovery.port_discovery_error import PortDiscoveryError
from serial_receiver.discovery.probe_result import ProbeResult

# Extra time a probe gets beyond its listening window before it's given up on
# (some ports block in open() or read() instead of failing).
PROBE_GRACE_S = 2.0


def list_devices() -> list[DiscoveredDevice]:
    """Every serial port the OS exposes, sorted by name, unprobed. Opens nothing."""
    return sorted(
        (
            DiscoveredDevice(
                device=p.device,
                description=p.description,
                usb_id=f"{p.vid:04X}:{p.pid:04X}" if p.vid is not None and p.pid is not None else None,
                manufacturer=p.manufacturer,
                serial_number=p.serial_number,
            )
            for p in list_ports.comports()
        ),
        key=lambda d: d.device,
    )


def discover(prober: DeviceProber, probe_duration_s: float) -> list[DiscoveredDevice]:
    """Lists every port and probes all of them at once; devices that speak the
    protocol come first. probe_duration_s <= 0 only lists, without opening any port."""
    devices = list_devices()
    if probe_duration_s <= 0:
        return devices
    probed = _probe_all(devices, prober, probe_duration_s)
    return sorted(probed, key=lambda d: (not d.speaks_protocol, d.device))


def find_protocol_device(prober: DeviceProber, probe_duration_s: float) -> DiscoveredDevice:
    """The only port carrying decodable traffic, or PortDiscoveryError if none or several do.

    Used by the CLI when no port is configured. It refuses to guess between
    several matching ports, because picking the wrong device silently would be worse.
    """
    found = [d for d in discover(prober, probe_duration_s) if d.speaks_protocol]
    if len(found) == 1:
        return found[0]
    if not found:
        raise PortDiscoveryError(
            f"No serial port carries decodable packets at {prober.baudrate} baud "
            f"(listened {probe_duration_s:g}s). Check the baud rate, or set the port explicitly."
        )
    raise PortDiscoveryError(
        "Several serial ports carry decodable packets, pick one with --port:\n"
        + "\n".join(f"  {d.device}  {d.description}" for d in found)
    )


def _probe_all(devices: list[DiscoveredDevice], prober: DeviceProber, duration_s: float) -> list[DiscoveredDevice]:
    """Probes every port in parallel, each in its own daemon thread.

    - Parallel: total time is one probe, however many ports there are.
    - Bounded: after duration_s + PROBE_GRACE_S we stop waiting. A port whose
      open()/read() never returns (some Bluetooth ports do this) is reported as
      blocked instead of stalling discovery. Its thread is abandoned, and being a
      daemon it won't keep the process alive at exit.

    Each thread writes only its own key in `results`. A single dict assignment is
    atomic in CPython, so no lock is needed. A thread that finishes after the
    deadline writes too late, and its result is ignored.
    """
    results: dict[str, ProbeResult] = {}

    def run(device: str) -> None:
        results[device] = prober.probe(device, duration_s)

    threads = [threading.Thread(target=run, args=(d.device,), daemon=True) for d in devices]
    for thread in threads:
        thread.start()
    deadline = time.monotonic() + duration_s + PROBE_GRACE_S
    for thread in threads:
        thread.join(max(0.0, deadline - time.monotonic()))  # one shared deadline, not one per thread

    timed_out = ProbeResult(prober.baudrate, duration_s, error="no response: the port blocked on open/read")
    return [dataclasses.replace(d, probe=results.get(d.device, timed_out)) for d in devices]
