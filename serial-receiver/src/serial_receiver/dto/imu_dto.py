import struct
from dataclasses import dataclass
from typing import ClassVar

from serial_receiver.dto.packet_dto import PacketDto


@dataclass(frozen=True, slots=True)
class ImuDto(PacketDto):
    """Accelerometer sample: u32 timestamp + 3x float32, 16 bytes.

    With the type byte and the CRC, a packet is 19 bytes:

        offset  0  type          u8    (bound in receiver.toml, 0x01 by default)
        offset  1  timestamp_ms  u32   } LAYOUT "<Ifff"
        offset  5  ax            f32   }
        offset  9  ay            f32   }
        offset 13  az            f32   }
        offset 17  crc16         u16
    """

    LAYOUT: ClassVar[struct.Struct] = struct.Struct("<Ifff")

    timestamp_ms: int  # ms on the sender's clock, taken when the sample was read
    ax: float  # m/s^2
    ay: float
    az: float

    def __str__(self) -> str:
        # What LoggingPacketHandler prints for every IMU packet.
        return f"IMU t={self.timestamp_ms}ms ax={self.ax:+.3f} ay={self.ay:+.3f} az={self.az:+.3f} m/s^2"
