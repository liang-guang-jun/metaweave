"""Serve the built single-page frontend from the HTTP root."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException
from starlette.responses import Response
from starlette.types import Scope

from ...kernel.infrastructure.logging import get_logger
from ..bootstrap.config import AppConfig, repository_root


class SpaStaticFiles(StaticFiles):
    """Static files that fall back to ``index.html`` for client-side routes.

    A single-page app owns routes such as ``/login`` that have no matching file
    on disk. Only browser navigations (``Accept: text/html``) receive the shell;
    API clients asking for JSON keep the original ``404`` so missing endpoints
    are not silently masked by the frontend.
    """

    async def get_response(self, path: str, scope: Scope) -> Response:
        """Serve a real asset, else the SPA shell for HTML navigations."""
        try:
            return await super().get_response(path, scope)
        except HTTPException as error:
            if error.status_code != 404 or not _accepts_html(scope):
                raise
            return await super().get_response("index.html", scope)


def mount_frontend(app: FastAPI, config: AppConfig) -> None:
    """Mount the built SPA at ``/`` when static frontend delivery is enabled.

    The mount is registered after the API routers, so ``/healthz``, ``/iam``,
    ``/catalog`` and friends always win over the catch-all static route.
    """
    logger = get_logger("server.http")
    frontend = config.app.frontend
    if frontend is None or frontend.type != "static":
        return
    directory = _resolve_directory(frontend.path)
    if not directory.is_dir():
        logger.warning("frontend.assets.missing", path=str(directory))
        return
    app.mount("/", SpaStaticFiles(directory=directory, html=True), name="frontend")
    logger.info("frontend.mounted", path=str(directory))


def _resolve_directory(path: Path) -> Path:
    """Resolve a configured directory against the repository root."""
    return path if path.is_absolute() else repository_root() / path


def _accepts_html(scope: Scope) -> bool:
    """Report whether the client prefers an HTML document response."""
    for name, value in scope.get("headers", []):
        if name.lower() == b"accept":
            return b"text/html" in value.lower()
    return False
