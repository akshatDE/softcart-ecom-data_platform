"""Domain model and static reference data for sales channels."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class SalesChannel:
    """A sales channel (MySQL ``sales_channels``)."""

    channel_id: int
    channel_name: str
    channel_type: str

    def to_record(self) -> dict[str, Any]:
        """Return a flat dict suitable for DataFrame construction."""
        return asdict(self)


#: Canonical channel list — mirrored in resources/config/seed_data.sql.
#: The float is the share of orders placed through that channel.
DEFAULT_CHANNELS: tuple[tuple[SalesChannel, float], ...] = (
    (SalesChannel(1, "SoftCart Web", "web"), 0.34),
    (SalesChannel(2, "SoftCart Mobile App", "mobile"), 0.26),
    (SalesChannel(3, "Amazon Marketplace", "marketplace"), 0.18),
    (SalesChannel(4, "eBay Marketplace", "marketplace"), 0.10),
    (SalesChannel(5, "Instagram Shop", "social"), 0.08),
    (SalesChannel(6, "Partner Kiosk", "retail"), 0.04),
)
