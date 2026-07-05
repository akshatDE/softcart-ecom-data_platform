"""Factory for the semi-structured product catalog."""

from __future__ import annotations

import random
from datetime import datetime, timezone

from faker import Faker

from src.main.models.product import Product, ProductVariant
from src.main.utility.logger import get_logger

logger = get_logger(__name__)

#: parent_category -> (subcategory, (min_price, max_price), brands)
_CATALOG_BLUEPRINT: dict[str, list[tuple[str, tuple[float, float], list[str]]]] = {
    "Electronics": [
        ("Laptops", (450.0, 2600.0), ["Novatech", "Lumina", "ByteForge"]),
        ("Smartphones", (200.0, 1400.0), ["Lumina", "Pixelon", "Vertex"]),
        ("Headphones", (25.0, 450.0), ["EchoWave", "Pulse Audio", "Vertex"]),
        ("Smart Home", (20.0, 300.0), ["HomeSense", "Novatech"]),
    ],
    "Fashion": [
        ("Men's Apparel", (12.0, 180.0), ["UrbanThread", "Northline", "Coastal"]),
        ("Women's Apparel", (12.0, 220.0), ["Velvet & Vine", "Coastal", "UrbanThread"]),
        ("Footwear", (25.0, 260.0), ["Stride", "Northline"]),
        ("Accessories", (8.0, 150.0), ["Velvet & Vine", "Stride"]),
    ],
    "Home & Kitchen": [
        ("Cookware", (15.0, 320.0), ["ChefCraft", "HearthLine"]),
        ("Furniture", (60.0, 1200.0), ["HearthLine", "OakNest"]),
        ("Bedding", (20.0, 250.0), ["OakNest", "CloudRest"]),
    ],
    "Sports & Outdoors": [
        ("Fitness Equipment", (18.0, 800.0), ["IronPeak", "FlexCore"]),
        ("Camping & Hiking", (15.0, 500.0), ["TrailBound", "IronPeak"]),
    ],
    "Beauty & Health": [
        ("Skincare", (8.0, 120.0), ["GlowLab", "PureLeaf"]),
        ("Personal Care", (5.0, 90.0), ["PureLeaf", "GlowLab"]),
    ],
}

_COLORS = ["Black", "White", "Navy", "Red", "Green", "Silver", "Rose Gold"]
_SIZES = ["XS", "S", "M", "L", "XL", "One Size"]
_TAG_POOL = [
    "bestseller", "new-arrival", "eco-friendly", "premium", "budget",
    "limited-edition", "gift-idea", "clearance", "exclusive", "trending",
]


class ProductFactory:
    """Generates catalog products across a fixed category hierarchy."""

    def __init__(self, faker: Faker, rng: random.Random) -> None:
        self._faker = faker
        self._rng = rng

    def build_products(self, count: int) -> list[Product]:
        """Create ``count`` products spread across every subcategory."""
        subcategories = [
            (parent, sub, price_range, brands)
            for parent, subs in _CATALOG_BLUEPRINT.items()
            for sub, price_range, brands in subs
        ]
        products: list[Product] = []
        for index in range(1, count + 1):
            parent, sub, (low, high), brands = self._rng.choice(subcategories)
            price = round(self._rng.uniform(low, high), 2)
            # Margins between 35% and 65% keep cost realistic relative to price.
            cost = round(price * self._rng.uniform(0.35, 0.65), 2)
            adjective = self._faker.word().capitalize()
            products.append(
                Product(
                    product_id=f"P{index:05d}",
                    name=f"{self._rng.choice(brands)} {adjective} {sub.rstrip('s')}",
                    description=self._faker.sentence(nb_words=12),
                    brand=self._rng.choice(brands),
                    category_name=sub,
                    parent_category=parent,
                    price=price,
                    cost=cost,
                    attributes=self._build_attributes(parent),
                    variants=self._build_variants(index),
                    tags=self._rng.sample(_TAG_POOL, k=self._rng.randint(1, 4)),
                    created_at=datetime.now(timezone.utc).isoformat(),
                )
            )
        logger.debug("Built {} products", len(products))
        return products

    def _build_attributes(self, parent_category: str) -> dict[str, object]:
        """Category-appropriate semi-structured attributes."""
        base: dict[str, object] = {
            "weight_kg": round(self._rng.uniform(0.1, 15.0), 2),
            "rating": round(self._rng.uniform(2.8, 5.0), 1),
            "review_count": self._rng.randint(0, 4200),
        }
        if parent_category == "Electronics":
            base["warranty_months"] = self._rng.choice([12, 24, 36])
            base["battery_life_hours"] = self._rng.randint(4, 30)
        elif parent_category == "Fashion":
            base["material"] = self._rng.choice(["cotton", "polyester", "wool", "leather"])
        return base

    def _build_variants(self, product_index: int) -> list[ProductVariant]:
        """Between one and four colour/size variants per product."""
        return [
            ProductVariant(
                sku=f"P{product_index:05d}-V{v}",
                color=self._rng.choice(_COLORS),
                size=self._rng.choice(_SIZES),
                stock=self._rng.randint(0, 500),
            )
            for v in range(1, self._rng.randint(2, 5))
        ]
