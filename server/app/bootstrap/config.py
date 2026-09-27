"""Validated, nested application configuration models."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

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


class FrontendConfig(StrictConfig):
    """Built single-page frontend served from the HTTP root."""

    type: Literal["static", "disabled"] = "static"
    path: Path = Path("dist/client")


class AppInfoConfig(StrictConfig):
    """Application identity exposed to delivery adapters."""

    name: str = "metaweave"
    debug: bool = False
    frontend: FrontendConfig | None = None


class ApiConfig(StrictConfig):
    """HTTP API namespace shared by every router.

    Serving the API under a prefix (for example ``/api/v1``) keeps it clear of
    the SPA's client-side routes and lets the frontend own the root path.
    """

    prefix: str = ""

    @field_validator("prefix")
    @classmethod
    def normalize_prefix(cls, prefix: str) -> str:
        """Normalize to one leading slash with no trailing slash."""
        trimmed = prefix.strip().strip("/")
        return f"/{trimmed}" if trimmed else ""


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
    #: Header carrying the access token. Hosting platforms (Databricks Apps, for
    #: example) own ``Authorization`` for their own SSO, so the HTTP layer reads
    #: this header first and still accepts ``Authorization: Bearer``.
    header: str = "X-Bearer-Token"
    access_ttl_seconds: PositiveInt = 3600
    refresh_ttl_seconds: PositiveInt = 2592000

    @field_validator("header")
    @classmethod
    def normalize_header(cls, value: str) -> str:
        """Reject a blank header name and drop surrounding whitespace."""
        header = value.strip()
        if not header:
            raise ValueError("token.header must not be empty")
        return header


class OidcConfig(StrictConfig):
    """OIDC verification settings."""

    issuer: str = ""
    audience: str = ""
    client_id: str = ""


class RegisterEmailConfig(StrictConfig):
    """Email-verification behaviour for self-service registration."""

    skip_verify: bool = True


class RegisterConfig(StrictConfig):
    """Self-service registration availability and behaviour.

    Exposed to YAML as the ``register:`` section via an alias: a field literally
    named ``register`` shadows ``ModelMetaclass.register`` and makes pydantic
    emit a shadowing warning.
    """

    enabled: bool = True
    email: RegisterEmailConfig = Field(default_factory=RegisterEmailConfig)


class AclConfig(StrictConfig):
    """ACL limits and cache settings."""

    max_entries: PositiveInt = 1000
    max_user_grants: PositiveInt = 10000
    cache_enabled: bool = False
    cache_ttl_seconds: PositiveInt = 30


class CorsConfig(StrictConfig):
    """Browser cross-origin policy for the HTTP adapter."""

    allow_origins: tuple[str, ...] = (
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:4173",
        "http://127.0.0.1:4173",
    )
    allow_credentials: bool = True


class AppConfig(StrictConfig):
    """Complete, validated configuration assembled from YAML overlays."""

    configuration: ConfigurationConfig = Field(default_factory=ConfigurationConfig)
    app: AppInfoConfig = Field(default_factory=AppInfoConfig)
    api: ApiConfig = Field(default_factory=ApiConfig)
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    server: ServerConfig = Field(default_factory=ServerConfig)
    cors: CorsConfig = Field(default_factory=CorsConfig)
    password_policy: PasswordPolicyConfig = Field(default_factory=PasswordPolicyConfig)
    token: TokenConfig = Field(default_factory=TokenConfig)
    oidc: OidcConfig = Field(default_factory=OidcConfig)
    registration: RegisterConfig = Field(
        default_factory=RegisterConfig, alias="register"
    )
    acl: AclConfig = Field(default_factory=AclConfig)


def default_config_dir() -> Path:
    """Return the repository/package configuration directory."""
    return Path(__file__).resolve().parents[2] / "config"


def repository_root() -> Path:
    """Return the repository root used to resolve relative runtime paths."""
    return default_config_dir().parents[1]
