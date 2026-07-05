"""Transformation of staged data into the DuckDB Kimball star schema.

Reads the ``staging.stg_*`` tables from PostgreSQL, conforms them into
dimensions with integer surrogate keys, and builds the order-item-grain
``fact_sales`` and ``fact_returns`` tables in DuckDB. The whole analytics
layer is rebuilt on each run (small data volumes make full refresh the
simplest idempotent strategy).
"""

from __future__ import annotations

import json
import time
from datetime import datetime

import pandas as pd

from src.main.databases.duckdb_connector import DuckDBConnector
from src.main.databases.postgres_connector import PostgresConnector
from src.main.utility.exceptions import ETLError
from src.main.utility.logger import get_logger

logger = get_logger(__name__)

_NO_PROMOTION_KEY = 1  # reserved surrogate for orders without a promotion


class TransformationService:
    """Builds the analytics star schema from staged data."""

    def __init__(self) -> None:
        self._postgres = PostgresConnector()
        self._schema = self._postgres.staging_schema

    def _staged(self, table: str) -> pd.DataFrame:
        """Read one staging table."""
        return self._postgres.read_table(table, schema=self._schema)

    def build_analytics(self) -> dict[str, int]:
        """Rebuild every dimension and fact table; returns row counts."""
        logger.info("Analytics transformation started")
        stg = {
            name: self._staged(f"stg_{name}")
            for name in (
                "customers", "products", "sales_channels", "promotions",
                "orders", "order_items", "payments", "returns",
            )
        }
        if stg["orders"].empty or stg["order_items"].empty:
            raise ETLError("Staging is empty — run the staging step first.")

        dims = self._build_dimensions(stg)
        fact_sales = self._build_fact_sales(stg, dims)
        fact_returns = self._build_fact_returns(stg, dims, fact_sales)

        counts = self._write_to_duckdb(dims, fact_sales, fact_returns)
        logger.info("Analytics transformation finished: {}", counts)
        return counts

    # ------------------------------------------------------------------ dims

    def _build_dimensions(self, stg: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
        """Conform staging data into the dimension tables."""
        customers = stg["customers"].copy()
        customers["customer_key"] = range(1, len(customers) + 1)
        customers["full_name"] = customers["first_name"] + " " + customers["last_name"]
        dim_customer = customers[
            ["customer_key", "customer_id", "full_name", "email",
             "city", "state", "country", "signup_date"]
        ]

        categories = (
            stg["products"][["category_name", "parent_category"]]
            .drop_duplicates()
            .sort_values(["parent_category", "category_name"])
            .reset_index(drop=True)
        )
        categories["category_key"] = range(1, len(categories) + 1)
        dim_category = categories[["category_key", "category_name", "parent_category"]]

        products = stg["products"].merge(categories, on=["category_name", "parent_category"])
        products["product_key"] = range(1, len(products) + 1)
        dim_product = products[
            ["product_key", "product_id", "product_name", "brand",
             "category_key", "category_name", "price", "cost"]
        ].rename(columns={"price": "unit_price", "cost": "unit_cost"})

        channels = stg["sales_channels"].copy()
        channels["channel_key"] = range(1, len(channels) + 1)
        dim_channel = channels[["channel_key", "channel_id", "channel_name", "channel_type"]]

        promotions = stg["promotions"].copy()
        promotions["promotion_key"] = range(
            _NO_PROMOTION_KEY + 1, _NO_PROMOTION_KEY + 1 + len(promotions)
        )
        no_promo = pd.DataFrame(
            [{
                "promotion_key": _NO_PROMOTION_KEY, "promotion_id": pd.NA,
                "promotion_code": "NONE", "description": "No promotion applied",
                "discount_type": "none", "discount_value": 0.0,
            }]
        )
        dim_promotion = pd.concat(
            [no_promo, promotions[
                ["promotion_key", "promotion_id", "promotion_code",
                 "description", "discount_type", "discount_value"]
            ]],
            ignore_index=True,
        )

        methods = sorted(stg["payments"]["payment_method"].dropna().unique())
        dim_payment_method = pd.DataFrame(
            {"payment_method_key": range(1, len(methods) + 1), "payment_method": methods}
        )

        dim_date = self._build_dim_date(stg)
        return {
            "dim_date": dim_date,
            "dim_customer": dim_customer,
            "dim_category": dim_category,
            "dim_product": dim_product,
            "dim_channel": dim_channel,
            "dim_promotion": dim_promotion,
            "dim_payment_method": dim_payment_method,
        }

    def _build_dim_date(self, stg: dict[str, pd.DataFrame]) -> pd.DataFrame:
        """Calendar dimension spanning all order and return dates."""
        order_dates = pd.to_datetime(stg["orders"]["order_date"])
        return_dates = pd.to_datetime(stg["returns"]["return_date"]) if not stg["returns"].empty else order_dates
        start = min(order_dates.min(), return_dates.min()).normalize()
        end = max(order_dates.max(), return_dates.max()).normalize()

        calendar = pd.DataFrame({"full_date": pd.date_range(start, end, freq="D")})
        calendar["date_key"] = calendar["full_date"].dt.strftime("%Y%m%d").astype(int)
        calendar["year"] = calendar["full_date"].dt.year
        calendar["quarter"] = calendar["full_date"].dt.quarter
        calendar["month"] = calendar["full_date"].dt.month
        calendar["month_name"] = calendar["full_date"].dt.month_name()
        calendar["day"] = calendar["full_date"].dt.day
        calendar["day_of_week"] = calendar["full_date"].dt.dayofweek + 1
        calendar["day_name"] = calendar["full_date"].dt.day_name()
        calendar["week_of_year"] = calendar["full_date"].dt.isocalendar().week.astype(int)
        calendar["is_weekend"] = calendar["day_of_week"] >= 6
        return calendar[
            ["date_key", "full_date", "year", "quarter", "month", "month_name",
             "day", "day_of_week", "day_name", "week_of_year", "is_weekend"]
        ]

    # ----------------------------------------------------------------- facts

    def _build_fact_sales(
        self, stg: dict[str, pd.DataFrame], dims: dict[str, pd.DataFrame]
    ) -> pd.DataFrame:
        """Order-item-grain sales fact with all surrogate keys resolved."""
        orders = stg["orders"].copy()
        orders["order_date_key"] = (
            pd.to_datetime(orders["order_date"]).dt.strftime("%Y%m%d").astype(int)
        )
        # One payment per order in the source model; guard against dupes anyway.
        payments = stg["payments"].drop_duplicates(subset="order_id")[
            ["order_id", "payment_method"]
        ]

        fact = (
            stg["order_items"]
            .merge(
                orders[["order_id", "customer_id", "channel_id",
                        "promotion_id", "order_date_key"]],
                on="order_id", how="inner",
            )
            .merge(payments, on="order_id", how="left")
            .merge(dims["dim_customer"][["customer_key", "customer_id"]], on="customer_id")
            .merge(
                dims["dim_product"][["product_key", "product_id", "category_key"]],
                on="product_id",
            )
            .merge(dims["dim_channel"][["channel_key", "channel_id"]], on="channel_id")
            .merge(
                dims["dim_payment_method"], on="payment_method", how="left"
            )
        )
        promo_lookup = dims["dim_promotion"].dropna(subset=["promotion_id"])[
            ["promotion_key", "promotion_id"]
        ]
        fact = fact.merge(promo_lookup, on="promotion_id", how="left")
        fact["promotion_key"] = fact["promotion_key"].fillna(_NO_PROMOTION_KEY).astype(int)
        fact["payment_method_key"] = fact["payment_method_key"].fillna(0).astype(int)

        fact["gross_revenue"] = (fact["quantity"] * fact["unit_price"]).round(2)
        fact["net_revenue"] = fact["line_total"].astype(float)
        fact = fact.sort_values("order_item_id").reset_index(drop=True)
        fact["sales_key"] = range(1, len(fact) + 1)
        return fact[
            ["sales_key", "order_id", "order_item_id", "order_date_key",
             "customer_key", "product_key", "category_key", "channel_key",
             "promotion_key", "payment_method_key", "quantity", "unit_price",
             "gross_revenue", "discount_amount", "net_revenue"]
        ]

    def _build_fact_returns(
        self,
        stg: dict[str, pd.DataFrame],
        dims: dict[str, pd.DataFrame],
        fact_sales: pd.DataFrame,
    ) -> pd.DataFrame:
        """Returns fact, reusing the conformed keys resolved for sales."""
        returns = stg["returns"].copy()
        if returns.empty:
            return pd.DataFrame(
                columns=["return_key", "return_id", "order_id", "order_item_id",
                         "return_date_key", "customer_key", "product_key",
                         "channel_key", "quantity_returned", "refund_amount", "reason"]
            )
        returns["return_date_key"] = (
            pd.to_datetime(returns["return_date"]).dt.strftime("%Y%m%d").astype(int)
        )
        keys = fact_sales[["order_item_id", "customer_key", "product_key", "channel_key"]]
        fact = returns.merge(keys, on="order_item_id", how="inner")
        fact = fact.rename(columns={"quantity": "quantity_returned"})
        fact = fact.sort_values("return_id").reset_index(drop=True)
        fact["return_key"] = range(1, len(fact) + 1)
        return fact[
            ["return_key", "return_id", "order_id", "order_item_id",
             "return_date_key", "customer_key", "product_key", "channel_key",
             "quantity_returned", "refund_amount", "reason"]
        ]

    # ----------------------------------------------------------------- write

    def _write_to_duckdb(
        self,
        dims: dict[str, pd.DataFrame],
        fact_sales: pd.DataFrame,
        fact_returns: pd.DataFrame,
    ) -> dict[str, int]:
        """Replace the DuckDB analytics layer and log the pipeline run."""
        duck = DuckDBConnector(read_only=False)
        try:
            duck.apply_schema()
            # Clear everything in reverse dependency order before loading:
            # facts reference all dims, and dim_product references dim_category.
            duck.execute_script(
                "DELETE FROM fact_returns; DELETE FROM fact_sales; "
                "DELETE FROM dim_product; "
                "DELETE FROM dim_category; DELETE FROM dim_customer; "
                "DELETE FROM dim_date; DELETE FROM dim_channel; "
                "DELETE FROM dim_promotion; DELETE FROM dim_payment_method;"
            )
            counts: dict[str, int] = {}
            for name, frame in dims.items():
                counts[name] = duck.load_dataframe(frame, name, replace=False)
            counts["fact_sales"] = duck.load_dataframe(fact_sales, "fact_sales", replace=False)
            counts["fact_returns"] = duck.load_dataframe(
                fact_returns, "fact_returns", replace=False
            )
            run_log = pd.DataFrame(
                [{
                    "run_id": int(time.time() * 1000),
                    "step_name": "build_analytics",
                    "row_counts": json.dumps(counts),
                    "completed_at": datetime.now(),
                }]
            )
            duck.load_dataframe(run_log, "pipeline_runs", replace=False)
            return counts
        finally:
            duck.close()


def run() -> dict[str, int]:
    """Airflow-friendly entry point."""
    return TransformationService().build_analytics()
