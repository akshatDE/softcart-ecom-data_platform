"""Platform-neutral dataset generation.

Runs the domain factories and returns the dataset in memory, without writing
anything. Every target (local files, Postgres, Snowflake, Databricks) calls
:func:`generate_dataset` and only adds its own writer, so all of them load the
exact same data for a given seed.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import date
from typing import Any

import pandas as pd
from faker import Faker

from src.main.factories.customer_factory import CustomerFactory
from src.main.factories.order_factory import OrderFactory
from src.main.factories.product_factory import ProductFactory
from src.main.factories.promotion_factory import PromotionFactory
from src.main.models.sales_channel import DEFAULT_CHANNELS
from src.main.utility.exceptions import DataGenerationError

#: Relational tables in dependency order (parents before children).
TABLES = (
    "sales_channels", "promotions", "customers", "customer_addresses",
    "orders", "order_items", "payments", "returns",
)


@dataclass(frozen=True)
class GenerationSettings:
    """Knobs for one generation run; defaults mirror ``config_file.ini``."""

    num_customers: int = 500
    num_products: int = 200
    num_orders: int = 6000
    num_promotions: int = 20
    max_items_per_order: int = 5
    return_rate: float = 0.08
    start_date: date = date(2024, 1, 1)
    end_date: date = date(2026, 6, 30)
    seed: int = 42

    @classmethod
    def from_config(cls) -> GenerationSettings:
        """Read the ``[data_generation]`` section of the project config."""
        from src.main.utility.config_loader import get_config

        config = get_config()
        section = "data_generation"
        return cls(
            num_customers=config.get_int(section, "num_customers"),
            num_products=config.get_int(section, "num_products"),
            num_orders=config.get_int(section, "num_orders"),
            num_promotions=config.get_int(section, "num_promotions"),
            max_items_per_order=config.get_int(section, "max_items_per_order"),
            return_rate=config.get_float(section, "return_rate"),
            start_date=date.fromisoformat(config.get(section, "start_date")),
            end_date=date.fromisoformat(config.get(section, "end_date")),
            seed=config.get_int(section, "seed"),
        )


@dataclass(frozen=True)
class GeneratedDataset:
    """One DataFrame per relational table plus the product catalog documents."""

    settings: GenerationSettings
    frames: dict[str, pd.DataFrame]
    products: list[dict[str, Any]]

    @property
    def counts(self) -> dict[str, int]:
        """Row counts per table, products included."""
        counts = {name: len(frame) for name, frame in self.frames.items()}
        counts["products"] = len(self.products)
        return counts


def generate_dataset(settings: GenerationSettings | None = None) -> GeneratedDataset:
    """Build the full, referentially consistent dataset in memory.

    The same settings (including ``seed``) always produce the same rows; only
    each product's ``metadata.created_at`` timestamp differs between runs.
    """
    settings = settings or GenerationSettings()
    if settings.start_date >= settings.end_date:
        raise DataGenerationError("start_date must be before end_date")

    rng = random.Random(settings.seed)
    faker = Faker()
    faker.seed_instance(settings.seed)

    customer_factory = CustomerFactory(faker, rng)
    product_factory = ProductFactory(faker, rng)
    promotion_factory = PromotionFactory(faker, rng)
    order_factory = OrderFactory(
        faker, rng, settings.max_items_per_order, settings.return_rate
    )

    customers = customer_factory.build_customers(
        settings.num_customers, settings.start_date, settings.end_date
    )
    addresses = customer_factory.build_addresses(customers)
    products = product_factory.build_products(settings.num_products)
    promotions = promotion_factory.build_promotions(
        settings.num_promotions, settings.start_date, settings.end_date
    )
    bundle = order_factory.build_orders(
        settings.num_orders, customers, products, promotions,
        settings.start_date, settings.end_date,
    )

    frames: dict[str, pd.DataFrame] = {
        "sales_channels": pd.DataFrame([c.to_record() for c, _ in DEFAULT_CHANNELS]),
        "promotions": pd.DataFrame([p.to_record() for p in promotions]),
        "customers": pd.DataFrame([c.to_record() for c in customers]),
        "customer_addresses": pd.DataFrame([a.to_record() for a in addresses]),
        "orders": pd.DataFrame([o.to_record() for o in bundle.orders]),
        "order_items": pd.DataFrame([i.to_record() for i in bundle.order_items]),
        "payments": pd.DataFrame([p.to_record() for p in bundle.payments]),
        "returns": pd.DataFrame([r.to_record() for r in bundle.returns]),
    }
    return GeneratedDataset(
        settings=settings,
        frames=frames,
        products=[product.to_document() for product in products],
    )
