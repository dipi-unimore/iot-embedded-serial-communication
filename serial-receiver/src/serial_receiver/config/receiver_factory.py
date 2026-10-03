"""Wiring: turns a loaded ReceiverConfig into the runtime objects.

    ReceiverConfig.packets (one PacketBindingConfig per [[packets]] block)
        binding.packet_type + binding.dto_cls   -> DtoRegistry       -> PacketDecoder
        binding.packet_type + binding.handlers  -> PacketDispatcher
    PacketDecoder + PacketDispatcher + port/baud/stats  -> Receiver

The decoder is built on its own as well (build_decoder) because discovery needs
exactly the same decoding rules as the receiver, without any handlers.
"""

import logging

from serial_receiver.config.receiver_config import ReceiverConfig
from serial_receiver.decoding.dto_registry import DtoRegistry
from serial_receiver.decoding.packet_decoder import PacketDecoder
from serial_receiver.handlers.packet_dispatcher import PacketDispatcher
from serial_receiver.receiver.receiver import Receiver

log = logging.getLogger(__name__)


def build_decoder(config: ReceiverConfig) -> PacketDecoder:
    """A decoder knowing one DTO per configured packet type."""
    registry = DtoRegistry()
    for binding in config.packets:
        registry.register(binding.packet_type, binding.dto_cls)
    return PacketDecoder(registry)


def build_receiver(config: ReceiverConfig, port: str) -> Receiver:
    """Wires a Receiver from a loaded config: the decoder plus one set of
    dispatcher handlers per configured packet type. Logs the resulting bindings,
    so the startup output shows what will happen to each packet type."""
    dispatcher = PacketDispatcher()
    for binding in config.packets:
        for handler in binding.handlers:
            dispatcher.register(binding.packet_type, handler)
        log.info(
            "Packet type 0x%02X -> %s, handlers: %s",
            binding.packet_type,
            binding.dto_cls.__name__,
            ", ".join(type(h).__name__ for h in binding.handlers) or "none (decoded, then dropped)",
        )

    return Receiver(port, config.baudrate, build_decoder(config), dispatcher, config.stats_interval_s)
