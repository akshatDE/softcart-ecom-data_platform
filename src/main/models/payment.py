"""Domain model for order payments."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any

#: Payment methods offered at SoftCart checkout, with realistic usage weights.
PAYMENT_METHODS: tuple[tuple[str, float], ...] = (
    ("credit_card", 0.38),
    ("debit_card", 0.22),
    ("paypal", 0.18),
    ("apple_pay", 0.12),
    ("gift_card", 0.05),
    ("bank_transfer", 0.05),
)


@dataclass(frozen=True)
class Payment:
    """A payment against an order (MySQL ``payments``)."""

    payment_id: int
    order_id: int
    payment_method: str
    amount: float
    payment_date: datetime
    status: str

    def to_record(self) -> dict[str, Any]:
        """Return a flat dict suitable for DataFrame construction."""
        return asdict(self)
