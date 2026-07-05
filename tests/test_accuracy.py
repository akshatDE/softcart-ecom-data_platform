"""Accuracy checks: values are correct and logically valid."""

from __future__ import annotations

import re

from tests.conftest import scalar

_EMAIL_PATTERN = re.compile(r"^[\w.+-]+@[\w-]+\.[\w.-]+$")


def test_order_totals_equal_item_sums(staging) -> None:
    """Each order's total_amount must equal the sum of its line totals."""
    schema = staging.staging_schema
    mismatches = scalar(
        staging,
        f"""
        SELECT COUNT(*) FROM {schema}.stg_orders o
        JOIN (SELECT order_id, SUM(line_total) AS line_sum
              FROM {schema}.stg_order_items GROUP BY order_id) items
        USING (order_id)
        WHERE ABS(o.total_amount - items.line_sum) > 0.01
        """,
    )
    assert mismatches == 0, f"{mismatches} orders where total != sum of items"


def test_payment_amounts_match_order_totals(staging) -> None:
    """Payments must cover exactly the order total."""
    schema = staging.staging_schema
    mismatches = scalar(
        staging,
        f"""
        SELECT COUNT(*) FROM {schema}.stg_orders o
        JOIN (SELECT order_id, SUM(amount) AS paid
              FROM {schema}.stg_payments GROUP BY order_id) p
        USING (order_id)
        WHERE ABS(o.total_amount - p.paid) > 0.01
        """,
    )
    assert mismatches == 0, f"{mismatches} orders where payment != total"


def test_emails_have_valid_format(staging) -> None:
    """Every staged customer email must look like an email address."""
    schema = staging.staging_schema
    emails = staging.read_sql(f"SELECT email FROM {schema}.stg_customers")["email"]
    invalid = [e for e in emails if not _EMAIL_PATTERN.match(str(e))]
    assert not invalid, f"{len(invalid)} invalid emails, e.g. {invalid[:3]}"


def test_net_revenue_equals_gross_minus_discount(analytics) -> None:
    """fact_sales arithmetic: net = gross - discount, row by row."""
    mismatches = scalar(
        analytics,
        "SELECT COUNT(*) FROM fact_sales "
        "WHERE ABS(gross_revenue - discount_amount - net_revenue) > 0.01",
    )
    assert mismatches == 0, f"{mismatches} fact rows with broken revenue arithmetic"


def test_refunds_never_exceed_line_net_revenue(analytics) -> None:
    """A return cannot refund more than the net value of its order line."""
    violations = scalar(
        analytics,
        """
        SELECT COUNT(*) FROM fact_returns r
        JOIN fact_sales s USING (order_item_id)
        WHERE r.refund_amount > s.net_revenue + 0.01
        """,
    )
    assert violations == 0, f"{violations} returns refund more than the line's net revenue"


def test_quantities_are_positive(analytics) -> None:
    """Sold and returned quantities must be strictly positive."""
    bad_sales = scalar(analytics, "SELECT COUNT(*) FROM fact_sales WHERE quantity <= 0")
    bad_returns = scalar(
        analytics, "SELECT COUNT(*) FROM fact_returns WHERE quantity_returned <= 0"
    )
    assert bad_sales == 0 and bad_returns == 0
