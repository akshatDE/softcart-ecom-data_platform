"""Completeness checks: required fields are populated."""

from __future__ import annotations

from tests.conftest import scalar


def test_customer_emails_not_null(staging) -> None:
    """Customer email is mandatory."""
    schema = staging.staging_schema
    missing = scalar(
        staging,
        f"SELECT COUNT(*) FROM {schema}.stg_customers "
        "WHERE email IS NULL OR email = ''",
    )
    assert missing == 0, f"{missing} customers without an email"


def test_order_dates_not_null(staging) -> None:
    """Every order must carry an order date."""
    schema = staging.staging_schema
    missing = scalar(
        staging, f"SELECT COUNT(*) FROM {schema}.stg_orders WHERE order_date IS NULL"
    )
    assert missing == 0, f"{missing} orders without an order_date"


def test_product_categories_not_null(staging) -> None:
    """Every product must be categorized."""
    schema = staging.staging_schema
    missing = scalar(
        staging,
        f"SELECT COUNT(*) FROM {schema}.stg_products "
        "WHERE category_name IS NULL OR category_name = '' "
        "OR parent_category IS NULL OR parent_category = ''",
    )
    assert missing == 0, f"{missing} products without a category"


def test_fact_sales_foreign_keys_not_null(analytics) -> None:
    """All surrogate keys on fact_sales must be populated."""
    missing = scalar(
        analytics,
        """
        SELECT COUNT(*) FROM fact_sales
        WHERE order_date_key IS NULL OR customer_key IS NULL
           OR product_key IS NULL OR category_key IS NULL
           OR channel_key IS NULL OR promotion_key IS NULL
           OR payment_method_key IS NULL
        """,
    )
    assert missing == 0, f"{missing} fact_sales rows with null foreign keys"


def test_fact_returns_foreign_keys_not_null(analytics) -> None:
    """All surrogate keys on fact_returns must be populated."""
    missing = scalar(
        analytics,
        "SELECT COUNT(*) FROM fact_returns "
        "WHERE return_date_key IS NULL OR customer_key IS NULL "
        "OR product_key IS NULL OR channel_key IS NULL",
    )
    assert missing == 0, f"{missing} fact_returns rows with null foreign keys"
