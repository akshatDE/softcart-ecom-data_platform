"""Loguru-based logging setup shared by every SoftCart module.

Usage::

    from src.main.utility.logger import get_logger
    logger = get_logger(__name__)
    logger.info("pipeline started")
"""

from __future__ import annotations

import sys
from pathlib import Path

from loguru import logger as _logger

from src.main.utility.config_loader import get_config

_CONFIGURED = False

_CONSOLE_FORMAT = (
    "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
    "<level>{level: <8}</level> | "
    "<cyan>{extra[module]}</cyan> | "
    "<level>{message}</level>"
)
_FILE_FORMAT = "{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {extra[module]} | {message}"


def _configure() -> None:
    """Install console and rotating-file sinks once per process."""
    global _CONFIGURED
    if _CONFIGURED:
        return

    config = get_config()
    level = config.get("logging", "level", "INFO").upper()
    log_dir = config.get_path("logging", "log_dir")
    rotation = config.get("logging", "rotation", "10 MB")
    retention = config.get("logging", "retention", "14 days")

    _logger.remove()
    _logger.configure(extra={"module": "softcart"})
    _logger.add(sys.stderr, level=level, format=_CONSOLE_FORMAT, colorize=True)
    try:
        Path(log_dir).mkdir(parents=True, exist_ok=True)
        _logger.add(
            Path(log_dir) / "softcart_{time:YYYY-MM-DD}.log",
            level="DEBUG",
            format=_FILE_FORMAT,
            rotation=rotation,
            retention=retention,
            enqueue=True,
            backtrace=False,
        )
    except OSError as exc:  # read-only filesystem etc. — console logging still works
        _logger.bind(module="logger").warning("File logging disabled: {}", exc)

    _CONFIGURED = True


def get_logger(module_name: str):
    """Return a loguru logger bound to ``module_name`` for readable output."""
    _configure()
    short_name = module_name.rsplit(".", maxsplit=1)[-1]
    return _logger.bind(module=short_name)
