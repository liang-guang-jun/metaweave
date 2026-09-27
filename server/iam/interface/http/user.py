"""User registration and verification routes with their schemas."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel, Field

from ...application.messages import (
    DisablePrincipal,
    ListUserMemberships,
    RegisterUser,
    RestorePrincipal,
    SearchUsers,
    VerifyUser,
)
from ...domain.value_objects import Subject, SubjectType, UserId
from ....app.http.dependencies import (
    AuthenticatedPrincipal,
    get_current_principal,
    get_authenticated_identity,
    get_message_bus,
)
from ....kernel.application.messaging.bus import MessageBus
from ....kernel.application.common.page import PageRequest
from .common import membership_response

router = APIRouter(prefix="/users", tags=["iam.users"])


class RegisterUserRequest(BaseModel):
    email: str = Field(min_length=3)
    password: str = Field(min_length=1)


class UserResponse(BaseModel):
    user_id: UUID


class UserMembershipResponse(BaseModel):
    membership_id: UUID
    tenant_id: UUID
    user_id: UUID
    active: bool
    is_admin: bool


class UserDirectoryItem(BaseModel):
    user_id: UUID
    email: str
    active: bool


class UserPageResponse(BaseModel):
    items: list[UserDirectoryItem]
    total: int
    page: int
    size: int
    pages: int
    has_next: bool


@router.get("", response_model=UserPageResponse)
async def search_users(
    bus: Annotated[MessageBus, Depends(get_message_bus)],
    _: Annotated[AuthenticatedPrincipal, Depends(get_authenticated_identity)],
    keyword: str = Query(default="", max_length=320),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
) -> UserPageResponse:
    """Search users for tenant invitations and group membership selection."""
    result = await bus.ask(SearchUsers(keyword, PageRequest(page, size)))
    return UserPageResponse(
        items=[
            UserDirectoryItem(
                user_id=item.user_id.value,
                email=item.email,
                active=item.active,
            )
            for item in result.items
        ],
        total=result.total,
        page=result.page,
        size=result.size,
        pages=result.pages,
        has_next=result.has_next,
    )


@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register_user(
    request: RegisterUserRequest,
    bus: Annotated[MessageBus, Depends(get_message_bus)],
) -> UserResponse:
    """Register a user account."""
    result = await bus.send(RegisterUser(str(request.email), request.password))
    return UserResponse(user_id=result.value)


@router.post("/{user_id}/verify", status_code=status.HTTP_204_NO_CONTENT)
async def verify_user(
    user_id: UUID,
    bus: Annotated[MessageBus, Depends(get_message_bus)],
) -> None:
    """Verify a user account."""
    await bus.send(VerifyUser(UserId(user_id)))


@router.post("/{user_id}/disable", status_code=status.HTTP_204_NO_CONTENT)
async def disable_user(
    user_id: UUID,
    bus: Annotated[MessageBus, Depends(get_message_bus)],
    _: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
) -> None:
    """Disable a user account. Instance-administrator authorization is enforced by the handler."""
    await bus.send(DisablePrincipal(Subject(UserId(user_id), SubjectType.USER)))


@router.post("/{user_id}/restore", status_code=status.HTTP_204_NO_CONTENT)
async def restore_user(
    user_id: UUID,
    bus: Annotated[MessageBus, Depends(get_message_bus)],
    _: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
) -> None:
    """Restore a disabled user account. Instance-admin authorization is handler-owned."""
    await bus.send(RestorePrincipal(Subject(UserId(user_id), SubjectType.USER)))


@router.get("/{user_id}/memberships", response_model=list[UserMembershipResponse])
async def list_user_memberships(
    user_id: UUID,
    bus: Annotated[MessageBus, Depends(get_message_bus)],
    _: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
) -> list[UserMembershipResponse]:
    """List tenant memberships from the read model."""
    result = await bus.ask(ListUserMemberships(UserId(user_id)))
    return [
        UserMembershipResponse.model_validate(membership_response(item))
        for item in result
    ]
