"""Consistency checks: data agrees across systems and tables."""

from __future__ import annotations

from tests.conftest import scalar


def test_order_items_reference_existing_orders(staging) -> None:
    """No orphan order items in staging."""
    schema = staging.staging_schema
    orphans = scalar(
        staging,
        f"SELECT COUNT(*) FROM {schema}.stg_order_items i "
        f"LEFT JOIN {schema}.stg_orders o USING (order_id) "
        "WHERE o.order_id IS NULL",
    )
    assert orphans == 0, f"{orphans} order items referencing missing orders"


def test_order_products_exist_in_catalog(staging) -> None:
    """Product ids sold in MySQL must exist in the MongoDB-sourced catalog."""
    schema = staging.staging_schema
    unknown = scalar(
        staging,
        f"SELECT COUNT(*) FROM {schema}.stg_order_items i "
        f"LEFT JOIN {schema}.stg_products p USING (product_id) "
        "WHERE p.product_id IS NULL",
    )
    assert unknown == 0, f"{unknown} order items with product ids missing from the catalog"


def test_fact_sales_keys_exist_in_dimensions(analytics) -> None:
    """Every fact_sales key must resolve to a dimension row."""
    for dimension, key in (
        ("dim_customer", "customer_key"),
        ("dim_product", "product_key"),
        ("dim_category", "category_key"),
        ("dim_channel", "channel_key"),
        ("dim_promotion", "promotion_key"),
        ("dim_date", "order_date_key"),
    ):
        join_key = "date_key" if dimension == "dim_date" else key
        dangling = scalar(
            analytics,
            f"SELECT COUNT(*) FROM fact_sales f LEFT JOIN {dimension} d "
            f"ON f.{key} = d.{join_key} WHERE d.{join_key} IS NULL",
        )
        assert dangling == 0, f"{dangling} fact_sales rows dangling against {dimension}"


def test_category_names_are_standardized(analytics) -> None:
    """Category names must be trimmed and consistently cased."""
    frame = analytics.query_df("SELECT category_name FROM dim_category")
    names = frame["category_name"].tolist()
    assert all(name == name.strip() for name in names), "untrimmed category names"
    lowered = [name.lower() for name in names]
    assert len(lowered) == len(set(lowered)), "categories differing only by case"


def test_no_conflicting_duplicate_customers(analytics) -> None:
    """The same customer email must not map to multiple customer ids."""
    conflicts = scalar(
        analytics,
        "SELECT COUNT(*) FROM (SELECT email FROM dim_customer "
        "GROUP BY email HAVING COUNT(DISTINCT customer_id) > 1)",
    )
    assert conflicts == 0, f"{conflicts} emails shared by different customer ids"


def test_staging_and_analytics_row_counts_agree(staging, analytics) -> None:
    """fact_sales must carry exactly the staged order items."""
    schema = staging.staging_schema
    staged = scalar(staging, f"SELECT COUNT(*) FROM {schema}.stg_order_items")
    facts = scalar(analytics, "SELECT COUNT(*) FROM fact_sales")
    assert staged == facts, f"stg_order_items={staged} but fact_sales={facts}"
