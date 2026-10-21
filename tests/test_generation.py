"""Unit tests for the shared generation core (no databases needed).

Every platform target (local files, Snowflake, Databricks) relies on these
guarantees, so they must hold before any platform-specific writer runs.
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from src.main.generation import TABLES, GenerationSettings, generate_dataset

SMALL = GenerationSettings(num_customers=50, num_products=20, num_orders=300, seed=7)


def _without_timestamps(products: list[dict]) -> list[dict]:
    """Drop ``metadata`` (holds the wall-clock ``created_at``) before comparing."""
    return [{k: v for k, v in doc.items() if k != "metadata"} for doc in products]


@pytest.fixture(scope="module")
def dataset():
    return generate_dataset(SMALL)


def test_same_seed_produces_identical_data(dataset):
    again = generate_dataset(SMALL)
    for name in TABLES:
        assert dataset.frames[name].equals(again.frames[name]), name
    assert _without_timestamps(dataset.products) == _without_timestamps(again.products)


def test_different_seed_produces_different_data(dataset):
    other = generate_dataset(replace(SMALL, seed=SMALL.seed + 1))
    assert not dataset.frames["customers"].equals(other.frames["customers"])


def test_all_tables_present_and_sized(dataset):
    assert tuple(dataset.frames) == TABLES
    assert dataset.counts["customers"] == SMALL.num_customers
    assert dataset.counts["products"] == SMALL.num_products
    assert dataset.counts["orders"] == SMALL.num_orders


def test_money_reconciles(dataset):
    orders = dataset.frames["orders"].set_index("order_id")
    item_totals = dataset.frames["order_items"].groupby("order_id")["line_total"].sum()
    payments = dataset.frames["payments"].set_index("order_id")["amount"]
    assert (orders["total_amount"] - item_totals).abs().max() < 0.01
    assert (orders["total_amount"] - payments).abs().max() < 0.01


def test_foreign_keys_resolve(dataset):
    f = dataset.frames
    product_ids = {doc["product_id"] for doc in dataset.products}
    assert f["orders"]["customer_id"].isin(f["customers"]["customer_id"]).all()
    assert f["orders"]["channel_id"].isin(f["sales_channels"]["channel_id"]).all()
    assert f["order_items"]["product_id"].isin(product_ids).all()
    assert f["returns"]["order_item_id"].isin(f["order_items"]["order_item_id"]).all()


def test_invalid_window_rejected():
    from src.main.utility.exceptions import DataGenerationError

    with pytest.raises(DataGenerationError):
        generate_dataset(replace(SMALL, start_date=SMALL.end_date))
