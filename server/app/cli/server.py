"""Run the Metaweave FastAPI process through Uvicorn."""

from __future__ import annotations

from typing import Annotated

import typer
import uvicorn

from ...kernel.infrastructure.logging import configure_logging, get_logger
from ..bootstrap import create_container, load_config
from ..http import create_app
from .db import apply_migrations


def serve(
    host: Annotated[
        str | None, typer.Option(help="Interface on which to listen.")
    ] = None,
    port: Annotated[
        int | None, typer.Option(min=1, max=65535, help="TCP port to listen on.")
    ] = None,
    reload: Annotated[
        bool | None, typer.Option(help="Enable Uvicorn code reloading.")
    ] = None,
    upgrade_db: Annotated[
        bool,
        typer.Option(
            "--upgrade-db",
            help="Apply Alembic migrations to the served database before serving.",
        ),
    ] = False,
) -> None:
    """Build the application and run its ASGI server using YAML defaults."""
    config = load_config()
    resolved_host = host if host is not None else config.server.host
    resolved_port = port if port is not None else config.server.port
    resolved_reload = reload if reload is not None else config.server.reload
    configure_logging(config.logging)
    logger = get_logger("server.http")
    logger.info(
        "server.listening",
        address=f"http://{resolved_host}:{resolved_port}",
        reload=resolved_reload,
    )
    if resolved_reload:
        if upgrade_db:
            # The reloader serves from a child process, so migrate before it
            # starts: a file-backed database is shared with that child while an
            # in-memory one is not.
            logger.info("database.migrations.applying", revision="head")
            apply_migrations(
                create_container(config).engine(),
                dispose_after=config.database.provider != "sqlite",
            )
        uvicorn.run(
            "server.app.http.app:create_app",
            factory=True,
            host=resolved_host,
            port=resolved_port,
            reload=True,
            log_config=None,
        )
        return
    container = create_container(config)
    if upgrade_db:
        logger.info("database.migrations.applying", revision="head")
        apply_migrations(
            container.engine(),
            dispose_after=config.database.provider != "sqlite",
        )
    uvicorn.run(
        create_app(container), host=resolved_host, port=resolved_port, log_config=None
    )
