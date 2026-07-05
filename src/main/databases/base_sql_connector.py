"""Shared SQLAlchemy plumbing for the MySQL and PostgreSQL connectors."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError

from src.main.utility.exceptions import DatabaseConnectionError, ETLError
from src.main.utility.logger import get_logger

logger = get_logger(__name__)


class BaseSQLConnector:
    """Thin wrapper over a SQLAlchemy engine with pandas helpers.

    Subclasses only need to provide :meth:`_build_url` and a ``name``.
    """

    name = "sql"

    def __init__(self) -> None:
        self._engine: Engine | None = None

    def _build_url(self) -> str:
        """Return the SQLAlchemy connection URL for this database."""
        raise NotImplementedError

    @property
    def engine(self) -> Engine:
        """Lazily created SQLAlchemy engine (pooled, pre-ping enabled)."""
        if self._engine is None:
            try:
                self._engine = create_engine(self._build_url(), pool_pre_ping=True)
                logger.debug("Created {} engine", self.name)
            except SQLAlchemyError as exc:
                raise DatabaseConnectionError(f"Cannot create {self.name} engine: {exc}") from exc
        return self._engine

    def test_connection(self) -> bool:
        """Return True if a trivial round-trip succeeds, else raise."""
        try:
            with self.engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            logger.info("Connected to {}", self.name)
            return True
        except SQLAlchemyError as exc:
            raise DatabaseConnectionError(f"{self.name} connection failed: {exc}") from exc

    def read_sql(self, sql: str, params: Mapping[str, Any] | None = None) -> pd.DataFrame:
        """Run a parameterized SELECT and return a DataFrame."""
        try:
            with self.engine.connect() as conn:
                frame = pd.read_sql(text(sql), conn, params=dict(params or {}))
            logger.debug("{}: read {} rows", self.name, len(frame))
            return frame
        except SQLAlchemyError as exc:
            raise ETLError(f"{self.name} read failed: {exc}") from exc

    def read_table(self, table: str, schema: str | None = None) -> pd.DataFrame:
        """Read an entire table into a DataFrame."""
        qualified = f"{schema}.{table}" if schema else table
        return self.read_sql(f"SELECT * FROM {qualified}")  # noqa: S608 — internal table names

    def execute(
        self,
        sql: str,
        params: Mapping[str, Any] | Sequence[Mapping[str, Any]] | None = None,
    ) -> None:
        """Execute a parameterized statement inside a transaction."""
        try:
            with self.engine.begin() as conn:
                conn.execute(text(sql), params)
        except SQLAlchemyError as exc:
            raise ETLError(f"{self.name} statement failed: {exc}") from exc

    def load_dataframe(
        self,
        frame: pd.DataFrame,
        table: str,
        schema: str | None = None,
        if_exists: str = "append",
        chunksize: int = 1000,
    ) -> int:
        """Bulk-load a DataFrame and return the number of rows written."""
        try:
            frame.to_sql(
                table,
                self.engine,
                schema=schema,
                if_exists=if_exists,
                index=False,
                chunksize=chunksize,
                method="multi",
            )
            logger.info("{}: loaded {} rows into {}", self.name, len(frame), table)
            return len(frame)
        except SQLAlchemyError as exc:
            raise ETLError(f"{self.name} load into {table} failed: {exc}") from exc

    def dispose(self) -> None:
        """Release pooled connections."""
        if self._engine is not None:
            self._engine.dispose()
            self._engine = None
