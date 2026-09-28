"""Validated application configuration and structured database settings."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    PositiveInt,
    field_validator,
    model_validator,
)


class StrictConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)


class ProfileConfig(StrictConfig):
    priority: int = Field(ge=1)


class ConfigurationConfig(StrictConfig):
    profiles: dict[str, ProfileConfig] = Field(default_factory=dict)

    @field_validator("profiles")
    @classmethod
    def profile_tags_are_valid(
        cls, profiles: dict[str, ProfileConfig]
    ) -> dict[str, ProfileConfig]:
        for tag in profiles:
            if not tag or not tag.replace("-", "").replace("_", "").isalnum():
                raise ValueError(
                    "profile tags must contain only letters, digits, '_' or '-'"
                )
        return profiles


class DatabaseAuthConfig(StrictConfig):
    type: Literal["none", "password", "databricks_app"] = "none"


class DatabasePoolConfig(StrictConfig):
    size: int = Field(5, ge=0)
    max_overflow: int = Field(10, ge=0)
    timeout_seconds: PositiveInt = 30
    recycle_seconds: int = Field(1800, ge=-1)


class DatabaseOptionsConfig(StrictConfig):
    busy_timeout_ms: PositiveInt = 5000


class DatabaseConfig(StrictConfig):
    provider: Literal["sqlite", "postgresql", "databricks_lakebase"] = "sqlite"
    driver: Literal["aiosqlite", "asyncpg", "psycopg"] = "aiosqlite"
    host: str = ""
    port: int = Field(0, ge=0, le=65535)
    database: str = ":memory:"
    username: str = ""
    password: str = ""
    auth: DatabaseAuthConfig = Field(default_factory=DatabaseAuthConfig)
    sslmode: str = ""
    echo: bool = False
    pool: DatabasePoolConfig = Field(default_factory=DatabasePoolConfig)
    options: DatabaseOptionsConfig = Field(default_factory=DatabaseOptionsConfig)

    @model_validator(mode="after")
    def validate_provider_driver_auth(self) -> DatabaseConfig:
        expected = {
            "sqlite": ("aiosqlite", "none"),
            "postgresql": ("asyncpg", "password"),
            "databricks_lakebase": ("asyncpg", "databricks_app"),
        }[self.provider]
        if self.driver != expected[0] or self.auth.type != expected[1]:
            raise ValueError(
                f"{self.provider} requires driver '{expected[0]}' and "
                f"database.auth.type='{expected[1]}'"
            )
        if self.provider == "postgresql":
            if not self.host or not self.database or self.database == ":memory:":
                raise ValueError(
                    "postgresql requires database.host and database.database"
                )
            if not self.username or not self.password:
                raise ValueError(
                    "postgresql password authentication requires username and password"
                )
        return self

    @property
    def dialect(self) -> str:
        return "sqlite" if self.provider == "sqlite" else "postgresql"

    @property
    def driver_is_async(self) -> bool:
        return self.driver in {"aiosqlite", "asyncpg", "psycopg"}


class LoggingConfig(StrictConfig):
    level: str = "INFO"
    json_output: bool = Field(False, alias="json")
    colors: bool = True
    silenced_loggers: tuple[str, ...] = ()
    log_request_headers: bool = False


class ApiConfig(StrictConfig):
    prefix: str = ""

    @field_validator("prefix")
    @classmethod
    def normalize_prefix(cls, prefix: str) -> str:
        trimmed = prefix.strip().strip("/")
        return f"/{trimmed}" if trimmed else ""


class CorsConfig(StrictConfig):
    allow_origins: tuple[str, ...] = (
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:4173",
        "http://127.0.0.1:4173",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
    )
    allow_credentials: bool = True


class ServerConfig(StrictConfig):
    host: str = "127.0.0.1"
    port: int = Field(8000, ge=1, le=65535)
    reload: bool = False
    api: ApiConfig = Field(default_factory=ApiConfig)
    cors: CorsConfig = Field(default_factory=CorsConfig)


class FrontendConfig(StrictConfig):
    type: Literal["static", "disabled"] = "static"
    path: Path = Path("dist/client")


class AppInfoConfig(StrictConfig):
    name: str = "metaweave"
    debug: bool = False
    frontend: FrontendConfig | None = None


class PasswordConfig(StrictConfig):
    min_length: PositiveInt = 12
    require_upper: bool = True
    require_digit: bool = True
    require_symbol: bool = True


class LoginConfig(StrictConfig):
    max_failures: PositiveInt = 5
    lockout_seconds: PositiveInt = 300


class TokenConfig(StrictConfig):
    issuer: str = "iam"
    audience: str = "business-api"
    secret: str = "development-only-change-me"
    header: str = "X-Bearer-Token"
    access_ttl_seconds: PositiveInt = 3600
    refresh_ttl_seconds: PositiveInt = 2592000

    @field_validator("header")
    @classmethod
    def normalize_header(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("iam.token.header must not be empty")
        return value


class RegisterEmailConfig(StrictConfig):
    skip_verify: bool = True


class RegistrationConfig(StrictConfig):
    enabled: bool = True
    email: RegisterEmailConfig = Field(default_factory=RegisterEmailConfig)


class IdentityProviderConfig(StrictConfig):
    enabled: bool = True


class DatabricksAppsHeadersConfig(StrictConfig):
    email: str = "X-Forwarded-Email"
    access_token: str = "X-Forwarded-Access-Token"

    @field_validator("email", "access_token")
    @classmethod
    def validate_header(cls, value: str) -> str:
        import re

        value = value.strip()
        if not re.fullmatch(r"[!#$%&'*+.^_`|~0-9A-Za-z-]+", value):
            raise ValueError("invalid HTTP header name")
        return value


class DatabricksAppsProviderConfig(IdentityProviderConfig):
    ignore_status: bool = False
    headers: DatabricksAppsHeadersConfig = Field(
        default_factory=DatabricksAppsHeadersConfig
    )


class IdentityProvidersConfig(StrictConfig):
    local: IdentityProviderConfig = Field(default_factory=IdentityProviderConfig)
    databricksapps: DatabricksAppsProviderConfig = Field(
        default_factory=DatabricksAppsProviderConfig
    )


class IdentityConfig(StrictConfig):
    providers: IdentityProvidersConfig = Field(default_factory=IdentityProvidersConfig)


class AclCacheConfig(StrictConfig):
    enabled: bool = False
    ttl_seconds: PositiveInt = 30


class AclConfig(StrictConfig):
    max_entries: PositiveInt = 1000
    max_user_grants: PositiveInt = 10000
    cache: AclCacheConfig = Field(default_factory=AclCacheConfig)


class IamConfig(StrictConfig):
    identity: IdentityConfig = Field(default_factory=IdentityConfig)
    registration: RegistrationConfig = Field(default_factory=RegistrationConfig)
    password: PasswordConfig = Field(default_factory=PasswordConfig)
    login: LoginConfig = Field(default_factory=LoginConfig)
    token: TokenConfig = Field(default_factory=TokenConfig)
    acl: AclConfig = Field(default_factory=AclConfig)


class AppConfig(StrictConfig):
    configuration: ConfigurationConfig = Field(default_factory=ConfigurationConfig)
    app: AppInfoConfig = Field(default_factory=AppInfoConfig)
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    server: ServerConfig = Field(default_factory=ServerConfig)
    iam: IamConfig = Field(default_factory=IamConfig)


def default_config_dir() -> Path:
    return Path(__file__).resolve().parents[2] / "config"


def repository_root() -> Path:
    return default_config_dir().parents[1]
