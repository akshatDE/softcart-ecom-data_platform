"""Connector for the SoftCart PostgreSQL staging warehouse."""

from __future__ import annotations

from urllib.parse import quote_plus

from src.main.databases.base_sql_connector import BaseSQLConnector
from src.main.utility.config_loader import get_config


class PostgresConnector(BaseSQLConnector):
    """SQLAlchemy connector for the staging warehouse."""

    name = "postgres"

    def __init__(self) -> None:
        super().__init__()
        self.staging_schema = get_config().get("postgres", "schema", "staging")

    def _build_url(self) -> str:
        config = get_config()
        user = config.get("postgres", "user")
        password = quote_plus(config.get("postgres", "password"))
        host = config.get("postgres", "host")
        port = config.get_int("postgres", "port")
        database = config.get("postgres", "database")
        return f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{database}"

    def ensure_schema(self) -> None:
        """Create the staging schema and tables if they do not exist yet."""
        schema_file = get_config().project_root / "resources" / "config" / "postgres_staging_schema.sql"
        from sqlalchemy import text

        with self.engine.begin() as conn:
            conn.execute(text(schema_file.read_text(encoding="utf-8")))

    def record_audit(self, table_name: str, row_count: int) -> None:
        """Append a load event to the ETL audit trail (timeliness checks)."""
        self.execute(
            f"INSERT INTO {self.staging_schema}.etl_audit (table_name, row_count) "
            "VALUES (:table_name, :row_count)",
            {"table_name": table_name, "row_count": row_count},
        )
