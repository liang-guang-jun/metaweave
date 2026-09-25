"""FastAPI dependencies shared by HTTP routers."""

from __future__ import annotations

from typing import cast

from fastapi import Request

from ..bootstrap.container import Container


def get_container(request: Request) -> Container:
    """Return the composition-root container mounted on this FastAPI app."""
    return cast(Container, request.app.state.container)
