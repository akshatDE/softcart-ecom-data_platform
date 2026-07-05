"""Programmatic data-quality checks used by the Airflow pipeline.

The Pytest suite under ``tests/`` covers the same five dimensions
(accuracy, completeness, consistency, timeliness, uniqueness) for
command-line runs; this service provides the in-pipeline gate that fails
the DAG before bad data reaches the dashboard.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.main.databases.duckdb_connector import DuckDBConnector
from src.main.databases.postgres_connector import PostgresConnector
from src.main.utility.config_loader import get_config
from src.main.utility.exceptions import DataQualityError
from src.main.utility.logger import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True)
class CheckResult:
    """Outcome of one data-quality check."""

    dimension: str
    name: str
    passed: bool
    detail: str


class DataQualityService:
    """Runs SQL-based quality checks against staging and analytics layers."""

    def __init__(self) -> None:
        self._config = get_config()

    # --------------------------------------------------------------- staging

    def check_staging(self) -> list[CheckResult]:
        """Quality gate after the staging load."""
        postgres = PostgresConnector()
        schema = postgres.staging_schema
        results: list[CheckResult] = []

        def scalar(sql: str) -> float:
            return float(postgres.read_sql(sql).iloc[0, 0])

        results.append(self._check(
            "completeness", "customer emails present",
            scalar(f"SELECT COUNT(*) FROM {schema}.stg_customers "
                   "WHERE email IS NULL OR email = ''") == 0,
            "null/empty emails in stg_customers",
        ))
        results.append(self._check(
            "completeness", "order dates present",
            scalar(f"SELECT COUNT(*) FROM {schema}.stg_orders WHERE order_date IS NULL") == 0,
            "null order_date in stg_orders",
        ))
        results.append(self._check(
            "uniqueness", "order ids unique",
            scalar(f"SELECT COUNT(*) - COUNT(DISTINCT order_id) FROM {schema}.stg_orders") == 0,
            "duplicate order_id in stg_orders",
        ))
        results.append(self._check(
            "consistency", "order items reference orders",
            scalar(f"SELECT COUNT(*) FROM {schema}.stg_order_items i "
                   f"LEFT JOIN {schema}.stg_orders o USING (order_id) "
                   "WHERE o.order_id IS NULL") == 0,
            "orphan order_items rows",
        ))
        results.append(self._check(
            "consistency", "order items reference products",
            scalar(f"SELECT COUNT(*) FROM {schema}.stg_order_items i "
                   f"LEFT JOIN {schema}.stg_products p USING (product_id) "
                   "WHERE p.product_id IS NULL") == 0,
            "order_items with unknown product_id",
        ))
        results.append(self._check(
            "accuracy", "order totals match line sums",
            scalar(
                f"SELECT COUNT(*) FROM {schema}.stg_orders o JOIN ("
                f"  SELECT order_id, SUM(line_total) AS line_sum "
                f"  FROM {schema}.stg_order_items GROUP BY order_id"
                ") s USING (order_id) "
                "WHERE ABS(o.total_amount - s.line_sum) > 0.01"
            ) == 0,
            "orders whose total_amount deviates from item sum",
        ))
        return self._finalize("staging", results)

    # ------------------------------------------------------------- analytics

    def check_analytics(self) -> list[CheckResult]:
        """Quality gate after the DuckDB transformation."""
        duck = DuckDBConnector(read_only=True)
        results: list[CheckResult] = []
        try:
            def scalar(sql: str) -> float:
                return float(duck.query_df(sql).iloc[0, 0])

            results.append(self._check(
                "completeness", "fact_sales keys not null",
                scalar("SELECT COUNT(*) FROM fact_sales WHERE customer_key IS NULL "
                       "OR product_key IS NULL OR order_date_key IS NULL") == 0,
                "null foreign keys in fact_sales",
            ))
            results.append(self._check(
                "uniqueness", "fact_sales grain unique",
                scalar("SELECT COUNT(*) - COUNT(DISTINCT order_item_id) FROM fact_sales") == 0,
                "duplicate order_item_id in fact_sales (rerun duplication)",
            ))
            results.append(self._check(
                "consistency", "fact_sales products exist in dim_product",
                scalar("SELECT COUNT(*) FROM fact_sales f LEFT JOIN dim_product p "
                       "USING (product_key) WHERE p.product_key IS NULL") == 0,
                "fact_sales rows with dangling product_key",
            ))
            results.append(self._check(
                "accuracy", "net revenue = gross - discount",
                scalar("SELECT COUNT(*) FROM fact_sales "
                       "WHERE ABS(gross_revenue - discount_amount - net_revenue) > 0.01") == 0,
                "net_revenue arithmetic mismatch",
            ))
            max_staleness = self._config.get_int("pipeline", "max_staleness_days", 400)
            results.append(self._check(
                "timeliness", "latest order date is recent",
                scalar("SELECT COALESCE(date_diff('day', MAX(d.full_date), current_date), 99999) "
                       "FROM fact_sales f JOIN dim_date d ON f.order_date_key = d.date_key")
                <= max_staleness,
                f"latest order older than {max_staleness} days",
            ))
        finally:
            duck.close()
        return self._finalize("analytics", results)

    # --------------------------------------------------------------- helpers

    @staticmethod
    def _check(dimension: str, name: str, passed: bool, failure_detail: str) -> CheckResult:
        """Build a result and log its outcome."""
        detail = "ok" if passed else failure_detail
        if passed:
            logger.info("DQ pass [{}] {}", dimension, name)
        else:
            logger.error("DQ FAIL [{}] {} — {}", dimension, name, failure_detail)
        return CheckResult(dimension, name, passed, detail)

    @staticmethod
    def _finalize(layer: str, results: list[CheckResult]) -> list[CheckResult]:
        """Raise if any check failed so orchestration halts the pipeline."""
        failures = [r for r in results if not r.passed]
        if failures:
            summary = "; ".join(f"[{r.dimension}] {r.name}: {r.detail}" for r in failures)
            raise DataQualityError(f"{layer} data-quality gate failed: {summary}")
        logger.info("{} data-quality gate passed ({} checks)", layer, len(results))
        return results


def run_staging_checks() -> int:
    """Airflow-friendly entry point (staging gate)."""
    return len(DataQualityService().check_staging())


def run_analytics_checks() -> int:
    """Airflow-friendly entry point (analytics gate)."""
    return len(DataQualityService().check_analytics())
