"""Data structures packet payloads are deserialized into.

Each DTO declares its own binary layout; which packet type maps to which DTO is
configured outside of it (receiver.toml / DtoRegistry), so the same DTO can be
reused for several packet types.
"""

from serial_receiver.dto.imu_dto import ImuDto
from serial_receiver.dto.packet_dto import PacketDto

__all__ = ["ImuDto", "PacketDto"]
