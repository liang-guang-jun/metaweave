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


class PasswordPolicyConfig(StrictConfig):
    """IAM password policy."""

    min_length: PositiveInt = 12
    require_upper: bool = True
    require_digit: bool = True
    require_symbol: bool = True
    max_failures: PositiveInt = 5
    lockout_seconds: PositiveInt = 300


class TokenConfig(StrictConfig):
    """IAM access-token settings."""

    issuer: str = "iam"
    audience: str = "business-api"
    secret: str = "development-only-change-me"
    access_ttl_seconds: PositiveInt = 3600
    refresh_ttl_seconds: PositiveInt = 2592000


class OidcConfig(StrictConfig):
    """OIDC verification settings."""

    issuer: str = ""
    audience: str = ""
    client_id: str = ""


class AclConfig(StrictConfig):
    """ACL limits and cache settings."""

    max_entries: PositiveInt = 1000
    max_user_grants: PositiveInt = 10000
    cache_enabled: bool = False
    cache_ttl_seconds: PositiveInt = 30


class AppConfig(StrictConfig):
    """Complete, validated configuration assembled from YAML overlays."""

    configuration: ConfigurationConfig = Field(default_factory=ConfigurationConfig)
    app: AppInfoConfig = Field(default_factory=AppInfoConfig)
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    server: ServerConfig = Field(default_factory=ServerConfig)
    password_policy: PasswordPolicyConfig = Field(default_factory=PasswordPolicyConfig)
    token: TokenConfig = Field(default_factory=TokenConfig)
    oidc: OidcConfig = Field(default_factory=OidcConfig)
    acl: AclConfig = Field(default_factory=AclConfig)


def default_config_dir() -> Path:
    """Return the repository/package configuration directory."""
    return Path(__file__).resolve().parents[2] / "config"
