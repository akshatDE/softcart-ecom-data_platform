"""Factory for marketing promotions."""

from __future__ import annotations

import random
from datetime import date, timedelta

from faker import Faker

from src.main.models.promotion import Promotion
from src.main.utility.logger import get_logger

logger = get_logger(__name__)

_CAMPAIGN_THEMES = [
    "Flash Sale", "Holiday Deal", "New Customer Offer", "Clearance Event",
    "Weekend Special", "Loyalty Reward", "Season Launch", "Bundle Bonus",
]


class PromotionFactory:
    """Generates promotions whose windows fall inside the order date range."""

    def __init__(self, faker: Faker, rng: random.Random) -> None:
        self._faker = faker
        self._rng = rng

    def build_promotions(self, count: int, window_start: date, window_end: date) -> list[Promotion]:
        """Create ``count`` promotions active somewhere within the window."""
        total_days = max((window_end - window_start).days - 14, 1)
        promotions: list[Promotion] = []
        for promotion_id in range(1, count + 1):
            start = window_start + timedelta(days=self._rng.randint(0, total_days))
            end = start + timedelta(days=self._rng.randint(7, 45))
            if end > window_end:
                end = window_end
            # Percentage promos dominate; fixed-amount promos are rarer.
            if self._rng.random() < 0.7:
                discount_type = "percentage"
                discount_value = float(self._rng.choice([5, 10, 15, 20, 25, 30]))
            else:
                discount_type = "fixed_amount"
                discount_value = float(self._rng.choice([5, 10, 15, 25, 50]))
            theme = self._rng.choice(_CAMPAIGN_THEMES)
            promotions.append(
                Promotion(
                    promotion_id=promotion_id,
                    promotion_code=f"{theme.split()[0].upper()}{promotion_id:03d}",
                    description=f"{theme} — {self._faker.catch_phrase()}",
                    discount_type=discount_type,
                    discount_value=discount_value,
                    start_date=start,
                    end_date=end,
                )
            )
        logger.debug("Built {} promotions", len(promotions))
        return promotions
