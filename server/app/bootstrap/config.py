"""Validated, nested application configuration models."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, PositiveInt, field_validator


class StrictConfig(BaseModel):
    """Base model that rejects misspelled configuration keys."""

    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)


class ProfileConfig(StrictConfig):
    """An optional YAML overlay registered by tag and merge priority."""

    priority: int = Field(ge=1)


class ConfigurationConfig(StrictConfig):
    """Configuration-loader settings declared only in config.default.yaml."""

    profiles: dict[str, ProfileConfig] = Field(default_factory=dict)

    @field_validator("profiles")
    @classmethod
    def profile_tags_are_valid(
        cls, profiles: dict[str, ProfileConfig]
    ) -> dict[str, ProfileConfig]:
        """Require tags that map unambiguously to config.<tag>.yaml files."""
        for tag in profiles:
            if not tag or not tag.replace("-", "").replace("_", "").isalnum():
                raise ValueError(
                    "profile tags must contain only letters, digits, '_' or '-'"
                )
        return profiles


class DatabaseConfig(StrictConfig):
    """Database connection configuration shared by runtime and migrations."""

    url: str = "sqlite+aiosqlite:///metaweave.db"
    echo: bool = False
    busy_timeout_ms: PositiveInt = 5000


class LoggingConfig(StrictConfig):
    """Logging defaults for process entry points."""

    level: str = "INFO"
    json_output: bool = Field(False, alias="json")
    colors: bool = True
    silenced_loggers: tuple[str, ...] = ()
    log_request_headers: bool = False


class ServerConfig(StrictConfig):
    """HTTP bind and development reload settings."""

    host: str = "127.0.0.1"
    port: int = Field(8000, ge=1, le=65535)
    reload: bool = False


class AppInfoConfig(StrictConfig):
    """Application identity exposed to delivery adapters."""

    name: str = "metaweave"
    debug: bool = False


class AppConfig(StrictConfig):
    """Complete, validated configuration assembled from YAML overlays."""

    configuration: ConfigurationConfig = Field(default_factory=ConfigurationConfig)
    app: AppInfoConfig = Field(default_factory=AppInfoConfig)
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    server: ServerConfig = Field(default_factory=ServerConfig)


def default_config_dir() -> Path:
    """Return the repository/package configuration directory."""
    return Path(__file__).resolve().parents[2] / "config"
