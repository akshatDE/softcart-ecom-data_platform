"""Shared synthetic-data generation used by every SoftCart platform target."""

from src.main.generation.dataset import (
    TABLES,
    GeneratedDataset,
    GenerationSettings,
    generate_dataset,
)

__all__ = ["TABLES", "GeneratedDataset", "GenerationSettings", "generate_dataset"]
