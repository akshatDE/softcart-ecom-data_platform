"""Factory for realistic customer and address data."""

from __future__ import annotations

import random
from datetime import date

from faker import Faker

from src.main.models.customer import Customer, CustomerAddress
from src.main.utility.logger import get_logger

logger = get_logger(__name__)

#: (country, weight) — SoftCart's main markets.
_COUNTRY_WEIGHTS: tuple[tuple[str, float], ...] = (
    ("United States", 0.55),
    ("Canada", 0.15),
    ("United Kingdom", 0.12),
    ("Germany", 0.08),
    ("Australia", 0.06),
    ("India", 0.04),
)


class CustomerFactory:
    """Generates referentially consistent customers and addresses."""

    def __init__(self, faker: Faker, rng: random.Random) -> None:
        self._faker = faker
        self._rng = rng

    def build_customers(self, count: int, signup_from: date, signup_to: date) -> list[Customer]:
        """Create ``count`` customers with unique emails and spread-out signups."""
        customers: list[Customer] = []
        seen_emails: set[str] = set()
        for customer_id in range(1, count + 1):
            first = self._faker.first_name()
            last = self._faker.last_name()
            email = f"{first}.{last}.{customer_id}@{self._faker.free_email_domain()}".lower()
            if email in seen_emails:  # defensive; the id suffix makes clashes unlikely
                email = f"user{customer_id}@softcartmail.com"
            seen_emails.add(email)
            customers.append(
                Customer(
                    customer_id=customer_id,
                    first_name=first,
                    last_name=last,
                    email=email,
                    phone=self._faker.phone_number(),
                    signup_date=self._faker.date_between_dates(signup_from, signup_to),
                )
            )
        logger.debug("Built {} customers", len(customers))
        return customers

    def build_addresses(self, customers: list[Customer]) -> list[CustomerAddress]:
        """Create one billing and one shipping address per customer."""
        addresses: list[CustomerAddress] = []
        countries = [c for c, _ in _COUNTRY_WEIGHTS]
        weights = [w for _, w in _COUNTRY_WEIGHTS]
        address_id = 1
        for customer in customers:
            country = self._rng.choices(countries, weights=weights, k=1)[0]
            city = self._faker.city()
            state = self._faker.state() if country == "United States" else self._faker.city()
            for address_type in ("billing", "shipping"):
                addresses.append(
                    CustomerAddress(
                        address_id=address_id,
                        customer_id=customer.customer_id,
                        address_type=address_type,
                        street=self._faker.street_address(),
                        city=city,
                        state=state,
                        country=country,
                        postal_code=self._faker.postcode(),
                    )
                )
                address_id += 1
        logger.debug("Built {} addresses", len(addresses))
        return addresses
