"""Synthetic source-data generation for SoftCart.

Generates a referentially consistent e-commerce history with the shared
generation core (:mod:`src.main.generation`), then persists it as flat files
under ``[data_generation] output_dir`` (CSV for relational entities, JSON for
the product catalog). Keeping generation and source loading as separate steps
lets the Airflow DAG re-load sources without regenerating data.
"""

from __future__ import annotations

from pathlib import Path

from src.main.generation import TABLES, GenerationSettings, generate_dataset
from src.main.generation.local_sink import PRODUCTS_FILE, write_to_directory
from src.main.utility.config_loader import get_config
from src.main.utility.logger import get_logger

logger = get_logger(__name__)

# Re-exported for callers that already import them from here.
__all__ = ["CSV_ENTITIES", "PRODUCTS_FILE", "DataGenerationService", "run"]

CSV_ENTITIES = TABLES


class DataGenerationService:
    """Generates the dataset from config and writes it to the output directory."""

    def __init__(self) -> None:
        self.output_dir: Path = get_config().get_path("data_generation", "output_dir")
        self.settings = GenerationSettings.from_config()

    def generate(self) -> dict[str, int]:
        """Generate the full dataset and write it to the output directory.

        Returns:
            Row counts per entity, for logging and Airflow XCom visibility.
        """
        s = self.settings
        logger.info(
            "Data generation started: {} customers, {} products, {} orders ({} → {})",
            s.num_customers, s.num_products, s.num_orders, s.start_date, s.end_date,
        )
        dataset = generate_dataset(s)
        counts = write_to_directory(dataset, self.output_dir)
        logger.info("Data generation finished: {}", counts)
        return counts


def run() -> dict[str, int]:
    """Airflow-friendly entry point."""
    return DataGenerationService().generate()
