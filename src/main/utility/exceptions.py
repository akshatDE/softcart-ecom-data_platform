"""Project-specific exception hierarchy for the SoftCart platform."""


class SoftCartError(Exception):
    """Base class for all SoftCart platform errors."""


class ConfigurationError(SoftCartError):
    """Raised when configuration is missing or malformed."""


class DatabaseConnectionError(SoftCartError):
    """Raised when a database connection cannot be established."""


class DataGenerationError(SoftCartError):
    """Raised when synthetic data generation fails."""


class ETLError(SoftCartError):
    """Raised when an extract/load/transform step fails."""


class DataQualityError(SoftCartError):
    """Raised when a data-quality check fails hard enough to stop the pipeline."""


class SQLValidationError(SoftCartError):
    """Raised when generated or user-supplied SQL fails safety validation."""


class NLPServiceError(SoftCartError):
    """Raised when the Ollama NLP-to-SQL service fails or misbehaves."""
