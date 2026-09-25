"""Build a fully configured dependency container from application settings."""

from __future__ import annotations

from ...kernel.infrastructure.logging import LoggingBehavior, configure_logging
from ...kernel.infrastructure.persistence.sqlalchemy import (
    create_async_engine,
    create_session_factory,
)
from .config import AppConfig
from .container import Container
from .loader import load_config


def create_container(config: AppConfig | None = None) -> Container:
    """Load configuration, configure logging, and wire infrastructure providers."""
    resolved_config = config or load_config()
    configure_logging(resolved_config.logging)
    engine = create_async_engine(
        resolved_config.database.url,
        echo=resolved_config.database.echo,
        sqlite_busy_timeout_ms=resolved_config.database.busy_timeout_ms,
    )
    container = Container()
    container.config.override(resolved_config)
    container.engine.override(engine)
    container.session_factory.override(create_session_factory(engine))
    container.behaviors().register_global(LoggingBehavior())
    return container
