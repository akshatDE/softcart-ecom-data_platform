"""Central configuration loading for the SoftCart platform.

All settings live in ``resources/config/config_file.ini``. Any value can be
overridden by an environment variable named ``SOFTCART_<SECTION>__<KEY>``
(upper-cased), which is how docker-compose points containers at service
hostnames without editing the file.
"""

from __future__ import annotations

import configparser
import os
from pathlib import Path

from src.main.utility.exceptions import ConfigurationError

_ENV_PREFIX = "SOFTCART_"
_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_DEFAULT_CONFIG_PATH = _PROJECT_ROOT / "resources" / "config" / "config_file.ini"


class ConfigLoader:
    """Read-only accessor over the project INI file with env overrides."""

    _instance: "ConfigLoader | None" = None

    def __init__(self, config_path: str | Path | None = None) -> None:
        """Parse the configuration file.

        Args:
            config_path: Optional explicit path; defaults to the packaged
                ``config_file.ini`` (or ``$SOFTCART_CONFIG`` if set).
        """
        path = Path(config_path or os.environ.get("SOFTCART_CONFIG", _DEFAULT_CONFIG_PATH))
        if not path.is_file():
            raise ConfigurationError(f"Configuration file not found: {path}")
        self._parser = configparser.ConfigParser()
        self._parser.read(path, encoding="utf-8")
        self._path = path

    @classmethod
    def instance(cls) -> "ConfigLoader":
        """Return the process-wide singleton loader."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @property
    def project_root(self) -> Path:
        """Root directory of the project checkout."""
        return _PROJECT_ROOT

    def get(self, section: str, key: str, fallback: str | None = None) -> str:
        """Return a string setting, honouring environment overrides."""
        env_name = f"{_ENV_PREFIX}{section.upper()}__{key.upper()}"
        env_value = os.environ.get(env_name)
        if env_value is not None:
            return env_value
        try:
            return self._parser.get(section, key)
        except (configparser.NoSectionError, configparser.NoOptionError) as exc:
            if fallback is not None:
                return fallback
            raise ConfigurationError(f"Missing config value [{section}] {key}") from exc

    def get_int(self, section: str, key: str, fallback: int | None = None) -> int:
        """Return an integer setting."""
        raw = self.get(section, key, None if fallback is None else str(fallback))
        try:
            return int(raw)
        except ValueError as exc:
            raise ConfigurationError(f"[{section}] {key} is not an integer: {raw!r}") from exc

    def get_float(self, section: str, key: str, fallback: float | None = None) -> float:
        """Return a float setting."""
        raw = self.get(section, key, None if fallback is None else str(fallback))
        try:
            return float(raw)
        except ValueError as exc:
            raise ConfigurationError(f"[{section}] {key} is not a number: {raw!r}") from exc

    def get_path(self, section: str, key: str) -> Path:
        """Return a filesystem setting resolved against the project root."""
        raw = Path(self.get(section, key))
        return raw if raw.is_absolute() else _PROJECT_ROOT / raw

    def section(self, name: str) -> dict[str, str]:
        """Return a whole section as a dict (env overrides applied)."""
        if not self._parser.has_section(name):
            raise ConfigurationError(f"Missing config section [{name}]")
        return {key: self.get(name, key) for key in self._parser.options(name)}


def get_config() -> ConfigLoader:
    """Convenience accessor for the singleton :class:`ConfigLoader`."""
    return ConfigLoader.instance()
