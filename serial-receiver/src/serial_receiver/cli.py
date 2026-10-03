"""Command-line entry point (`uv run serial-receiver`, see [project.scripts] in pyproject.toml).

Two modes:
    receive (default)  load receiver.toml, apply CLI overrides, pick the port, then
                       build_receiver() and run_forever() until Ctrl+C
    --discover         probe every serial port and print a report, then exit

Precedence for settings: CLI flag > receiver.toml > built-in default. The port is
resolved as --port, then [serial] port, then discovery (the only port carrying
decodable packets).
"""

import argparse
import dataclasses
import logging
import sys
from pathlib import Path

from serial_receiver.config.config_error import ConfigError
from serial_receiver.config.config_loader import DEFAULT_BAUD, load_config
from serial_receiver.config.receiver_config import ReceiverConfig
from serial_receiver.config.receiver_factory import build_decoder, build_receiver
from serial_receiver.discovery import port_discovery
from serial_receiver.discovery.device_prober import DeviceProber
from serial_receiver.discovery.discovery_report import format_report
from serial_receiver.discovery.port_discovery_error import PortDiscoveryError

DEFAULT_CONFIG_PATH = Path("receiver.toml")
DEFAULT_PROBE_SECONDS = 3.0

log = logging.getLogger("serial_receiver")


def main() -> None:
    """Parses the arguments, sets up logging, and runs the selected mode."""
    parser = argparse.ArgumentParser(description="Receive and decode COBS + CRC-16 framed packets streamed over a serial port.")
    parser.add_argument(
        "-c", "--config", type=Path, default=DEFAULT_CONFIG_PATH,
        help=f"TOML config: serial settings + packet type -> DTO/handlers bindings (default: ./{DEFAULT_CONFIG_PATH})",
    )
    parser.add_argument("-p", "--port", help="serial port, overrides the config (default: the only port carrying decodable packets)")
    parser.add_argument("-b", "--baud", type=int, help="baud rate, overrides the config")
    parser.add_argument("--stats-interval", type=float, metavar="SECONDS", help="overrides the config, 0 = off")
    parser.add_argument(
        "--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="console log level (default: INFO)",
    )
    discovery = parser.add_argument_group("device discovery")
    discovery.add_argument(
        "--discover", action="store_true",
        help="probe every serial port at the configured baud rate, report which ones carry decodable packets, then exit",
    )
    discovery.add_argument(
        "--probe-seconds", type=float, default=DEFAULT_PROBE_SECONDS, metavar="SECONDS",
        help=f"how long each port is listened to (in parallel), by --discover and by port auto-detection; "
        f"0 = --discover only lists ports (default: {DEFAULT_PROBE_SECONDS:g})",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=args.log_level,
        format="%(asctime)s.%(msecs)03d %(levelname)-7s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    if args.discover:
        run_discovery(args)
        return

    config = apply_overrides(load_config_or_exit(args.config), args)

    # Port resolution: explicit flag, then config, then discovery. Discovery uses
    # the same decoder the receiver will use, so "found" means "these packets
    # will decode".
    port = args.port or config.port
    if port is None:
        probe_s = args.probe_seconds if args.probe_seconds > 0 else DEFAULT_PROBE_SECONDS
        log.info("No port configured: looking for decodable packets at %d baud (%gs)...", config.baudrate, probe_s)
        try:
            device = port_discovery.find_protocol_device(DeviceProber(build_decoder(config), config.baudrate), probe_s)
        except PortDiscoveryError as exc:
            sys.exit(str(exc))
        port = device.device
        log.info("Found %s (~%.1f pkt/s)", port, device.probe.rate_hz)

    receiver = build_receiver(config, port)
    try:
        receiver.run_forever()
    except KeyboardInterrupt:
        log.info("Stopped. Final stats: %s", receiver.stats)
    finally:
        receiver.close()  # lets handlers release resources, e.g. disconnect from the MQTT broker


def run_discovery(args: argparse.Namespace) -> None:
    """--discover: probe every port with a decoder built from the config, print the report."""
    # The config is only needed to name the DTOs packets decode into; without
    # one, probing still recognizes CRC-valid packets of any type.
    if args.config.exists():
        config = apply_overrides(load_config_or_exit(args.config), args)
    else:
        log.warning("%s not found: probing without DTOs (packet types will show as unconfigured)", args.config)
        config = apply_overrides(ReceiverConfig(port=None, baudrate=DEFAULT_BAUD, stats_interval_s=0.0, packets=()), args)

    prober = DeviceProber(build_decoder(config), config.baudrate)
    if args.probe_seconds > 0:
        log.info("Probing every serial port for %gs at %d baud...", args.probe_seconds, config.baudrate)
    print(format_report(port_discovery.discover(prober, args.probe_seconds)))


def load_config_or_exit(path: Path) -> ReceiverConfig:
    """load_config(), turning a ConfigError into a clean exit message instead of a traceback."""
    try:
        return load_config(path)
    except ConfigError as exc:
        sys.exit(f"Config error: {exc}")


def apply_overrides(config: ReceiverConfig, args: argparse.Namespace) -> ReceiverConfig:
    """Returns a copy of the (frozen) config with the CLI flags that were given applied on top.
    --port isn't applied here: main() resolves it, since it may come from discovery."""
    if args.baud is not None:
        config = dataclasses.replace(config, baudrate=args.baud)
    if args.stats_interval is not None:
        config = dataclasses.replace(config, stats_interval_s=args.stats_interval)
    return config


if __name__ == "__main__":
    main()
