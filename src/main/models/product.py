"""Domain models for the MongoDB product catalog."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ProductVariant:
    """A sellable variant of a product (e.g. a colour/size combination)."""

    sku: str
    color: str
    size: str
    stock: int


@dataclass
class Product:
    """A catalog product stored as a semi-structured MongoDB document."""

    product_id: str
    name: str
    description: str
    brand: str
    category_name: str
    parent_category: str
    price: float
    cost: float
    attributes: dict[str, Any] = field(default_factory=dict)
    variants: list[ProductVariant] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    created_at: str = ""

    def to_document(self) -> dict[str, Any]:
        """Serialize into the nested document shape stored in MongoDB."""
        return {
            "product_id": self.product_id,
            "name": self.name,
            "description": self.description,
            "brand": {"name": self.brand},
            "category": {
                "name": self.category_name,
                "parent": self.parent_category,
                "path": f"{self.parent_category}/{self.category_name}",
            },
            "pricing": {"price": self.price, "cost": self.cost, "currency": "USD"},
            "attributes": self.attributes,
            "variants": [
                {"sku": v.sku, "color": v.color, "size": v.size, "stock": v.stock}
                for v in self.variants
            ],
            "tags": self.tags,
            "metadata": {"created_at": self.created_at, "source": "softcart-catalog"},
        }
