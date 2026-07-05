"""Shared fixtures for the SoftCart data-quality test suite.

Database-backed tests skip gracefully when the corresponding layer is not
available (e.g. the pipeline has not run yet), so ``pytest`` is always safe
to invoke. The NLP-SQL security tests are pure unit tests and always run.
"""

from __future__ import annotations

import pandas as pd
import pytest

from src.main.utility.exceptions import SoftCartError


@pytest.fixture(scope="session")
def staging():
    """Connector to the PostgreSQL staging warehouse (or skip)."""
    from src.main.databases.postgres_connector import PostgresConnector

    connector = PostgresConnector()
    try:
        connector.test_connection()
        # An empty staging layer means the pipeline never ran.
        count = connector.read_sql(
            f"SELECT COUNT(*) AS n FROM {connector.staging_schema}.stg_orders"
        )["n"].iloc[0]
    except SoftCartError as exc:
        pytest.skip(f"PostgreSQL staging not available: {exc}")
    if count == 0:
        pytest.skip("Staging is empty — run the pipeline before the DQ suite.")
    yield connector
    connector.dispose()


@pytest.fixture(scope="session")
def analytics():
    """Read-only connector to the DuckDB analytics layer (or skip)."""
    from src.main.databases.duckdb_connector import DuckDBConnector

    connector = DuckDBConnector(read_only=True)
    if not connector.database_path.is_file():
        pytest.skip(f"DuckDB database not found at {connector.database_path}")
    try:
        count = connector.query_df("SELECT COUNT(*) AS n FROM fact_sales")["n"].iloc[0]
    except SoftCartError as exc:
        pytest.skip(f"DuckDB analytics not queryable: {exc}")
    if count == 0:
        pytest.skip("fact_sales is empty — run the transformation first.")
    yield connector
    connector.close()


def scalar(connector, sql: str) -> float:
    """Return the first cell of a query result as a float."""
    frame: pd.DataFrame = (
        connector.query_df(sql) if hasattr(connector, "query_df") else connector.read_sql(sql)
    )
    return float(frame.iloc[0, 0])
