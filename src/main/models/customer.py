"""Domain models for customers and their addresses."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date
from typing import Any


@dataclass(frozen=True)
class Customer:
    """A SoftCart customer account (MySQL ``customers``)."""

    customer_id: int
    first_name: str
    last_name: str
    email: str
    phone: str
    signup_date: date

    def to_record(self) -> dict[str, Any]:
        """Return a flat dict suitable for DataFrame construction."""
        return asdict(self)


@dataclass(frozen=True)
class CustomerAddress:
    """A billing or shipping address (MySQL ``customer_addresses``)."""

    address_id: int
    customer_id: int
    address_type: str
    street: str
    city: str
    state: str
    country: str
    postal_code: str

    def to_record(self) -> dict[str, Any]:
        """Return a flat dict suitable for DataFrame construction."""
        return asdict(self)
