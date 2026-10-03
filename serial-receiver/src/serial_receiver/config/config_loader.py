"""Parses receiver.toml into a ReceiverConfig, importing the DTO and handler
classes it references by "package.module:ClassName" path.

This is where the configuration becomes dynamic: the receiver never hardcodes
which DTOs or handlers exist. Each [[packets]] block names them by import path,
and they're imported, validated and (for handlers) instantiated here, once, at
startup. Any problem raises ConfigError with the block number and the reason,
before a single byte is read.

    [serial]
    port = "/dev/ttyUSB0"              # optional: when omitted, the only port carrying decodable packets
    baud = 921600

    [stats]
    interval_s = 5.0                   # 0 disables the periodic stats line

    [handlers.mqtt]                    # a named handler: one instance, shareable by several packet types
    class = "serial_receiver.handlers.mqtt.mqtt_packet_handler:MqttPacketHandler"
    [handlers.mqtt.options]
    client_id = "serial-receiver-1"
    ...

    [[packets]]
    type = 0x01                        # packet type byte, as sent by the sender
    dto = "serial_receiver.dto.imu_dto:ImuDto"
    handlers = [
        "mqtt",                                                                # a named handler
        "serial_receiver.handlers.logging_packet_handler:LoggingPacketHandler", # a new instance
        { class = "my_pkg.my_handler:MyHandler", options = { some_arg = 1 } },  # a new instance
    ]

Handler entries in [[packets]]:
    "name"                         the [handlers.name] instance. Created once, on first use, and
                                   shared by every packet type that lists it (e.g. one MQTT
                                   connection). Names can't contain ':', so they never clash
                                   with class paths.
    "pkg.mod:Class"                a new instance, no options
    { class = ..., options = ... } a new instance with options
"""

import importlib
import logging
import tomllib
from pathlib import Path
from typing import Any

from serial_receiver.config.config_error import ConfigError
from serial_receiver.config.packet_binding_config import PacketBindingConfig
from serial_receiver.config.receiver_config import ReceiverConfig
from serial_receiver.dto.packet_dto import PacketDto
from serial_receiver.handlers.packet_handler import PacketHandler

log = logging.getLogger(__name__)

DEFAULT_BAUD = 921600  # must match the sender's baud rate
DEFAULT_STATS_INTERVAL_S = 5.0


def load_config(path: Path) -> ReceiverConfig:
    """Reads and validates the whole file. Raises ConfigError on any problem.

    Optional sections fall back to defaults ([serial] port -> None, i.e. discovery;
    baud -> DEFAULT_BAUD; [stats] interval_s -> DEFAULT_STATS_INTERVAL_S). At least
    one [[packets]] block is required, since otherwise nothing could be decoded.
    """
    try:
        with path.open("rb") as f:
            raw = tomllib.load(f)
    except FileNotFoundError:
        raise ConfigError(f"config file not found: {path}") from None
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(f"{path}: invalid TOML: {exc}") from None

    serial_section = raw.get("serial", {})
    stats_section = raw.get("stats", {})
    packet_entries = raw.get("packets", [])
    if not packet_entries:
        raise ConfigError(f"{path}: no [[packets]] configured - nothing could be decoded")

    named_specs = _parse_named_handlers(raw.get("handlers", {}))
    named_instances: dict[str, PacketHandler] = {}  # filled on first use by _resolve_handler
    bindings = tuple(
        _parse_binding(entry, index, named_specs, named_instances) for index, entry in enumerate(packet_entries)
    )
    for name in sorted(set(named_specs) - set(named_instances)):
        log.warning("[handlers.%s] is defined but no [[packets]] block uses it: not created", name)
    seen: set[int] = set()
    for binding in bindings:
        if binding.packet_type in seen:
            raise ConfigError(f"{path}: packet type 0x{binding.packet_type:02X} is configured more than once")
        seen.add(binding.packet_type)

    return ReceiverConfig(
        port=serial_section.get("port"),
        baudrate=int(serial_section.get("baud", DEFAULT_BAUD)),
        stats_interval_s=float(stats_section.get("interval_s", DEFAULT_STATS_INTERVAL_S)),
        packets=bindings,
    )


