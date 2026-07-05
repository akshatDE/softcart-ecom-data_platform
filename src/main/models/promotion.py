"""Domain model for promotions."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date
from typing import Any


@dataclass(frozen=True)
class Promotion:
    """A marketing promotion (MySQL ``promotions``).

    ``discount_type`` is either ``percentage`` (value = percent off) or
    ``fixed_amount`` (value = flat currency discount per order).
    """

    promotion_id: int
    promotion_code: str
    description: str
    discount_type: str
    discount_value: float
    start_date: date
    end_date: date

    def to_record(self) -> dict[str, Any]:
        """Return a flat dict suitable for DataFrame construction."""
        return asdict(self)

    def is_active_on(self, day: date) -> bool:
        """Return True if the promotion is valid on ``day``."""
        return self.start_date <= day <= self.end_date
