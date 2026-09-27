"""Tenant membership routes with their schemas."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel

from ...application.messages import (
    AcceptInvitation,
    CreateTenant,
    DisableMembership,
    InviteMember,
    RestoreMembership,
    SearchTenantMemberships,
)
from ...domain.value_objects import MembershipId, TenantId, TenantMembershipType, UserId
from ....app.http.dependencies import (
    AuthenticatedPrincipal,
    get_authenticated_identity,
    get_current_principal,
    get_message_bus,
)
from ....kernel.application.messaging.bus import MessageBus
from ....kernel.application.common.page import PageRequest
from .common import membership_response

router = APIRouter(prefix="/tenants", tags=["iam.memberships"])


class CreateTenantRequest(BaseModel):
    name: str
    description: str = ""
    owner_user_id: UUID | None = None


class TenantResponse(BaseModel):
    tenant_id: UUID


class InviteMemberRequest(BaseModel):
    user_id: UUID
    is_admin: bool = False
    membership_type: TenantMembershipType | None = None


class MembershipResponse(BaseModel):
    membership_id: UUID
    tenant_id: UUID
    user_id: UUID
    active: bool = False
    is_admin: bool = False
    email: str | None = None
    membership_type: str = "MEMBER"


class MembershipPageResponse(BaseModel):
    items: list[MembershipResponse]
    total: int
    page: int
    size: int
    pages: int
    has_next: bool


@router.post("", response_model=TenantResponse, status_code=status.HTTP_201_CREATED)
async def create_tenant(
    request: CreateTenantRequest,
    bus: Annotated[MessageBus, Depends(get_message_bus)],
    principal: Annotated[AuthenticatedPrincipal, Depends(get_authenticated_identity)],
) -> TenantResponse:
    """Create a tenant and optionally invite its owner."""
    result = await bus.send(
        CreateTenant(
            request.name,
            UserId(request.owner_user_id)
            if request.owner_user_id
            else UserId(principal.user_id),
        )
    )
    return TenantResponse(tenant_id=result.value)


@router.get("/{tenant_id}/memberships", response_model=MembershipPageResponse)
async def list_tenant_memberships(
    tenant_id: UUID,
    bus: Annotated[MessageBus, Depends(get_message_bus)],
    principal: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
    keyword: str = Query(default="", max_length=320),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
) -> MembershipPageResponse:
    """Search tenant memberships by user email or user id."""
    if principal.tenant_id != tenant_id:
        raise HTTPException(status_code=403, detail="tenant context mismatch")
    result = await bus.ask(
        SearchTenantMemberships(TenantId(tenant_id), keyword, PageRequest(page, size))
    )
    return MembershipPageResponse(
        items=[
            MembershipResponse(
                membership_id=item.membership_id.value,
                tenant_id=item.tenant_id.value,
                user_id=item.user_id.value,
                active=item.active,
                is_admin=item.is_admin,
                email=item.email,
                membership_type=item.membership_type.value,
            )
            for item in result.items
        ],
        total=result.total,
        page=result.page,
        size=result.size,
        pages=result.pages,
        has_next=result.has_next,
    )


@router.post(
    "/{tenant_id}/memberships",
    response_model=MembershipResponse,
    status_code=status.HTTP_201_CREATED,
)
async def invite_member(
    tenant_id: UUID,
    request: InviteMemberRequest,
    bus: Annotated[MessageBus, Depends(get_message_bus)],
    _: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
) -> MembershipResponse:
    """Invite a user to a tenant."""
    result = await bus.send(
        InviteMember(
            TenantId(tenant_id),
            UserId(request.user_id),
            request.is_admin,
            request.membership_type,
        )
    )
    return MembershipResponse(
        membership_id=result.value,
        tenant_id=tenant_id,
        user_id=request.user_id,
        is_admin=request.is_admin,
        membership_type=(
            request.membership_type
            or (
                TenantMembershipType.ADMIN
                if request.is_admin
                else TenantMembershipType.MEMBER
            )
        ).value,
    )


@router.post(
    "/memberships/{membership_id}/accept", status_code=status.HTTP_204_NO_CONTENT
)
async def accept_invitation(
    membership_id: UUID,
    bus: Annotated[MessageBus, Depends(get_message_bus)],
    _: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
) -> None:
    """Accept a pending tenant membership invitation."""
    await bus.send(AcceptInvitation(MembershipId(membership_id)))


@router.post(
    "/{tenant_id}/memberships/{membership_id}/disable",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def disable_membership(
    tenant_id: UUID,
    membership_id: UUID,
    bus: Annotated[MessageBus, Depends(get_message_bus)],
    principal: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
) -> None:
    """Disable a tenant membership without deleting its history."""
    if principal.tenant_id != tenant_id:
        raise HTTPException(status_code=403, detail="tenant context mismatch")
    await bus.send(DisableMembership(MembershipId(membership_id)))


@router.post(
    "/{tenant_id}/memberships/{membership_id}/restore",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def restore_membership(
    tenant_id: UUID,
    membership_id: UUID,
    bus: Annotated[MessageBus, Depends(get_message_bus)],
    principal: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
) -> None:
    """Restore a previously disabled tenant membership."""
    if principal.tenant_id != tenant_id:
        raise HTTPException(status_code=403, detail="tenant context mismatch")
    await bus.send(RestoreMembership(MembershipId(membership_id)))
