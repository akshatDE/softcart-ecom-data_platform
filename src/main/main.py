"""Command-line entry point for the SoftCart data pipeline.

Runs the same steps the Airflow DAG orchestrates, useful for local
development and one-shot rebuilds::

    python -m src.main.main --step all
    python -m src.main.main --step generate
    python -m src.main.main --step load-sources
    python -m src.main.main --step stage
    python -m src.main.main --step quality
    python -m src.main.main --step transform
"""

from __future__ import annotations

import argparse
import sys

from src.main.services import (
    data_generation_service,
    data_quality_service,
    ingestion_service,
    staging_service,
    transformation_service,
)
from src.main.utility.exceptions import SoftCartError
from src.main.utility.logger import get_logger

logger = get_logger(__name__)

_STEPS = ("generate", "load-sources", "stage", "quality", "transform", "all")


def _run_step(step: str) -> None:
    """Execute one named pipeline step."""
    if step == "generate":
        data_generation_service.run()
    elif step == "load-sources":
        ingestion_service.run_mysql()
        ingestion_service.run_mongodb()
    elif step == "stage":
        staging_service.run()
    elif step == "quality":
        data_quality_service.run_staging_checks()
    elif step == "transform":
        transformation_service.run()
        data_quality_service.run_analytics_checks()
    else:
        raise ValueError(f"Unknown step: {step}")


def main(argv: list[str] | None = None) -> int:
    """Parse arguments and run the requested pipeline step(s)."""
    parser = argparse.ArgumentParser(description="SoftCart data pipeline runner")
    parser.add_argument("--step", choices=_STEPS, default="all",
                        help="Pipeline step to run (default: all)")
    args = parser.parse_args(argv)

    steps = ["generate", "load-sources", "stage", "quality", "transform"] \
        if args.step == "all" else [args.step]

    logger.info("Pipeline run started: steps={}", steps)
    for step in steps:
        logger.info("=== step: {} ===", step)
        try:
            _run_step(step)
        except SoftCartError as exc:
            logger.critical("Pipeline failed at step {!r}: {}", step, exc)
            return 1
        except Exception:  # noqa: BLE001 — last-resort guard so failures are never silent
            logger.exception("Unexpected error at step {!r}", step)
            return 1
    logger.info("Pipeline run finished successfully")
    return 0


if __name__ == "__main__":
    sys.exit(main())
