"""Factory for orders, order items, payments, and returns.

Realism knobs baked in:

* **Customer skew** — a minority of loyal customers place most orders
  (Zipf-like weights), which makes repeat-buyer and Pareto analyses
  meaningful on the dashboard.
* **Product popularity skew** — revenue concentrates in a head of popular
  products.
* **Seasonality** — November/December are boosted, late summer dips.
* **Promotions** — applied only when the promotion window covers the order
  date; percentage promos discount each line, fixed promos hit the first line.

All money is rounded at line level and totals are sums of rounded lines, so
the accuracy data-quality checks (order total == Σ line totals == payment
amount) hold exactly.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

from faker import Faker

from src.main.models.customer import Customer
from src.main.models.order import Order, OrderItem, Return
from src.main.models.payment import PAYMENT_METHODS, Payment
from src.main.models.product import Product
from src.main.models.promotion import Promotion
from src.main.models.sales_channel import DEFAULT_CHANNELS
from src.main.utility.logger import get_logger

logger = get_logger(__name__)

#: Relative order volume per calendar month (index 1..12).
_MONTH_WEIGHTS = {1: 0.8, 2: 0.8, 3: 0.9, 4: 0.9, 5: 1.0, 6: 1.0,
                  7: 0.9, 8: 0.85, 9: 1.0, 10: 1.1, 11: 1.5, 12: 1.6}

_ORDER_STATUSES = (("delivered", 0.82), ("shipped", 0.08), ("processing", 0.06), ("cancelled", 0.04))
_RETURN_REASONS = (
    "Defective item", "Wrong size", "Not as described", "Changed mind",
    "Arrived late", "Better price found", "Damaged in transit",
)


@dataclass
class OrderBundle:
    """Everything produced for the transactional side of one generation run."""

    orders: list[Order] = field(default_factory=list)
    order_items: list[OrderItem] = field(default_factory=list)
    payments: list[Payment] = field(default_factory=list)
    returns: list[Return] = field(default_factory=list)


class OrderFactory:
    """Generates a referentially consistent transactional history."""

    def __init__(
        self,
        faker: Faker,
        rng: random.Random,
        max_items_per_order: int = 5,
        return_rate: float = 0.08,
    ) -> None:
        self._faker = faker
        self._rng = rng
        self._max_items = max(1, max_items_per_order)
        self._return_rate = min(max(return_rate, 0.0), 1.0)

    def build_orders(
        self,
        count: int,
        customers: list[Customer],
        products: list[Product],
        promotions: list[Promotion],
        window_start: date,
        window_end: date,
    ) -> OrderBundle:
        """Generate ``count`` orders plus their items, payments and returns."""
        bundle = OrderBundle()
        customer_weights = self._zipf_weights(len(customers), exponent=0.8)
        product_weights = self._zipf_weights(len(products), exponent=0.9)
        channels = [channel for channel, _ in DEFAULT_CHANNELS]
        channel_weights = [weight for _, weight in DEFAULT_CHANNELS]

        order_item_id = 1
        return_id = 1
        for order_id in range(1, count + 1):
            customer = self._rng.choices(customers, weights=customer_weights, k=1)[0]
            order_date = self._seasonal_datetime(window_start, window_end, customer.signup_date)
            channel = self._rng.choices(channels, weights=channel_weights, k=1)[0]
            promotion = self._pick_promotion(promotions, order_date.date())
            status = self._weighted_choice(_ORDER_STATUSES)

            items, order_item_id = self._build_items(
                order_id, order_item_id, products, product_weights, promotion
            )
            total_amount = round(sum(item.line_total for item in items), 2)

            bundle.orders.append(
                Order(
                    order_id=order_id,
                    customer_id=customer.customer_id,
                    channel_id=channel.channel_id,
                    promotion_id=promotion.promotion_id if promotion else None,
                    order_date=order_date,
                    status=status,
                    total_amount=total_amount,
                )
            )
            bundle.order_items.extend(items)
            bundle.payments.append(self._build_payment(order_id, order_date, total_amount, status))

            if status == "delivered":
                for item in items:
                    if self._rng.random() < self._return_rate:
                        bundle.returns.append(
                            self._build_return(return_id, item, order_date, window_end)
                        )
                        return_id += 1

        logger.debug(
            "Built {} orders / {} items / {} payments / {} returns",
            len(bundle.orders), len(bundle.order_items),
            len(bundle.payments), len(bundle.returns),
        )
        return bundle

    def _zipf_weights(self, size: int, exponent: float) -> list[float]:
        """Zipf-like weights after shuffling ranks, so popularity is not
        correlated with entity id."""
        ranks = list(range(1, size + 1))
        self._rng.shuffle(ranks)
        return [1.0 / (rank ** exponent) for rank in ranks]

    def _seasonal_datetime(self, start: date, end: date, not_before: date) -> datetime:
        """Random datetime in the window, month-weighted, after signup."""
        floor = max(start, not_before)
        if floor >= end:
            floor = start
        span_days = (end - floor).days or 1
        # Rejection-sample against the month weights for seasonality.
        while True:
            day = floor + timedelta(days=self._rng.randint(0, span_days))
            if self._rng.random() <= _MONTH_WEIGHTS[day.month] / 1.6:
                return datetime(
                    day.year, day.month, day.day,
                    self._rng.randint(6, 23), self._rng.randint(0, 59), self._rng.randint(0, 59),
                )

    def _pick_promotion(self, promotions: list[Promotion], order_day: date) -> Promotion | None:
        """~30% of orders use a promotion, if any is active that day."""
        if self._rng.random() >= 0.30:
            return None
        active = [p for p in promotions if p.is_active_on(order_day)]
        return self._rng.choice(active) if active else None

    def _build_items(
        self,
        order_id: int,
        next_item_id: int,
        products: list[Product],
        product_weights: list[float],
        promotion: Promotion | None,
    ) -> tuple[list[OrderItem], int]:
        """Create 1..max_items distinct product lines for one order."""
        line_count = self._rng.randint(1, self._max_items)
        chosen = self._rng.choices(products, weights=product_weights, k=line_count)
        # De-duplicate products within an order; quantity captures repeats.
        by_product: dict[str, Product] = {p.product_id: p for p in chosen}

        items: list[OrderItem] = []
        fixed_budget = (
            float(promotion.discount_value)
            if promotion and promotion.discount_type == "fixed_amount"
            else 0.0
        )
        for product in by_product.values():
            quantity = self._rng.randint(1, 4)
            unit_price = round(product.price * self._rng.uniform(0.97, 1.03), 2)
            gross = round(quantity * unit_price, 2)
            if promotion and promotion.discount_type == "percentage":
                discount = round(gross * promotion.discount_value / 100.0, 2)
            else:
                discount = round(min(fixed_budget, gross), 2)
                fixed_budget -= discount
            items.append(
                OrderItem(
                    order_item_id=next_item_id,
                    order_id=order_id,
                    product_id=product.product_id,
                    quantity=quantity,
                    unit_price=unit_price,
                    discount_amount=discount,
                    line_total=round(gross - discount, 2),
                )
            )
            next_item_id += 1
        return items, next_item_id

    def _build_payment(
        self, order_id: int, order_date: datetime, amount: float, order_status: str
    ) -> Payment:
        """One payment per order; cancelled orders end up refunded."""
        method = self._weighted_choice(PAYMENT_METHODS)
        status = "refunded" if order_status == "cancelled" else "completed"
        return Payment(
            payment_id=order_id,
            order_id=order_id,
            payment_method=method,
            amount=amount,
            payment_date=order_date + timedelta(minutes=self._rng.randint(0, 20)),
            status=status,
        )

    def _build_return(
        self, return_id: int, item: OrderItem, order_date: datetime, window_end: date
    ) -> Return:
        """Return of part or all of an order line, refunding net value."""
        quantity = self._rng.randint(1, item.quantity)
        # Refund the net (post-discount) share of the returned units.
        refund = round(item.line_total * quantity / item.quantity, 2)
        return_date = order_date + timedelta(days=self._rng.randint(3, 30))
        cap = datetime.combine(window_end, datetime.min.time())
        return Return(
            return_id=return_id,
            order_id=item.order_id,
            order_item_id=item.order_item_id,
            return_date=min(return_date, cap),
            quantity=quantity,
            refund_amount=refund,
            reason=self._rng.choice(_RETURN_REASONS),
        )

    def _weighted_choice(self, options: tuple[tuple[str, float], ...]) -> str:
        """Pick a label from (label, weight) pairs."""
        labels = [label for label, _ in options]
        weights = [weight for _, weight in options]
        return self._rng.choices(labels, weights=weights, k=1)[0]
