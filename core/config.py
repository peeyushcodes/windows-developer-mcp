"""
Application configuration for Windows Developer MCP.

Loads settings from ``config.toml`` at the project root, then validates them
with Pydantic. Falls back to sensible defaults if no config file is found.

Environment variable overrides are supported with the ``MCP_`` prefix:
    MCP_SECURITY__TIMEOUT=120   → security.timeout = 120
    MCP_WORKSPACE__READ_ONLY=true → workspace.read_only = True

Usage::

    from core.config import get_config

    cfg = get_config()
    print(cfg.security.timeout)  # 60
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
import tomllib
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator

logger = logging.getLogger(__name__)

# Path to the config file, relative to the project root.
_CONFIG_PATH = Path("config.toml")

# Module-level singleton — loaded once, reused everywhere.
_config: AppConfig | None = None


# ==============================================================================
# Config Section Models
# ==============================================================================


class ServerConfig(BaseModel):
    """Top-level server identity settings."""

    name: str = "Windows Developer MCP"
    version: str = "0.1.0"


class WorkspaceConfig(BaseModel):
    """File system workspace boundary settings."""

    path: str = "."
    allowed_directories: list[str] = Field(default_factory=list)
    read_only: bool = False

    @property
    def resolved_path(self) -> Path:
        """Return the workspace path as a resolved absolute ``Path``."""
        return Path(self.path).resolve()


class SecurityConfig(BaseModel):
    """Command execution security settings."""

    timeout: int = Field(default=60, ge=1, le=3600, description="Subprocess timeout in seconds.")
    require_confirmation: bool = Field(
        default=True,
        description="Require explicit confirmation for destructive commands.",
    )
    max_output_length: int = Field(
        default=50_000,
        ge=1_000,
        description="Maximum characters returned per tool response.",
    )
    extra_blocked_patterns: list[str] = Field(
        default_factory=list,
        description="Additional regex patterns to block, appended to the built-in list.",
    )
    command_allowlist: list[str] = Field(
        default_factory=list,
        description="If non-empty, only commands matching these prefixes are allowed.",
    )

    @field_validator("timeout", mode="before")
    @classmethod
    def _coerce_timeout(cls, v: Any) -> int:
        """Accept string values from environment variable overrides."""
        return int(v)


class LoggingConfig(BaseModel):
    """Audit and application logging settings."""

    level: str = Field(default="INFO", description="Python logging level.")
    log_dir: str = Field(default="logs", description="Audit log directory.")
    max_log_size_mb: int = Field(default=10, ge=1, description="Max log file size in MB.")
    backup_count: int = Field(default=5, ge=0, description="Number of rotated log backups.")

    @field_validator("level")
    @classmethod
    def _validate_level(cls, v: str) -> str:
        valid = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        upper = v.upper()
        if upper not in valid:
            raise ValueError(f"Invalid log level {v!r}. Must be one of: {valid}")
        return upper


class ProvidersConfig(BaseModel):
    """Feature flags for each provider. Set to false to disable entirely."""

    terminal: bool = True
    filesystem: bool = True
    git: bool = True
    python: bool = True
    node: bool = True
    docker: bool = True
    windows: bool = True
    network: bool = True
    sqlite: bool = True
    project: bool = True
    github: bool = True
    browser: bool = False

    def is_enabled(self, name: str) -> bool:
        """Return True if the named provider is enabled.

        Args:
            name: The provider name (e.g. ``"git"``, ``"terminal"``).

        Returns:
            True if enabled, False otherwise. Unknown providers default to False.
        """
        return bool(getattr(self, name, False))


class AppConfig(BaseModel):
    """Root application configuration model."""

    server: ServerConfig = Field(default_factory=ServerConfig)
    workspace: WorkspaceConfig = Field(default_factory=WorkspaceConfig)
    security: SecurityConfig = Field(default_factory=SecurityConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    providers: ProvidersConfig = Field(default_factory=ProvidersConfig)

    @model_validator(mode="after")
    def _apply_env_overrides(self) -> AppConfig:
        """Apply MCP_ prefixed environment variables as overrides."""
        prefix = "MCP_"
        for key, value in os.environ.items():
            if not key.startswith(prefix):
                continue
            # MCP_SECURITY__TIMEOUT → ["security", "timeout"]
            parts = key[len(prefix):].lower().split("__")
            if len(parts) == 2:
                section, field = parts
                section_model = getattr(self, section, None)
                if section_model is not None and hasattr(section_model, field):
                    try:
                        # Re-validate to coerce types
                        current_data = section_model.model_dump()
                        current_data[field] = value
                        updated = section_model.__class__.model_validate(current_data)
                        object.__setattr__(self, section, updated)
                    except Exception:
                        logger.warning(
                            "Failed to apply env override %s=%r", key, value
                        )
        return self


# ==============================================================================
# Public API
# ==============================================================================


def load_config(path: Path = _CONFIG_PATH) -> AppConfig:
    """
    Load and validate the application configuration from a TOML file.

    Falls back to default values if the file does not exist or contains
    errors. The loaded config is cached and subsequent calls return the
    same instance.

    Args:
        path: Path to the TOML configuration file.

    Returns:
        A fully-validated :class:`AppConfig` instance.
    """
    global _config

    if _config is not None:
        return _config

    if not path.exists():
        logger.info("No config.toml found at %s — using defaults.", path.resolve())
        _config = AppConfig()
        return _config

    try:
        with open(path, "rb") as f:
            raw: dict[str, Any] = tomllib.load(f)
        _config = AppConfig.model_validate(raw)
        logger.info("Loaded configuration from %s", path.resolve())
    except Exception as exc:
        logger.warning(
            "Failed to parse config at %s: %s — falling back to defaults.",
            path.resolve(),
            exc,
        )
        _config = AppConfig()

    return _config


def get_config() -> AppConfig:
    """
    Return the application configuration singleton.

    Calls :func:`load_config` on first access. Subsequent calls return
    the cached instance without re-reading the file.

    Returns:
        The application :class:`AppConfig` instance.
    """
    global _config
    if _config is None:
        return load_config()
    return _config


def reset_config() -> None:
    """
    Clear the cached configuration singleton.

    Intended for use in tests only. Forces the next :func:`get_config`
    call to re-read the configuration file from disk.
    """
    global _config
    _config = None
