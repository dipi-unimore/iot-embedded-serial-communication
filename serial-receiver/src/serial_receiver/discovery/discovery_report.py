"""Human-readable rendering of a discovery run, for the CLI."""

from serial_receiver.discovery.discovered_device import DiscoveredDevice
from serial_receiver.discovery.probe_result import ProbeResult


def format_report(devices: list[DiscoveredDevice]) -> str:
    probed = any(d.probe is not None for d in devices)
    found = sum(d.speaks_protocol for d in devices)
    header = f"{len(devices)} serial port(s)"
    if probed:
        header += f", {found} speaking the protocol"
    lines = [header + ":", ""]

    for d in devices:
        marker = "*" if d.speaks_protocol else " "
        lines.append(f"{marker} {d.device:<36} {d.usb_id or '-':<10} {d.description}")
        details = [f"manufacturer: {d.manufacturer}" if d.manufacturer else None,
                   f"serial: {d.serial_number}" if d.serial_number else None]
        if any(details):
            lines.append("      " + "   ".join(x for x in details if x))
        if d.probe is not None:
            lines.append("      " + _format_probe(d.probe))

    if not devices:
        lines.append("  (no serial ports)")
    if probed:
        lines += ["", "* = decodable packets received"]
    return "\n".join(lines)


def _format_probe(probe: ProbeResult) -> str:
    head = f"probe @ {probe.baudrate} baud, {probe.duration_s:g}s: "
    if probe.error:
        return head + f"ERROR - {probe.error}"
    if not probe.speaks_protocol:
        return head + f"no valid packets (rejected frames: {probe.rejected_frames})"

    parts = [f"{t:#04x} {probe.dto_names[t]} x{n}" for t, n in sorted(probe.decoded.items())]
    parts += [f"{t:#04x} (no DTO configured) x{n}" for t, n in sorted(probe.unconfigured.items())]
    return head + f"STREAMING ~{probe.rate_hz:.1f} pkt/s | " + ", ".join(parts) + f" | rejected: {probe.rejected_frames}"
