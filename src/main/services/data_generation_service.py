"""Synthetic source-data generation for SoftCart.

Generates a referentially consistent e-commerce history with Faker and the
domain factories, then persists it as flat files under
``[data_generation] output_dir`` (CSV for relational entities, JSON for the
product catalog). Keeping generation and source loading as separate steps
lets the Airflow DAG re-load sources without regenerating data.
"""

from __future__ import annotations

import json
import random
from datetime import date, datetime
from pathlib import Path

import pandas as pd
from faker import Faker

from src.main.factories.customer_factory import CustomerFactory
from src.main.factories.order_factory import OrderFactory
from src.main.factories.product_factory import ProductFactory
from src.main.factories.promotion_factory import PromotionFactory
from src.main.models.sales_channel import DEFAULT_CHANNELS
from src.main.utility.config_loader import get_config
from src.main.utility.exceptions import DataGenerationError
from src.main.utility.logger import get_logger

logger = get_logger(__name__)

PRODUCTS_FILE = "products.json"
CSV_ENTITIES = (
    "sales_channels", "promotions", "customers", "customer_addresses",
    "orders", "order_items", "payments", "returns",
)


class DataGenerationService:
    """Orchestrates the factories and persists their output to disk."""

    def __init__(self) -> None:
        config = get_config()
        self.output_dir: Path = config.get_path("data_generation", "output_dir")
        self.num_customers = config.get_int("data_generation", "num_customers")
        self.num_products = config.get_int("data_generation", "num_products")
        self.num_orders = config.get_int("data_generation", "num_orders")
        self.num_promotions = config.get_int("data_generation", "num_promotions")
        self.max_items_per_order = config.get_int("data_generation", "max_items_per_order")
        self.return_rate = config.get_float("data_generation", "return_rate")
        self.window_start = date.fromisoformat(config.get("data_generation", "start_date"))
        self.window_end = date.fromisoformat(config.get("data_generation", "end_date"))
        seed = config.get_int("data_generation", "seed")

        self._rng = random.Random(seed)
        self._faker = Faker()
        self._faker.seed_instance(seed)

    def generate(self) -> dict[str, int]:
        """Generate the full dataset and write it to the output directory.

        Returns:
            Row counts per entity, for logging and Airflow XCom visibility.
        """
        logger.info(
            "Data generation started: {} customers, {} products, {} orders ({} → {})",
            self.num_customers, self.num_products, self.num_orders,
            self.window_start, self.window_end,
        )
        if self.window_start >= self.window_end:
            raise DataGenerationError("start_date must be before end_date")

        customer_factory = CustomerFactory(self._faker, self._rng)
        product_factory = ProductFactory(self._faker, self._rng)
        promotion_factory = PromotionFactory(self._faker, self._rng)
        order_factory = OrderFactory(
            self._faker, self._rng, self.max_items_per_order, self.return_rate
        )

        customers = customer_factory.build_customers(
            self.num_customers, self.window_start, self.window_end
        )
        addresses = customer_factory.build_addresses(customers)
        products = product_factory.build_products(self.num_products)
        promotions = promotion_factory.build_promotions(
            self.num_promotions, self.window_start, self.window_end
        )
        bundle = order_factory.build_orders(
            self.num_orders, customers, products, promotions,
            self.window_start, self.window_end,
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
        counts = self._persist(frames, products)
        logger.info("Data generation finished: {}", counts)
        return counts

    def _persist(self, frames: dict[str, pd.DataFrame], products: list) -> dict[str, int]:
        """Write CSVs and the product JSON; return row counts."""
        try:
            self.output_dir.mkdir(parents=True, exist_ok=True)
            counts: dict[str, int] = {}
            for name, frame in frames.items():
                path = self.output_dir / f"{name}.csv"
                frame.to_csv(path, index=False)
                counts[name] = len(frame)
                logger.debug("Wrote {} rows to {}", len(frame), path)

            documents = [product.to_document() for product in products]
            products_path = self.output_dir / PRODUCTS_FILE
            products_path.write_text(json.dumps(documents, indent=2), encoding="utf-8")
            counts["products"] = len(documents)

            manifest = {
                "generated_at": datetime.now().isoformat(),
                "counts": counts,
            }
            (self.output_dir / "manifest.json").write_text(
                json.dumps(manifest, indent=2), encoding="utf-8"
            )
            return counts
        except OSError as exc:
            raise DataGenerationError(f"Failed to persist generated data: {exc}") from exc


def run() -> dict[str, int]:
    """Airflow-friendly entry point."""
    return DataGenerationService().generate()