def _parse_named_handlers(section: Any) -> dict[str, dict[str, Any]]:
    """The [handlers.<name>] tables -> {name: {class, options}}, shape-checked only.
    Nothing is imported or instantiated here: that happens on first use."""
    if not isinstance(section, dict):
        raise ConfigError("[handlers] must be a table of named handlers: [handlers.<name>]")
    for name, spec in section.items():
        where = f"[handlers.{name}]"
        if ":" in name:
            raise ConfigError(f"{where}: handler names can't contain ':' (that's how class paths are told apart)")
        if not isinstance(spec, dict) or "class" not in spec:
            raise ConfigError(f"{where}: needs a 'class' key (and optionally an [handlers.{name}.options] table)")
        if not isinstance(spec.get("options", {}), dict):
            raise ConfigError(f"{where}: 'options' must be a table")
    return section


def _parse_binding(
    entry: dict[str, Any],
    index: int,
    named_specs: dict[str, dict[str, Any]],
    named_instances: dict[str, PacketHandler],
) -> PacketBindingConfig:
    """One [[packets]] block -> PacketBindingConfig: validates the type byte, imports
    and checks the DTO class, resolves the handlers (named or new instances)."""
    where = f"[[packets]] #{index + 1}"
    for key in ("type", "dto"):
        if key not in entry:
            raise ConfigError(f"{where}: missing '{key}'")

    packet_type = entry["type"]
    if not isinstance(packet_type, int) or not 0 <= packet_type <= 0xFF:
        raise ConfigError(f"{where}: 'type' must be an integer 0x00-0xFF, got {packet_type!r}")

    dto_cls = _import_object(entry["dto"], where)
    if not (isinstance(dto_cls, type) and issubclass(dto_cls, PacketDto)):
        raise ConfigError(f"{where}: {entry['dto']!r} is not a PacketDto subclass")
    try:
        dto_cls.check_definition()
    except TypeError as exc:
        raise ConfigError(f"{where}: {exc}") from None

    handlers = tuple(
        _resolve_handler(spec, where, named_specs, named_instances) for spec in entry.get("handlers", [])
    )
    return PacketBindingConfig(packet_type, dto_cls, handlers)


def _resolve_handler(
    spec: Any,
    where: str,
    named_specs: dict[str, dict[str, Any]],
    named_instances: dict[str, PacketHandler],
) -> PacketHandler:
    """A bare name -> the shared [handlers.<name>] instance, created on first use.
    Anything else (class path, inline table) -> a new instance via _build_handler."""
    if isinstance(spec, str) and ":" not in spec:
        if spec not in named_specs:
            defined = ", ".join(sorted(named_specs)) or "none"
            raise ConfigError(f"{where}: unknown handler name {spec!r} (defined [handlers.*]: {defined})")
        if spec not in named_instances:
            named_instances[spec] = _build_handler(named_specs[spec], f"[handlers.{spec}]")
        return named_instances[spec]
    return _build_handler(spec, where)


def _build_handler(spec: str | dict[str, Any], where: str) -> PacketHandler:
    """A handler entry is either "pkg.mod:Class" (no options) or
    { class = "pkg.mod:Class", options = {...} }, where options become the
    constructor's keyword arguments. A constructor rejecting them (TypeError for
    unknown arguments, ValueError for bad values) becomes a ConfigError."""
    if isinstance(spec, str):
        class_path, options = spec, {}
    elif isinstance(spec, dict) and "class" in spec:
        class_path, options = spec["class"], spec.get("options", {})
    else:
        raise ConfigError(
            f"{where}: a handler must be a [handlers.*] name, a class path or {{ class = ..., options = {{...}} }}"
        )

    handler_cls = _import_object(class_path, where)
    if not (isinstance(handler_cls, type) and issubclass(handler_cls, PacketHandler)):
        raise ConfigError(f"{where}: {class_path!r} is not a PacketHandler subclass")
    try:
        return handler_cls(**options)
    except (TypeError, ValueError) as exc:
        raise ConfigError(f"{where}: can't create {class_path} with options {options}: {exc}") from None


def _import_object(path: str, where: str) -> Any:
    """Imports "package.module:Name" and returns the attribute. The module can be
    any importable one, inside this package or not (e.g. your own handlers)."""
    module_name, sep, attr = path.partition(":")
    if not sep or not module_name or not attr:
        raise ConfigError(f"{where}: {path!r} must be in the form 'package.module:ClassName'")
    try:
        module = importlib.import_module(module_name)
    except ImportError as exc:
        raise ConfigError(f"{where}: can't import module {module_name!r}: {exc}") from None
    try:
        return getattr(module, attr)
    except AttributeError:
        raise ConfigError(f"{where}: module {module_name!r} has no {attr!r}") from None
