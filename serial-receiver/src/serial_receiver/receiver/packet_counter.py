from collections import defaultdict


class PacketCounter:
    """Hands out per-packet-type sequence numbers: 1, 2, 3... separately for each type.

    The Receiver calls next() once for every decoded packet and stores the result
    in Packet.number. The counters live as long as the Receiver: they aren't reset
    when the serial port reconnects, so numbers stay unique for the whole run.
    Downstream (e.g. on an MQTT topic), a gap in the numbers of one type means
    packets of that type were lost after decoding.
    """

    def __init__(self) -> None:
        self._counts: defaultdict[int, int] = defaultdict(int)

    def next(self, packet_type: int) -> int:
        self._counts[packet_type] += 1
        return self._counts[packet_type]
