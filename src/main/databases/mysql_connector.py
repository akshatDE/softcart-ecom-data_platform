"""Connector for the SoftCart MySQL OLTP database."""

from __future__ import annotations

from urllib.parse import quote_plus

from src.main.databases.base_sql_connector import BaseSQLConnector
from src.main.utility.config_loader import get_config

#: Load order that satisfies foreign keys; reversed for truncation.
OLTP_TABLES_IN_FK_ORDER: tuple[str, ...] = (
    "sales_channels",
    "promotions",
    "customers",
    "customer_addresses",
    "orders",
    "order_items",
    "payments",
    "returns",
)


class MySQLConnector(BaseSQLConnector):
    """SQLAlchemy connector for the transactional MySQL source system."""

    name = "mysql"

    def _build_url(self) -> str:
        config = get_config()
        user = config.get("mysql", "user")
        password = quote_plus(config.get("mysql", "password"))
        host = config.get("mysql", "host")
        port = config.get_int("mysql", "port")
        database = config.get("mysql", "database")
        return f"mysql+pymysql://{user}:{password}@{host}:{port}/{database}"

    def truncate_all(self) -> None:
        """Truncate every OLTP table (FK checks off) for a clean reload."""
        from sqlalchemy import text

        with self.engine.begin() as conn:
            conn.execute(text("SET FOREIGN_KEY_CHECKS = 0"))
            for table in reversed(OLTP_TABLES_IN_FK_ORDER):
                conn.execute(text(f"TRUNCATE TABLE {table}"))
            conn.execute(text("SET FOREIGN_KEY_CHECKS = 1"))
