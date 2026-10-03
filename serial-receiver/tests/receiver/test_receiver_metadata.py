import time

from serial_receiver.decoding.dto_registry import DtoRegistry
from serial_receiver.decoding.packet import Packet
from serial_receiver.decoding.packet_decoder import PacketDecoder
from serial_receiver.dto.imu_dto import ImuDto
from serial_receiver.handlers.packet_dispatcher import PacketDispatcher
from serial_receiver.handlers.packet_handler import PacketHandler
from serial_receiver.protocol import cobs
from serial_receiver.receiver.packet_counter import PacketCounter
from serial_receiver.receiver.receiver import Receiver


class Recorder(PacketHandler):
    def __init__(self) -> None:
        self.packets: list[Packet] = []

    def handle(self, packet: Packet) -> None:
        self.packets.append(packet)


def frame(packet_type: int) -> bytes:
    return cobs.encode(PacketDecoder.encode(Packet(packet_type, ImuDto(1, 0.0, 0.0, 9.81))))


def test_counter_is_per_type():
    counter = PacketCounter()
    assert [counter.next(t) for t in (1, 1, 2, 1, 2)] == [1, 2, 1, 3, 2]


def test_receiver_stamps_number_per_type_and_receive_time():
    registry = DtoRegistry()
    registry.register(0x01, ImuDto)
    registry.register(0x02, ImuDto)
    recorder = Recorder()
    dispatcher = PacketDispatcher()
    dispatcher.register(0x01, recorder)
    dispatcher.register(0x02, recorder)
    receiver = Receiver("/dev/null", 921600, PacketDecoder(registry), dispatcher)

    before = time.time_ns() // 1_000_000
    for packet_type in (0x01, 0x01, 0x02, 0x01):
        receiver._handle_frame(frame(packet_type))
    after = time.time_ns() // 1_000_000

    assert [(p.packet_type, p.number) for p in recorder.packets] == [(1, 1), (1, 2), (2, 1), (1, 3)]
    assert all(before <= p.received_at_ms <= after for p in recorder.packets)
