from dataclasses import dataclass


@dataclass
class ReceiverStats:
    """Counters kept by Receiver, cumulative over the whole run (across reconnects).

    Every frame ends up in exactly one counter. `packets` means decoded and
    dispatched; each other counter is a reason the frame was dropped.
    """

    packets: int = 0  # decoded and handed to the dispatcher
    discarded_while_syncing: int = 0  # dropped before the first valid packet: expected noise, not a link error
    cobs_errors: int = 0  # frame wasn't valid COBS
    crc_errors: int = 0  # valid COBS, but the CRC didn't match: corrupted on the wire
    unknown_type: int = 0  # valid CRC, but no DTO configured for its type byte
    other_errors: int = 0  # valid CRC, but wrong size for its DTO (or too short)

    @property
    def errors(self) -> int:
        """Link/config errors after sync: what the "errors" percentage in the Stats line is based on."""
        return self.cobs_errors + self.crc_errors + self.unknown_type + self.other_errors
