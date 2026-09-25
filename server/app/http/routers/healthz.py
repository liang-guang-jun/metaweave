"""Service liveness endpoint."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from ...bootstrap.container import Container
from ..dependencies import get_container

router = APIRouter(tags=["system"])


class HealthzResponse(BaseModel):
    """Liveness response returned by the health probe."""

    status: str


@router.get("/healthz", response_model=HealthzResponse)
async def healthz(
    container: Annotated[Container, Depends(get_container)],
) -> HealthzResponse:
    """Report that the HTTP process is running and has a composed container."""
    return HealthzResponse(status="ok")
