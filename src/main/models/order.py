"""Domain models for orders, order items, and returns."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class Order:
    """An order header (MySQL ``orders``)."""

    order_id: int
    customer_id: int
    channel_id: int
    promotion_id: int | None
    order_date: datetime
    status: str
    total_amount: float

    def to_record(self) -> dict[str, Any]:
        """Return a flat dict suitable for DataFrame construction."""
        return asdict(self)


@dataclass(frozen=True)
class OrderItem:
    """A single order line (MySQL ``order_items``)."""

    order_item_id: int
    order_id: int
    product_id: str
    quantity: int
    unit_price: float
    discount_amount: float
    line_total: float

    def to_record(self) -> dict[str, Any]:
        """Return a flat dict suitable for DataFrame construction."""
        return asdict(self)


@dataclass(frozen=True)
class Return:
    """A product return against an order item (MySQL ``returns``)."""

    return_id: int
    order_id: int
    order_item_id: int
    return_date: datetime
    quantity: int
    refund_amount: float
    reason: str

    def to_record(self) -> dict[str, Any]:
        """Return a flat dict suitable for DataFrame construction."""
        return asdict(self)
