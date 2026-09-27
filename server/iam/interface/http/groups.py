"""Group routes with their schemas."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel

from ...application.messages import (
    AddGroupMember,
    CreateGroup,
    RestoreGroupMember,
    RemoveGroupMember,
    SearchGroupMemberships,
    SearchGroups,
)
from ...domain.value_objects import (
    GroupId,
    GroupMembershipId,
    GroupMemberType,
    TenantId,
    UserId,
)
from ....app.http.dependencies import (
    AuthenticatedPrincipal,
    get_current_principal,
    get_message_bus,
)
from ....kernel.application.messaging.bus import MessageBus
from ....kernel.application.common.page import PageRequest

router = APIRouter(prefix="/tenants/{tenant_id}/groups", tags=["iam.groups"])


class CreateGroupRequest(BaseModel):
    name: str


class AddGroupMemberRequest(BaseModel):
    member_id: UUID
    member_type: GroupMemberType = GroupMemberType.USER


class GroupDirectoryItem(BaseModel):
    group_id: UUID
    tenant_id: UUID
    name: str


class GroupPageResponse(BaseModel):
    items: list[GroupDirectoryItem]
    total: int
    page: int
    size: int
    pages: int
    has_next: bool


class GroupMembershipResponse(BaseModel):
    membership_id: UUID
    group_id: UUID
    member_id: UUID
    member_type: str
    active: bool
    display_name: str | None = None


class GroupMembershipPageResponse(BaseModel):
    items: list[GroupMembershipResponse]
    total: int
    page: int
    size: int
    pages: int
    has_next: bool


@router.get("", response_model=GroupPageResponse)
async def search_groups(
    tenant_id: UUID,
    bus: Annotated[MessageBus, Depends(get_message_bus)],
    principal: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
    keyword: str = Query(default="", max_length=255),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
) -> GroupPageResponse:
    """Search groups in the selected tenant for navigation or nesting."""
    if principal.tenant_id != tenant_id:
        raise HTTPException(status_code=403, detail="tenant context mismatch")
    result = await bus.ask(
        SearchGroups(TenantId(tenant_id), keyword, PageRequest(page, size))
    )
    return GroupPageResponse(
        items=[
            GroupDirectoryItem(
                group_id=item.group_id.value,
                tenant_id=item.tenant_id.value,
                name=item.name,
            )
            for item in result.items
        ],
        total=result.total,
        page=result.page,
        size=result.size,
        pages=result.pages,
        has_next=result.has_next,
    )


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_group(
    tenant_id: UUID,
    request: CreateGroupRequest,
    bus: Annotated[MessageBus, Depends(get_message_bus)],
    _: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
) -> dict[str, UUID]:
    """Create a tenant-local group."""
    group_id = await bus.send(CreateGroup(TenantId(tenant_id), request.name))
    return {"group_id": group_id.value}


@router.get("/{group_id}/members", response_model=GroupMembershipPageResponse)
async def list_group_members(
    tenant_id: UUID,
    group_id: UUID,
    bus: Annotated[MessageBus, Depends(get_message_bus)],
    principal: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
    keyword: str = Query(default="", max_length=320),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
) -> GroupMembershipPageResponse:
    """Search active and disabled members of a group."""
    if principal.tenant_id != tenant_id:
        raise HTTPException(status_code=403, detail="tenant context mismatch")
    result = await bus.ask(
        SearchGroupMemberships(GroupId(group_id), keyword, PageRequest(page, size))
    )
    return GroupMembershipPageResponse(
        items=[
            GroupMembershipResponse(
                membership_id=item.membership_id.value,
                group_id=item.group_id.value,
                member_id=item.member_id.value,
                member_type=item.member_type.value,
                active=item.active,
                display_name=item.display_name,
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
    "/{group_id}/members/{membership_id}/disable",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def disable_group_member(
    tenant_id: UUID,
    group_id: UUID,
    membership_id: UUID,
    bus: Annotated[MessageBus, Depends(get_message_bus)],
    principal: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
) -> None:
    """Disable a group membership without deleting it."""
    if principal.tenant_id != tenant_id:
        raise HTTPException(status_code=403, detail="tenant context mismatch")
    await bus.send(
        RemoveGroupMember(GroupMembershipId(membership_id), GroupId(group_id))
    )


@router.post(
    "/{group_id}/members/{membership_id}/restore",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def restore_group_member(
    tenant_id: UUID,
    group_id: UUID,
    membership_id: UUID,
    bus: Annotated[MessageBus, Depends(get_message_bus)],
    principal: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
) -> None:
    """Restore a disabled group membership."""
    if principal.tenant_id != tenant_id:
        raise HTTPException(status_code=403, detail="tenant context mismatch")
    await bus.send(
        RestoreGroupMember(GroupMembershipId(membership_id), GroupId(group_id))
    )


@router.post("/{group_id}/members", status_code=status.HTTP_204_NO_CONTENT)
async def add_group_member(
    group_id: UUID,
    request: AddGroupMemberRequest,
    bus: Annotated[MessageBus, Depends(get_message_bus)],
    _: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
) -> None:
    """Add a user or nested group to a group."""
    member = (
        GroupId(request.member_id)
        if request.member_type is GroupMemberType.GROUP
        else UserId(request.member_id)
    )
    await bus.send(AddGroupMember(GroupId(group_id), member, request.member_type))
