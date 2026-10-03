import logging

import pytest

from serial_receiver.decoding.packet import Packet
from serial_receiver.dto.imu_dto import ImuDto
from serial_receiver.handlers.logging_packet_handler import LoggingPacketHandler
from serial_receiver.handlers.packet_dispatcher import PacketDispatcher
from serial_receiver.handlers.packet_handler import PacketHandler


class RecordingHandler(PacketHandler):
    def __init__(self) -> None:
        self.received: list[Packet] = []

    def handle(self, packet: Packet) -> None:
        self.received.append(packet)


class FailingHandler(PacketHandler):
    def handle(self, packet: Packet) -> None:
        raise RuntimeError("boom")


PACKET = Packet(0x01, ImuDto(1, 0.0, 0.0, 9.81))


def test_routes_by_packet_type():
    imu, other = RecordingHandler(), RecordingHandler()
    dispatcher = PacketDispatcher()
    dispatcher.register(0x01, imu)
    dispatcher.register(0x02, other)

    dispatcher.dispatch(PACKET)

    assert imu.received == [PACKET]
    assert other.received == []


def test_failing_handler_does_not_stop_the_others(caplog):
    after = RecordingHandler()
    dispatcher = PacketDispatcher()
    dispatcher.register(0x01, FailingHandler())
    dispatcher.register(0x01, after)

    dispatcher.dispatch(PACKET)

    assert after.received == [PACKET]
    assert "FailingHandler failed" in caplog.text


def test_logging_handler_logs_dto_at_configured_level(caplog):
    caplog.set_level(logging.DEBUG)
    LoggingPacketHandler(level="debug").handle(PACKET)
    assert caplog.records[-1].levelno == logging.DEBUG
    assert caplog.records[-1].getMessage() == str(PACKET.dto)


def test_logging_handler_rejects_unknown_level():
    with pytest.raises(ValueError):
        LoggingPacketHandler(level="LOUD")


class ClosingHandler(PacketHandler):
    def __init__(self, fail: bool = False) -> None:
        self.closed = 0
        self._fail = fail

    def handle(self, packet: Packet) -> None:
        pass

    def close(self) -> None:
        self.closed += 1
        if self._fail:
            raise RuntimeError("boom")


def test_close_closes_each_distinct_handler_once_even_if_one_fails(caplog):
    shared, failing, other = ClosingHandler(), ClosingHandler(fail=True), ClosingHandler()
    dispatcher = PacketDispatcher()
    dispatcher.register(0x01, shared)
    dispatcher.register(0x02, shared)
    dispatcher.register(0x01, failing)
    dispatcher.register(0x02, other)

    dispatcher.close()

    assert (shared.closed, failing.closed, other.closed) == (1, 1, 1)
    assert "ClosingHandler failed to close" in caplog.text
