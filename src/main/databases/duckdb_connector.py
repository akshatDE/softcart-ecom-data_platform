"""Connector for the DuckDB analytics database (star schema layer)."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Sequence

import duckdb
import pandas as pd

from src.main.utility.config_loader import get_config
from src.main.utility.exceptions import DatabaseConnectionError, ETLError
from src.main.utility.logger import get_logger

logger = get_logger(__name__)


class DuckDBConnector:
    """Wrapper over the DuckDB Python API for the analytics layer.

    Analytics/API consumers should use ``read_only=True`` so a dashboard
    query can never mutate the warehouse; only the transformation service
    opens a writable connection.
    """

    def __init__(self, read_only: bool = False) -> None:
        self.database_path: Path = get_config().get_path("duckdb", "database_path")
        self.read_only = read_only
        self._conn: duckdb.DuckDBPyConnection | None = None

    @property
    def connection(self) -> duckdb.DuckDBPyConnection:
        """Lazily opened DuckDB connection."""
        if self._conn is None:
            try:
                self.database_path.parent.mkdir(parents=True, exist_ok=True)
                self._conn = duckdb.connect(str(self.database_path), read_only=self.read_only)
                logger.debug(
                    "Opened duckdb at {} (read_only={})", self.database_path, self.read_only
                )
            except duckdb.Error as exc:
                raise DatabaseConnectionError(f"DuckDB connection failed: {exc}") from exc
        return self._conn

    def execute_script(self, sql_script: str) -> None:
        """Run a multi-statement SQL script (schema creation etc.)."""
        try:
            self.connection.execute(sql_script)
        except duckdb.Error as exc:
            raise ETLError(f"DuckDB script failed: {exc}") from exc

    def apply_schema(self) -> None:
        """Create the analytics star schema if it does not exist."""
        schema_file = (
            get_config().project_root / "resources" / "config" / "duckdb_analytics_schema.sql"
        )
        self.execute_script(schema_file.read_text(encoding="utf-8"))
        logger.info("duckdb: analytics schema ensured")

    def query_df(self, sql: str, params: Sequence[Any] | None = None) -> pd.DataFrame:
        """Run a parameterized query and return a DataFrame."""
        try:
            return self.connection.execute(sql, params or []).df()
        except duckdb.Error as exc:
            raise ETLError(f"DuckDB query failed: {exc}") from exc

    def load_dataframe(self, frame: pd.DataFrame, table: str, replace: bool = True) -> int:
        """Load a DataFrame into ``table``; optionally clearing it first."""
        try:
            self.connection.register("_softcart_tmp", frame)
            if replace:
                self.connection.execute(f"DELETE FROM {table}")
            self.connection.execute(
                f"INSERT INTO {table} SELECT * FROM _softcart_tmp"  # noqa: S608 — internal names
            )
            self.connection.unregister("_softcart_tmp")
            logger.info("duckdb: loaded {} rows into {}", len(frame), table)
            return len(frame)
        except duckdb.Error as exc:
            raise ETLError(f"DuckDB load into {table} failed: {exc}") from exc

    def interrupt(self) -> None:
        """Cancel the currently running query (used by query timeouts)."""
        if self._conn is not None:
            self._conn.interrupt()

    def close(self) -> None:
        """Close the connection."""
        if self._conn is not None:
            self._conn.close()
            self._conn = None
