"""Authenticated user self-service routes with their schemas."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from ...application.messages import GetCurrentUser
from ...domain.value_objects import UserId
from ....app.http.dependencies import (
    AuthenticatedPrincipal,
    get_authenticated_identity,
    get_message_bus,
)
from ....kernel.application.messaging.bus import MessageBus

router = APIRouter(tags=["iam.me"])


class CurrentUserResponse(BaseModel):
    """Profile of the authenticated user."""

    user_id: UUID
    email: str
    active: bool


@router.get("/me", response_model=CurrentUserResponse)
async def get_current_user(
    bus: Annotated[MessageBus, Depends(get_message_bus)],
    principal: Annotated[AuthenticatedPrincipal, Depends(get_authenticated_identity)],
) -> CurrentUserResponse:
    """Return the profile of the user behind the bearer token."""
    result = await bus.ask(GetCurrentUser(UserId(principal.user_id)))
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )
    return CurrentUserResponse(
        user_id=result.user_id.value,
        email=result.email,
        active=result.active,
    )
