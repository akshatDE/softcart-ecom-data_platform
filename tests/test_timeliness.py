"""Timeliness checks: data is available and fresh when expected."""

from __future__ import annotations

from datetime import datetime, timedelta

import pandas as pd

from src.main.utility.config_loader import get_config
from tests.conftest import scalar


def test_staging_loaded_recently(staging) -> None:
    """The last staging load must be recent (audit trail freshness)."""
    schema = staging.staging_schema
    frame = staging.read_sql(f"SELECT MAX(loaded_at) AS last_load FROM {schema}.etl_audit")
    last_load = pd.to_datetime(frame["last_load"].iloc[0])
    assert pd.notna(last_load), "etl_audit is empty — staging never recorded a load"
    age = datetime.now() - last_load.to_pydatetime()
    assert age < timedelta(days=2), f"staging last loaded {age} ago"


def test_every_staging_table_has_an_audit_entry(staging) -> None:
    """Each core staging table must appear in the audit trail."""
    schema = staging.staging_schema
    audited = set(
        staging.read_sql(f"SELECT DISTINCT table_name FROM {schema}.etl_audit")["table_name"]
    )
    expected = {"stg_orders", "stg_order_items", "stg_customers", "stg_products"}
    missing = expected - audited
    assert not missing, f"no audit entries for: {sorted(missing)}"


def test_latest_order_date_exists_in_analytics(analytics) -> None:
    """The analytics layer must contain a plausible latest order date."""
    latest_key = scalar(analytics, "SELECT MAX(order_date_key) FROM fact_sales")
    assert latest_key > 0, "fact_sales has no order dates"
    staleness_limit = get_config().get_int("pipeline", "max_staleness_days", 400)
    days_stale = scalar(
        analytics,
        "SELECT date_diff('day', MAX(d.full_date), current_date) "
        "FROM fact_sales f JOIN dim_date d ON f.order_date_key = d.date_key",
    )
    assert days_stale <= staleness_limit, (
        f"latest order is {days_stale:.0f} days old (limit {staleness_limit})"
    )


def test_pipeline_run_timestamp_is_recent(analytics) -> None:
    """The analytics build itself must have completed recently."""
    frame = analytics.query_df(
        "SELECT MAX(completed_at) AS last_run FROM pipeline_runs "
        "WHERE step_name = 'build_analytics'"
    )
    last_run = pd.to_datetime(frame["last_run"].iloc[0])
    assert pd.notna(last_run), "pipeline_runs has no build_analytics entry"
    age = datetime.now() - last_run.to_pydatetime()
    assert age < timedelta(days=2), f"analytics last rebuilt {age} ago"
