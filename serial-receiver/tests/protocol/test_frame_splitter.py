from serial_receiver.protocol import cobs
from serial_receiver.protocol.frame_splitter import FrameSplitter


def test_drops_partial_first_frame_and_handles_chunking():
    frames = [cobs.encode(bytes([i, 0, i])) for i in range(1, 4)]
    stream = b"tail-of-a-frame" + b"\x00" + b"\x00".join(frames) + b"\x00"

    splitter = FrameSplitter()
    received = []
    for i in range(0, len(stream), 7):  # arbitrary chunk boundaries
        received.extend(splitter.feed(stream[i : i + 7]))

    assert received == frames


def test_discards_oversized_frame_and_resyncs():
    good = cobs.encode(b"\x01\x02\x03")
    splitter = FrameSplitter(max_frame_len=32)
    received = list(splitter.feed(b"\x00" + b"\xaa" * 100 + b"\x00" + good + b"\x00"))
    assert received == [good]
    assert splitter.overflows == 1
