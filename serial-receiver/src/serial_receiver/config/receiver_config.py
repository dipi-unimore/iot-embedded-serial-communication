from dataclasses import dataclass

from serial_receiver.config.packet_binding_config import PacketBindingConfig


@dataclass(frozen=True)
class ReceiverConfig:
    """The whole receiver.toml, validated. Frozen: the CLI applies its overrides
    by making a copy (dataclasses.replace)."""

    port: str | None  # [serial] port; None = use discovery to find it
    baudrate: int  # [serial] baud
    stats_interval_s: float  # [stats] interval_s; <= 0 disables the Stats line
    packets: tuple[PacketBindingConfig, ...]  # one per [[packets]] block, unique packet types
