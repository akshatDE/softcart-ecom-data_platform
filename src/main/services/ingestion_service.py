"""Ingestion of generated flat files into the source systems.

Loads the CSVs produced by :mod:`data_generation_service` into MySQL (in
foreign-key order, truncate-and-load for idempotent reruns) and the product
JSON into MongoDB.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from src.main.databases.mongodb_connector import MongoDBConnector
from src.main.databases.mysql_connector import MySQLConnector, OLTP_TABLES_IN_FK_ORDER
from src.main.services.data_generation_service import PRODUCTS_FILE
from src.main.utility.config_loader import get_config
from src.main.utility.exceptions import ETLError
from src.main.utility.logger import get_logger

logger = get_logger(__name__)


class IngestionService:
    """Loads generated data into the MySQL OLTP and MongoDB catalog."""

    def __init__(self) -> None:
        config = get_config()
        self.input_dir: Path = config.get_path("data_generation", "output_dir")
        self.batch_size = config.get_int("pipeline", "batch_size", 1000)

    def _read_csv(self, entity: str) -> pd.DataFrame:
        """Read one generated CSV, failing clearly if generation never ran."""
        path = self.input_dir / f"{entity}.csv"
        if not path.is_file():
            raise ETLError(f"Missing generated file {path}; run data generation first.")
        return pd.read_csv(path)

    def load_mysql(self) -> dict[str, int]:
        """Truncate and reload every OLTP table in FK-safe order."""
        logger.info("MySQL source load started")
        connector = MySQLConnector()
        connector.test_connection()
        connector.truncate_all()

        counts: dict[str, int] = {}
        try:
            for table in OLTP_TABLES_IN_FK_ORDER:
                frame = self._read_csv(table)
                # pandas NaN -> SQL NULL for optional FKs (e.g. promotion_id).
                frame = frame.astype(object).where(frame.notna(), None)
                counts[table] = connector.load_dataframe(
                    frame, table, chunksize=self.batch_size
                )
        finally:
            connector.dispose()
        logger.info("MySQL source load finished: {}", counts)
        return counts

    def load_mongodb(self) -> int:
        """Replace the MongoDB product catalog with the generated documents."""
        logger.info("MongoDB source load started")
        path = self.input_dir / PRODUCTS_FILE
        if not path.is_file():
            raise ETLError(f"Missing generated file {path}; run data generation first.")
        documents = json.loads(path.read_text(encoding="utf-8"))

        connector = MongoDBConnector()
        try:
            count = connector.replace_products(documents)
        finally:
            connector.close()
        logger.info("MongoDB source load finished: {} documents", count)
        return count


def run_mysql() -> dict[str, int]:
    """Airflow-friendly entry point for the MySQL load."""
    return IngestionService().load_mysql()


def run_mongodb() -> int:
    """Airflow-friendly entry point for the MongoDB load."""
    return IngestionService().load_mongodb()
