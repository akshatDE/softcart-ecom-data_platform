"""Extraction from source systems into the PostgreSQL staging warehouse.

For each source table this service extracts with pandas/SQLAlchemy, applies
light cleaning and standardization, then truncate-and-loads the matching
``staging.stg_*`` table. Every load is recorded in ``staging.etl_audit`` so
timeliness checks can verify data freshness.
"""

from __future__ import annotations

import json

import pandas as pd

from src.main.databases.mongodb_connector import MongoDBConnector
from src.main.databases.mysql_connector import MySQLConnector
from src.main.databases.postgres_connector import PostgresConnector
from src.main.utility.config_loader import get_config
from src.main.utility.logger import get_logger

logger = get_logger(__name__)

#: MySQL table -> columns kept in staging (order matters for the load).
_MYSQL_TABLE_COLUMNS: dict[str, list[str]] = {
    "sales_channels": ["channel_id", "channel_name", "channel_type"],
    "promotions": [
        "promotion_id", "promotion_code", "description",
        "discount_type", "discount_value", "start_date", "end_date",
    ],
    "customer_addresses": [
        "address_id", "customer_id", "address_type", "street",
        "city", "state", "country", "postal_code",
    ],
    "orders": [
        "order_id", "customer_id", "channel_id", "promotion_id",
        "order_date", "status", "total_amount",
    ],
    "order_items": [
        "order_item_id", "order_id", "product_id", "quantity",
        "unit_price", "discount_amount", "line_total",
    ],
    "payments": [
        "payment_id", "order_id", "payment_method", "amount",
        "payment_date", "status",
    ],
    "returns": [
        "return_id", "order_id", "order_item_id", "return_date",
        "quantity", "refund_amount", "reason",
    ],
}


class StagingService:
    """Extracts, cleans, and stages source data in PostgreSQL."""

    def __init__(self) -> None:
        config = get_config()
        self.prefix = config.get("pipeline", "staging_table_prefix", "stg_")
        self.batch_size = config.get_int("pipeline", "batch_size", 1000)
        self._postgres = PostgresConnector()

    def stage_all(self) -> dict[str, int]:
        """Run the full extraction into staging; returns rows per table."""
        logger.info("Staging extraction started")
        self._postgres.ensure_schema()
        counts: dict[str, int] = {}

        mysql = MySQLConnector()
        mysql.test_connection()
        try:
            counts.update(self._stage_mysql_tables(mysql))
            counts["stg_customers"] = self._stage_customers(mysql)
        finally:
            mysql.dispose()

        counts["stg_products"] = self._stage_products()
        logger.info("Staging extraction finished: {}", counts)
        return counts

    def _stage_mysql_tables(self, mysql: MySQLConnector) -> dict[str, int]:
        """Copy each plain MySQL table into its staging twin."""
        counts: dict[str, int] = {}
        for table, columns in _MYSQL_TABLE_COLUMNS.items():
            frame = mysql.read_table(table)[columns]
            frame = self._clean_strings(frame)
            frame = frame.drop_duplicates(subset=columns[0])
            counts[f"{self.prefix}{table}"] = self._load(f"{self.prefix}{table}", frame)
        return counts

    def _stage_customers(self, mysql: MySQLConnector) -> int:
        """Stage customers enriched with their billing geography."""
        customers = mysql.read_table("customers")[
            ["customer_id", "first_name", "last_name", "email", "phone", "signup_date"]
        ]
        addresses = mysql.read_sql(
            "SELECT customer_id, city, state, country FROM customer_addresses "
            "WHERE address_type = :address_type",
            {"address_type": "billing"},
        ).drop_duplicates(subset="customer_id")

        frame = customers.merge(addresses, on="customer_id", how="left")
        frame = self._clean_strings(frame)
        frame["email"] = frame["email"].str.lower()
        frame = frame.drop_duplicates(subset="customer_id")
        return self._load(f"{self.prefix}customers", frame)

    def _stage_products(self) -> int:
        """Flatten MongoDB product documents into a relational staging table."""
        mongo = MongoDBConnector()
        try:
            documents = mongo.fetch_products()
        finally:
            mongo.close()

        rows = [
            {
                "product_id": doc.get("product_id"),
                "product_name": (doc.get("name") or "").strip(),
                "brand": (doc.get("brand") or {}).get("name"),
                "category_name": ((doc.get("category") or {}).get("name") or "Unknown").strip(),
                "parent_category": ((doc.get("category") or {}).get("parent") or "Unknown").strip(),
                "price": (doc.get("pricing") or {}).get("price", 0.0),
                "cost": (doc.get("pricing") or {}).get("cost", 0.0),
                "tags": ",".join(doc.get("tags") or []),
                "attributes": json.dumps(doc.get("attributes") or {}),
                "variant_count": len(doc.get("variants") or []),
                "created_at": (doc.get("metadata") or {}).get("created_at"),
            }
            for doc in documents
        ]
        frame = pd.DataFrame(rows).drop_duplicates(subset="product_id")
        frame["created_at"] = pd.to_datetime(frame["created_at"], errors="coerce", utc=True)
        frame["created_at"] = frame["created_at"].dt.tz_localize(None)
        return self._load(f"{self.prefix}products", frame)

    @staticmethod
    def _clean_strings(frame: pd.DataFrame) -> pd.DataFrame:
        """Trim whitespace on string values.

        Object-dtype columns can hold non-string values (MySQL DECIMALs
        arrive as ``decimal.Decimal``), so strip per value, not per column.
        """
        frame = frame.copy()
        for column in frame.select_dtypes(include="object").columns:
            frame[column] = frame[column].map(
                lambda value: value.strip() if isinstance(value, str) else value
            )
        return frame

    def _load(self, table: str, frame: pd.DataFrame) -> int:
        """Truncate-and-load one staging table and record the audit row."""
        schema = self._postgres.staging_schema
        self._postgres.execute(f"TRUNCATE TABLE {schema}.{table}")
        count = self._postgres.load_dataframe(
            frame, table, schema=schema, chunksize=self.batch_size
        )
        self._postgres.record_audit(table, count)
        return count


def run() -> dict[str, int]:
    """Airflow-friendly entry point."""
    return StagingService().stage_all()
