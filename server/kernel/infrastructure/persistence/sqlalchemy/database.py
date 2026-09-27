"""Driver-neutral async SQLAlchemy engine and session construction."""

from __future__ import annotations

from typing import Protocol, cast

from sqlalchemy import event
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
)
from sqlalchemy.ext.asyncio import (
    create_async_engine as sqlalchemy_create_async_engine,
)


def create_async_engine(
    url: str,
    *,
    echo: bool = False,
    sqlite_busy_timeout_ms: int | None = None,
) -> AsyncEngine:
    """Build an async engine for any SQLAlchemy-supported async dialect.

    SQLite receives its safe single-node PRAGMAs when selected. Other drivers,
    such as ``postgresql+asyncpg``, are passed directly to SQLAlchemy without
    SQLite-specific validation or connection hooks.
    """
    parsed_url = make_url(url)
    engine = sqlalchemy_create_async_engine(url, echo=echo)
    if parsed_url.get_backend_name() != "sqlite":
        return engine

    class _Cursor(Protocol):
        def close(self) -> None: ...

        def execute(self, statement: str) -> object: ...

    class _CursorConnection(Protocol):
        def cursor(self) -> _Cursor: ...

    @event.listens_for(engine.sync_engine, "connect")
    def _configure_connection(dbapi_connection: object, _: object) -> None:
        cursor = cast(_CursorConnection, dbapi_connection).cursor()
        try:
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA journal_mode=WAL")
            if sqlite_busy_timeout_ms is not None:
                cursor.execute(f"PRAGMA busy_timeout={sqlite_busy_timeout_ms}")
        finally:
            cursor.close()

    return engine


def create_session_factory(
    engine: AsyncEngine,
) -> async_sessionmaker[AsyncSession]:
    """Create non-expiring sessions appropriate for aggregate reconstitution."""
    return async_sessionmaker(engine, expire_on_commit=False)
