"""Database backend resolution and dynamic credential providers."""
# ruff: noqa: D102, D107

from __future__ import annotations

import asyncio
import os
import ssl
from collections.abc import Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

from sqlalchemy import URL
from sqlalchemy.ext.asyncio import AsyncEngine

from .database import create_async_engine

if TYPE_CHECKING:
    from databricks.sdk import WorkspaceClient

    from .....app.bootstrap.config import DatabaseConfig


class DatabaseConfigurationError(RuntimeError):
    """Raised when effective backend configuration cannot be resolved safely."""


class DatabaseCredentialProvider(Protocol):
    """Return credentials only when a physical connection needs them."""

    async def password(self) -> str | None: ...


class NoDatabaseCredentialProvider:
    """Use no database password for SQLite."""

    async def password(self) -> None:
        return None


class StaticPasswordCredentialProvider:
    """Return the configured PostgreSQL password without exposing it elsewhere."""

    def __init__(self, password: str) -> None:
        self._password = password

    async def password(self) -> str:
        return self._password


class DatabricksLakebaseCredentialProvider:
    """Generate a fresh App service-principal database token per new connection."""

    def __init__(self, workspace: WorkspaceClient, endpoint: str) -> None:
        self._workspace = workspace
        self._endpoint = endpoint

    async def password(self) -> str:
        credential = await asyncio.to_thread(
            self._workspace.postgres.generate_database_credential,
            endpoint=self._endpoint,
        )
        if not credential.token:
            raise DatabaseConfigurationError(
                "Databricks Lakebase returned an empty database credential"
            )
        return credential.token


@dataclass(frozen=True, slots=True)
class DatabaseConnectionInfo:
    """Resolved non-secret metadata needed to create a database connection."""

    drivername: str
    host: str | None
    port: int | None
    database: str | None
    username: str | None
    sslmode: str

    def url(self) -> URL:
        """Build a password-free URL so secrets never enter engine state/logs."""
        return URL.create(
            self.drivername,
            username=self.username,
            host=self.host,
            port=self.port,
            database=self.database,
            query={"sslmode": self.sslmode} if self.sslmode else {},
        )


class DatabaseBackend(Protocol):
    """Resolve provider-specific settings and create its SQLAlchemy engine."""

    def url(self) -> URL: ...

    def create_engine(self) -> AsyncEngine: ...


def _required(environment: Mapping[str, str], *names: str) -> dict[str, str]:
    values = {name: environment.get(name, "").strip() for name in names}
    missing = [name for name, value in values.items() if not value]
    if missing:
        raise DatabaseConfigurationError(
            "Databricks Lakebase requires runtime environment variables: "
            + ", ".join(missing)
        )
    return values


def _ssl_context(sslmode: str) -> ssl.SSLContext | bool | None:
    """Map PostgreSQL SSL modes to asyncpg's supported TLS values."""
    if sslmode in {"", "disable"}:
        return False if sslmode == "disable" else None
    context = ssl.create_default_context()
    if sslmode in {"allow", "prefer", "require"}:
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
    elif sslmode not in {"verify-ca", "verify-full"}:
        raise DatabaseConfigurationError(f"Unsupported PGSSLMODE: {sslmode}")
    return context


class SqliteDatabaseBackend:
    """Create the local SQLite engine with its existing PRAGMA options."""

    def __init__(self, config: DatabaseConfig) -> None:
        self._config = config

    def url(self) -> URL:
        return URL.create("sqlite+aiosqlite", database=self._config.database)

    def create_engine(self) -> AsyncEngine:
        return create_async_engine(
            self.url(),
            echo=self._config.echo,
            sqlite_busy_timeout_ms=self._config.options.busy_timeout_ms,
        )


class PostgresqlDatabaseBackend:
    """Create static-password asyncpg PostgreSQL connections."""

    def __init__(self, config: DatabaseConfig) -> None:
        self._config = config
        self._credentials = StaticPasswordCredentialProvider(config.password)

    def url(self) -> URL:
        return DatabaseConnectionInfo(
            "postgresql+asyncpg",
            self._config.host,
            self._config.port or None,
            self._config.database,
            self._config.username,
            self._config.sslmode,
        ).url()

    def create_engine(self) -> AsyncEngine:
        return _create_postgres_engine(self.url(), self._config, self._credentials)


class DatabricksLakebaseDatabaseBackend:
    """Resolve Databricks App metadata and refresh OAuth tokens per connection."""

    def __init__(
        self,
        config: DatabaseConfig,
        workspace: WorkspaceClient,
        environment: Mapping[str, str] | None = None,
    ) -> None:
        self._config = config
        values = _required(
            environment or os.environ,
            "PGHOST",
            "PGPORT",
            "PGDATABASE",
            "PGUSER",
            "PGSSLMODE",
            "LAKEBASE_ENDPOINT",
        )
        try:
            port = int(values["PGPORT"])
        except ValueError as error:
            raise DatabaseConfigurationError("PGPORT must be an integer") from error
        if not 1 <= port <= 65535:
            raise DatabaseConfigurationError("PGPORT must be between 1 and 65535")
        self._info = DatabaseConnectionInfo(
            "postgresql+asyncpg",
            values["PGHOST"],
            port,
            values["PGDATABASE"],
            values["PGUSER"],
            values["PGSSLMODE"],
        )
        self._credentials = DatabricksLakebaseCredentialProvider(
            workspace, values["LAKEBASE_ENDPOINT"]
        )

    def url(self) -> URL:
        return self._info.url()

    def create_engine(self) -> AsyncEngine:
        return _create_postgres_engine(self.url(), self._config, self._credentials)


def _create_postgres_engine(
    url: URL, config: DatabaseConfig, credentials: DatabaseCredentialProvider
) -> AsyncEngine:
    """Create asyncpg connections with credentials supplied at pool expansion time."""

    async def connect() -> object:
        import asyncpg  # type: ignore[import-untyped]

        password = await credentials.password()
        return await asyncpg.connect(
            host=url.host,
            port=url.port,
            user=url.username,
            password=password,
            database=url.database,
            ssl=_ssl_context(config.sslmode),
        )

    return create_async_engine(
        url,
        echo=config.echo,
        pool_size=config.pool.size,
        max_overflow=config.pool.max_overflow,
        pool_timeout=config.pool.timeout_seconds,
        pool_recycle=config.pool.recycle_seconds,
        async_creator=connect,
    )


def create_database_backend(
    config: DatabaseConfig,
    *,
    workspace: WorkspaceClient | None = None,
    environment: Mapping[str, str] | None = None,
) -> DatabaseBackend:
    """Select the sole provider-specific branch for the application."""
    if config.provider == "sqlite":
        return SqliteDatabaseBackend(config)
    if config.provider == "postgresql":
        return PostgresqlDatabaseBackend(config)
    if workspace is None:
        raise DatabaseConfigurationError(
            "databricks_lakebase requires an injected WorkspaceClient"
        )
    return DatabricksLakebaseDatabaseBackend(config, workspace, environment)
