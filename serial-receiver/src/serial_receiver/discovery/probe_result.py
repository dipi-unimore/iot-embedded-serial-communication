from dataclasses import dataclass, field


@dataclass(frozen=True)
class ProbeResult:
    """What DeviceProber heard on a port while listening to it for duration_s.

    Frames are classified the way Receiver would classify them:

        decoded        CRC valid and a DTO configured for the type: the receiver would handle these
        unconfigured   CRC valid, but no DTO for the type: the sender speaks the protocol,
                       the config just doesn't know this type
        rejected       bad COBS / CRC / length, or oversized. Includes the noise right after
                       opening (boot logs, the partial first frame is already dropped by FrameSplitter)
    """

    baudrate: int
    duration_s: float
    decoded: dict[int, int] = field(default_factory=dict)  # packet type -> packets decoded into its DTO
    dto_names: dict[int, str] = field(default_factory=dict)  # packet type -> DTO class name, for the report
    unconfigured: dict[int, int] = field(default_factory=dict)  # packet type -> CRC-valid packets with no DTO configured
    rejected_frames: int = 0
    error: str | None = None  # the port couldn't be opened/read (busy, gone, blocked); counters are then empty

    @property
    def decoded_total(self) -> int:
        return sum(self.decoded.values())

    @property
    def speaks_protocol(self) -> bool:
        """At least one CRC-valid packet: something on this port speaks our protocol,
        even if some of its packet types have no DTO configured.

        This is the test discovery uses to call a port "found". A CRC-16 match on
        random noise is very unlikely, so a single valid packet is enough.
        """
        return bool(self.decoded or self.unconfigured)

    @property
    def rate_hz(self) -> float:
        """Valid packets per second over the whole probe. Slightly underestimates
        the real rate if the device spent part of the probe booting."""
        valid = self.decoded_total + sum(self.unconfigured.values())
        return valid / self.duration_s if self.duration_s > 0 else 0.0
