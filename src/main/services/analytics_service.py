"""Read-only analytics queries over the DuckDB star schema.

Every method returns ``list[dict]`` so FastAPI can serialize responses
directly, and accepts an optional :class:`QueryFilters` so the dashboard can
slice the whole page by date range, parent category, and sales channel.

All filter values are bound as positional parameters — never interpolated —
and the WHERE fragments themselves are built only from fixed templates.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any

import pandas as pd

from src.main.databases.duckdb_connector import DuckDBConnector
from src.main.utility.logger import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True)
class QueryFilters:
    """Global dashboard filters applied to fact-table queries.

    ``categories`` filters on ``dim_category.parent_category``;
    ``channels`` on ``dim_channel.channel_name``.
    """

    start_date: date | None = None
    end_date: date | None = None
    categories: tuple[str, ...] = field(default_factory=tuple)
    channels: tuple[str, ...] = field(default_factory=tuple)

    @staticmethod
    def _date_key(value: date) -> int:
        """Convert a date to the yyyymmdd surrogate used by dim_date."""
        return value.year * 10_000 + value.month * 100 + value.day

    def sales_where(self) -> tuple[str, list[Any]]:
        """WHERE fragment + params for queries over ``fact_sales f``.

        The fragment starts with `` AND `` so callers embed it after a
        ``WHERE 1=1`` anchor: ``WHERE 1=1{where}``.
        """
        clauses: list[str] = []
        params: list[Any] = []
        if self.start_date is not None:
            clauses.append("f.order_date_key >= ?")
            params.append(self._date_key(self.start_date))
        if self.end_date is not None:
            clauses.append("f.order_date_key <= ?")
            params.append(self._date_key(self.end_date))
        if self.categories:
            placeholders = ", ".join("?" for _ in self.categories)
            clauses.append(
                "f.category_key IN (SELECT category_key FROM dim_category "
                f"WHERE parent_category IN ({placeholders}))"
            )
            params.extend(self.categories)
        if self.channels:
            placeholders = ", ".join("?" for _ in self.channels)
            clauses.append(
                "f.channel_key IN (SELECT channel_key FROM dim_channel "
                f"WHERE channel_name IN ({placeholders}))"
            )
            params.extend(self.channels)
        fragment = "".join(f" AND {clause}" for clause in clauses)
        return fragment, params

    def returns_where(self) -> tuple[str, list[Any]]:
        """WHERE fragment + params for queries over ``fact_returns r``."""
        clauses: list[str] = []
        params: list[Any] = []
        if self.start_date is not None:
            clauses.append("r.return_date_key >= ?")
            params.append(self._date_key(self.start_date))
        if self.end_date is not None:
            clauses.append("r.return_date_key <= ?")
            params.append(self._date_key(self.end_date))
        if self.categories:
            placeholders = ", ".join("?" for _ in self.categories)
            clauses.append(
                "r.product_key IN (SELECT p.product_key FROM dim_product p "
                "JOIN dim_category c USING (category_key) "
                f"WHERE c.parent_category IN ({placeholders}))"
            )
            params.extend(self.categories)
        if self.channels:
            placeholders = ", ".join("?" for _ in self.channels)
            clauses.append(
                "r.channel_key IN (SELECT channel_key FROM dim_channel "
                f"WHERE channel_name IN ({placeholders}))"
            )
            params.extend(self.channels)
        fragment = "".join(f" AND {clause}" for clause in clauses)
        return fragment, params


_NO_FILTERS = QueryFilters()


class AnalyticsService:
    """Serves aggregated analytics for the API and dashboard."""

    def __init__(self, connector: DuckDBConnector | None = None) -> None:
        self._duck = connector or DuckDBConnector(read_only=True)

    def _rows(self, sql: str, params: list[Any] | None = None) -> list[dict[str, Any]]:
        """Run a query and return JSON-safe records."""
        frame = self._duck.query_df(sql, params)
        for column in frame.columns:
            if pd.api.types.is_datetime64_any_dtype(frame[column]):
                frame[column] = frame[column].dt.strftime("%Y-%m-%d")
        return frame.to_dict(orient="records")

    def filter_options(self) -> dict[str, Any]:
        """Available filter values for the dashboard sidebar."""
        dates = self._duck.query_df(
            "SELECT MIN(d.full_date) AS min_date, MAX(d.full_date) AS max_date "
            "FROM fact_sales f JOIN dim_date d ON f.order_date_key = d.date_key"
        )
        categories = self._duck.query_df(
            "SELECT DISTINCT parent_category FROM dim_category ORDER BY 1"
        )
        channels = self._duck.query_df(
            "SELECT channel_name FROM dim_channel ORDER BY channel_name"
        )
        return {
            "min_date": str(pd.to_datetime(dates["min_date"].iloc[0]).date()),
            "max_date": str(pd.to_datetime(dates["max_date"].iloc[0]).date()),
            "categories": categories["parent_category"].tolist(),
            "channels": channels["channel_name"].tolist(),
        }

    def kpi_summary(self, filters: QueryFilters = _NO_FILTERS) -> list[dict[str, Any]]:
        """Headline KPIs for the dashboard header."""
        where, params = filters.sales_where()
        returns_where, returns_params = filters.returns_where()
        return self._rows(
            f"""
            SELECT
                COUNT(DISTINCT f.order_id)              AS orders,
                COUNT(DISTINCT f.customer_key)          AS customers,
                ROUND(SUM(f.gross_revenue), 2)          AS gross_revenue,
                ROUND(SUM(f.discount_amount), 2)        AS total_discounts,
                ROUND(SUM(f.net_revenue), 2)            AS net_revenue,
                SUM(f.quantity)                         AS units_sold,
                (SELECT ROUND(COALESCE(SUM(r.refund_amount), 0), 2)
                 FROM fact_returns r WHERE 1=1{returns_where}) AS refunds
            FROM fact_sales f
            WHERE 1=1{where}
            """,
            returns_params + params,
        )

    def revenue_by_category(self, filters: QueryFilters = _NO_FILTERS) -> list[dict[str, Any]]:
        """Gross/net revenue and quantity by category."""
        where, params = filters.sales_where()
        return self._rows(
            f"""
            SELECT c.parent_category, c.category_name,
                   ROUND(SUM(f.gross_revenue), 2) AS gross_revenue,
                   ROUND(SUM(f.discount_amount), 2) AS discounts,
                   ROUND(SUM(f.net_revenue), 2) AS net_revenue,
                   SUM(f.quantity) AS quantity_sold
            FROM fact_sales f
            JOIN dim_category c USING (category_key)
            WHERE 1=1{where}
            GROUP BY 1, 2
            ORDER BY net_revenue DESC
            """,
            params,
        )

    def revenue_by_product(
        self, limit: int = 20, filters: QueryFilters = _NO_FILTERS
    ) -> list[dict[str, Any]]:
        """Top products by net revenue."""
        where, params = filters.sales_where()
        return self._rows(
            f"""
            SELECT p.product_name, p.brand, p.category_name,
                   ROUND(SUM(f.net_revenue), 2) AS net_revenue,
                   ROUND(SUM(f.gross_revenue), 2) AS gross_revenue,
                   SUM(f.quantity) AS quantity_sold
            FROM fact_sales f
            JOIN dim_product p USING (product_key)
            WHERE 1=1{where}
            GROUP BY 1, 2, 3
            ORDER BY net_revenue DESC
            LIMIT ?
            """,
            params + [max(1, min(limit, 200))],
        )

    def sales_trend(
        self, granularity: str = "month", filters: QueryFilters = _NO_FILTERS
    ) -> list[dict[str, Any]]:
        """Net revenue and quantity over time, by month or day."""
        bucket = "d.full_date" if granularity == "day" else \
            "CAST(date_trunc('month', d.full_date) AS DATE)"
        where, params = filters.sales_where()
        return self._rows(
            f"""
            SELECT {bucket} AS period,
                   ROUND(SUM(f.net_revenue), 2) AS net_revenue,
                   ROUND(SUM(f.gross_revenue), 2) AS gross_revenue,
                   SUM(f.quantity) AS quantity_sold,
                   COUNT(DISTINCT f.order_id) AS orders
            FROM fact_sales f
            JOIN dim_date d ON f.order_date_key = d.date_key
            WHERE 1=1{where}
            GROUP BY 1
            ORDER BY 1
            """,
            params,
        )

    def category_trend(self, filters: QueryFilters = _NO_FILTERS) -> list[dict[str, Any]]:
        """Monthly net revenue per parent category (growth/decline view)."""
        where, params = filters.sales_where()
        return self._rows(
            f"""
            SELECT CAST(date_trunc('month', d.full_date) AS DATE) AS period,
                   c.parent_category,
                   ROUND(SUM(f.net_revenue), 2) AS net_revenue
            FROM fact_sales f
            JOIN dim_date d ON f.order_date_key = d.date_key
            JOIN dim_category c USING (category_key)
            WHERE 1=1{where}
            GROUP BY 1, 2
            ORDER BY 1, 2
            """,
            params,
        )

    def customer_segments(self, filters: QueryFilters = _NO_FILTERS) -> list[dict[str, Any]]:
        """Spending-tier segmentation of customers."""
        where, params = filters.sales_where()
        return self._rows(
            f"""
            WITH spend AS (
                SELECT f.customer_key, SUM(f.net_revenue) AS total_spend
                FROM fact_sales f WHERE 1=1{where} GROUP BY 1
            )
            SELECT CASE
                       WHEN total_spend >= 5000 THEN 'VIP (5k+)'
                       WHEN total_spend >= 1000 THEN 'High (1k-5k)'
                       WHEN total_spend >= 250 THEN 'Mid (250-1k)'
                       ELSE 'Low (<250)'
                   END AS spending_tier,
                   COUNT(*) AS customers,
                   ROUND(SUM(total_spend), 2) AS net_revenue
            FROM spend
            GROUP BY 1
            ORDER BY net_revenue DESC
            """,
            params,
        )

    def repeat_vs_one_time(self, filters: QueryFilters = _NO_FILTERS) -> list[dict[str, Any]]:
        """Repeat versus one-time buyers, with their revenue share."""
        where, params = filters.sales_where()
        return self._rows(
            f"""
            WITH per_customer AS (
                SELECT f.customer_key,
                       COUNT(DISTINCT f.order_id) AS orders,
                       SUM(f.net_revenue) AS net_revenue
                FROM fact_sales f WHERE 1=1{where} GROUP BY 1
            )
            SELECT CASE WHEN orders > 1 THEN 'Repeat buyers' ELSE 'One-time buyers' END
                       AS buyer_type,
                   COUNT(*) AS customers,
                   ROUND(SUM(net_revenue), 2) AS net_revenue,
                   ROUND(AVG(orders), 2) AS avg_orders
            FROM per_customer
            GROUP BY 1
            ORDER BY buyer_type
            """,
            params,
        )

    def top_customers(
        self, limit: int = 20, filters: QueryFilters = _NO_FILTERS
    ) -> list[dict[str, Any]]:
        """Highest lifetime-value customers."""
        where, params = filters.sales_where()
        return self._rows(
            f"""
            SELECT c.full_name, c.country,
                   COUNT(DISTINCT f.order_id) AS orders,
                   ROUND(SUM(f.net_revenue), 2) AS lifetime_value
            FROM fact_sales f
            JOIN dim_customer c USING (customer_key)
            WHERE 1=1{where}
            GROUP BY 1, 2
            ORDER BY lifetime_value DESC
            LIMIT ?
            """,
            params + [max(1, min(limit, 200))],
        )

    def revenue_concentration(
        self, entity: str = "product", filters: QueryFilters = _NO_FILTERS
    ) -> list[dict[str, Any]]:
        """Pareto curve: cumulative revenue share by ranked entity."""
        key = "customer_key" if entity == "customer" else "product_key"
        where, params = filters.sales_where()
        return self._rows(
            f"""
            WITH ranked AS (
                SELECT f.{key} AS entity_key, SUM(f.net_revenue) AS net_revenue
                FROM fact_sales f WHERE 1=1{where} GROUP BY 1
            ),
            curve AS (
                SELECT entity_key, net_revenue,
                       ROW_NUMBER() OVER (ORDER BY net_revenue DESC) AS rank,
                       SUM(net_revenue) OVER (ORDER BY net_revenue DESC
                           ROWS UNBOUNDED PRECEDING) AS cumulative_revenue,
                       SUM(net_revenue) OVER () AS total_revenue,
                       COUNT(*) OVER () AS total_entities
                FROM ranked
            )
            SELECT rank,
                   ROUND(100.0 * rank / total_entities, 2) AS entity_pct,
                   ROUND(100.0 * cumulative_revenue / total_revenue, 2)
                       AS cumulative_revenue_pct
            FROM curve
            ORDER BY rank
            """,
            params,
        )

    def clv_distribution(self, filters: QueryFilters = _NO_FILTERS) -> list[dict[str, Any]]:
        """Customer lifetime value per customer (for histogramming)."""
        where, params = filters.sales_where()
        return self._rows(
            f"""
            SELECT f.customer_key, ROUND(SUM(f.net_revenue), 2) AS lifetime_value
            FROM fact_sales f WHERE 1=1{where}
            GROUP BY 1 ORDER BY lifetime_value DESC
            """,
            params,
        )

    def channel_performance(self, filters: QueryFilters = _NO_FILTERS) -> list[dict[str, Any]]:
        """Revenue, quantity, and orders per sales channel."""
        where, params = filters.sales_where()
        return self._rows(
            f"""
            SELECT ch.channel_name, ch.channel_type,
                   ROUND(SUM(f.net_revenue), 2) AS net_revenue,
                   SUM(f.quantity) AS quantity_sold,
                   COUNT(DISTINCT f.order_id) AS orders
            FROM fact_sales f
            JOIN dim_channel ch USING (channel_key)
            WHERE 1=1{where}
            GROUP BY 1, 2
            ORDER BY net_revenue DESC
            """,
            params,
        )

    def channel_product_matrix(
        self, limit: int = 5, filters: QueryFilters = _NO_FILTERS
    ) -> list[dict[str, Any]]:
        """Best-selling products per channel (top ``limit`` each)."""
        where, params = filters.sales_where()
        return self._rows(
            f"""
            WITH ranked AS (
                SELECT ch.channel_name, p.product_name,
                       SUM(f.net_revenue) AS net_revenue,
                       SUM(f.quantity) AS quantity_sold,
                       ROW_NUMBER() OVER (PARTITION BY ch.channel_name
                                          ORDER BY SUM(f.net_revenue) DESC) AS rank
                FROM fact_sales f
                JOIN dim_channel ch USING (channel_key)
                JOIN dim_product p USING (product_key)
                WHERE 1=1{where}
                GROUP BY 1, 2
            )
            SELECT channel_name, product_name,
                   ROUND(net_revenue, 2) AS net_revenue, quantity_sold, rank
            FROM ranked WHERE rank <= ?
            ORDER BY channel_name, rank
            """,
            params + [max(1, min(limit, 20))],
        )

    def promotion_performance(self, filters: QueryFilters = _NO_FILTERS) -> list[dict[str, Any]]:
        """Volume versus discount cost per promotion (incl. no-promo baseline)."""
        where, params = filters.sales_where()
        return self._rows(
            f"""
            SELECT pr.promotion_code, pr.discount_type, pr.discount_value,
                   COUNT(DISTINCT f.order_id) AS orders,
                   SUM(f.quantity) AS quantity_sold,
                   ROUND(SUM(f.gross_revenue), 2) AS gross_revenue,
                   ROUND(SUM(f.discount_amount), 2) AS discounts,
                   ROUND(SUM(f.net_revenue), 2) AS net_revenue,
                   ROUND(AVG(f.quantity), 2) AS avg_items_per_line
            FROM fact_sales f
            JOIN dim_promotion pr USING (promotion_key)
            WHERE 1=1{where}
            GROUP BY 1, 2, 3
            ORDER BY net_revenue DESC
            """,
            params,
        )

    def last_refresh(self) -> list[dict[str, Any]]:
        """Most recent pipeline run timestamp (dashboard footer)."""
        return self._rows(
            "SELECT step_name, completed_at FROM pipeline_runs "
            "ORDER BY completed_at DESC LIMIT 1"
        )

    def close(self) -> None:
        """Release the DuckDB connection."""
        self._duck.close()
