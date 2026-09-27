"""FastAPI application factory and lifecycle wiring."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError

from ...catalog.interface.http import router as catalog_router
from ...iam.domain.errors import IamDomainError
from ...iam.interface.http import router as iam_router
from ...kernel.infrastructure.logging import get_logger
from ..bootstrap.container import Container
from ..bootstrap.factory import create_factory
from .middleware import HttpLoggingMiddleware
from .routers.healthz import router as healthz_router


def create_app(container: Container | None = None) -> FastAPI:
    """Create FastAPI and mount one fully built application container in state."""
    resolved_container = container or create_factory()
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
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://localhost:4173",
            "http://127.0.0.1:4173",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(IamDomainError)
    async def handle_iam_error(_: Request, error: IamDomainError) -> JSONResponse:
        """Translate domain validation/authentication failures into HTTP errors."""
        if str(error) == "invalid credentials":
            return JSONResponse(
                status_code=401,
                content={"detail": "invalid credentials"},
                headers={"WWW-Authenticate": "Bearer"},
            )
        return JSONResponse(status_code=400, content={"detail": str(error)})

    @app.exception_handler(IntegrityError)
    async def handle_integrity_error(_: Request, error: IntegrityError) -> JSONResponse:
        """Expose persistence uniqueness races as a transport-level conflict."""
        return JSONResponse(
            status_code=409,
            content={"detail": "resource conflict"},
        )

    app.state.container = resolved_container
    app.add_middleware(HttpLoggingMiddleware, config=config.logging)
    app.include_router(healthz_router)
    app.include_router(iam_router)
    app.include_router(catalog_router)
    return app
