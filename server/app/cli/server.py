"""Run the Metaweave FastAPI process through Uvicorn."""

from __future__ import annotations

from typing import Annotated

import typer
import uvicorn

from ...kernel.infrastructure.logging import configure_logging, get_logger
from ..bootstrap import create_container, load_config
from ..http import create_app


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
) -> None:
    """Build the application and run its ASGI server using YAML defaults."""
    config = load_config()
    resolved_host = host if host is not None else config.server.host
    resolved_port = port if port is not None else config.server.port
    resolved_reload = reload if reload is not None else config.server.reload
    configure_logging(config.logging)
    get_logger("server.http").info(
        "server.listening",
        address=f"http://{resolved_host}:{resolved_port}",
        reload=resolved_reload,
    )
    if resolved_reload:
        uvicorn.run(
            "server.app.http.app:create_app",
            factory=True,
            host=resolved_host,
            port=resolved_port,
            reload=True,
            log_config=None,
        )
        return
    app = create_app(create_container(config))
    uvicorn.run(app, host=resolved_host, port=resolved_port, log_config=None)
