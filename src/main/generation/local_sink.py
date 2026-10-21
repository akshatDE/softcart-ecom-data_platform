"""Write a generated dataset to flat files (the open-source pipeline's format).

CSV per relational table, ``products.json`` for the catalog and a
``manifest.json`` with row counts.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from src.main.generation.dataset import GeneratedDataset
from src.main.utility.exceptions import DataGenerationError
from src.main.utility.logger import get_logger

logger = get_logger(__name__)

PRODUCTS_FILE = "products.json"
MANIFEST_FILE = "manifest.json"


def write_to_directory(dataset: GeneratedDataset, output_dir: Path) -> dict[str, int]:
    """Persist ``dataset`` under ``output_dir``; return row counts."""
    try:
        output_dir.mkdir(parents=True, exist_ok=True)
        for name, frame in dataset.frames.items():
            path = output_dir / f"{name}.csv"
            frame.to_csv(path, index=False)
            logger.debug("Wrote {} rows to {}", len(frame), path)

        (output_dir / PRODUCTS_FILE).write_text(
            json.dumps(dataset.products, indent=2), encoding="utf-8"
        )
        counts = dataset.counts
        manifest = {"generated_at": datetime.now().isoformat(), "counts": counts}
        (output_dir / MANIFEST_FILE).write_text(
            json.dumps(manifest, indent=2), encoding="utf-8"
        )
        return counts
    except OSError as exc:
        raise DataGenerationError(f"Failed to persist generated data: {exc}") from exc
