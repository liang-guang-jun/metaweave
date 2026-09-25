"""FastAPI application factory and lifecycle wiring."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from ...kernel.infrastructure.logging import get_logger
from ..bootstrap.container import Container
from ..bootstrap.factory import create_container
from .middleware import HttpLoggingMiddleware
from .routers.healthz import router as healthz_router


def create_app(container: Container | None = None) -> FastAPI:
    """Create FastAPI and mount one fully built application container in state."""
    resolved_container = container or create_container()
    config = resolved_container.config()

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncGenerator[None]:
        """Dispose external resources when the ASGI process terminates."""
        logger = get_logger("server.http")
        logger.info("application.started", app_name=config.app.name)
        try:
            yield
        finally:
            logger.info("application.stopping", app_name=config.app.name)
            await resolved_container.engine().dispose()
            resolved_container.shutdown_resources()
            logger.info("application.stopped", app_name=config.app.name)

    app = FastAPI(title=config.app.name, debug=config.app.debug, lifespan=lifespan)
    app.state.container = resolved_container
    app.add_middleware(HttpLoggingMiddleware, config=config.logging)
    app.include_router(healthz_router)
    return app
