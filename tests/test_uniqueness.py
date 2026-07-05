"""Uniqueness checks: no unintended duplicates."""

from __future__ import annotations

from tests.conftest import scalar


def _duplicates(connector, table: str, key: str) -> float:
    """Number of duplicated key values in a table."""
    return scalar(
        connector,
        f"SELECT COUNT(*) - COUNT(DISTINCT {key}) FROM {table}",
    )


def test_staging_primary_keys_unique(staging) -> None:
    """Business keys must be unique in every staging table."""
    schema = staging.staging_schema
    for table, key in (
        ("stg_customers", "customer_id"),
        ("stg_orders", "order_id"),
        ("stg_order_items", "order_item_id"),
        ("stg_payments", "payment_id"),
        ("stg_returns", "return_id"),
        ("stg_products", "product_id"),
        ("stg_promotions", "promotion_id"),
    ):
        dupes = _duplicates(staging, f"{schema}.{table}", key)
        assert dupes == 0, f"{dupes} duplicate {key} values in {table}"


def test_customer_emails_unique(staging) -> None:
    """Emails are a natural key and must not repeat."""
    schema = staging.staging_schema
    dupes = _duplicates(staging, f"{schema}.stg_customers", "email")
    assert dupes == 0, f"{dupes} duplicated customer emails"


def test_dimension_surrogate_keys_unique(analytics) -> None:
    """Surrogate keys must be unique in every dimension."""
    for table, key in (
        ("dim_customer", "customer_key"),
        ("dim_product", "product_key"),
        ("dim_category", "category_key"),
        ("dim_date", "date_key"),
        ("dim_channel", "channel_key"),
        ("dim_promotion", "promotion_key"),
        ("dim_payment_method", "payment_method_key"),
    ):
        dupes = _duplicates(analytics, table, key)
        assert dupes == 0, f"{dupes} duplicate {key} values in {table}"


def test_fact_records_not_duplicated_after_reruns(analytics) -> None:
    """Rebuilds must not double-load facts (order_item_id is the grain)."""
    sales_dupes = _duplicates(analytics, "fact_sales", "order_item_id")
    assert sales_dupes == 0, f"{sales_dupes} duplicated order items in fact_sales"
    return_dupes = _duplicates(analytics, "fact_returns", "return_id")
    assert return_dupes == 0, f"{return_dupes} duplicated returns in fact_returns"
