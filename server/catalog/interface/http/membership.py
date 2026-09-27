from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel

from ...application.messages import InviteWorkspaceMember, ListWorkspaceMembers
from ...domain.value_objects import WorkspaceId, WorkspaceMembershipId, WorkspaceRole
from ....app.http.dependencies import AuthenticatedPrincipal, get_current_principal, get_message_bus
from ....kernel.application.common.page import PageRequest
from ....kernel.application.messaging.bus import MessageBus
from ....iam.domain.value_objects import TenantId, UserId

router = APIRouter(prefix="/workspaces/{workspace_id}/members", tags=["catalog.memberships"])


class InviteRequest(BaseModel):
    user_id: UUID
    role: WorkspaceRole = WorkspaceRole.VIEWER


class MemberResponse(BaseModel):
    membership_id: UUID
    workspace_id: UUID
    user_id: UUID
    role: WorkspaceRole
    active: bool


class MemberPageResponse(BaseModel):
    items: list[MemberResponse]
    total: int
    page: int
    size: int
    pages: int
    has_next: bool


def _tenant(principal: AuthenticatedPrincipal) -> TenantId:
    from fastapi import HTTPException
    if principal.tenant_id is None:
        raise HTTPException(status_code=400, detail="tenant context required")
    return TenantId(principal.tenant_id)


@router.get("", response_model=MemberPageResponse)
async def list_members(
    workspace_id: UUID,
    bus: Annotated[MessageBus, Depends(get_message_bus)],
    principal: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
) -> MemberPageResponse:
    result = await bus.ask(ListWorkspaceMembers(WorkspaceId(workspace_id), PageRequest(page, size)))
    return MemberPageResponse(
        items=[MemberResponse(membership_id=x.membership_id.value, workspace_id=x.workspace_id.value, user_id=x.user_id.value, role=x.role, active=x.active) for x in result.items],
        total=result.total, page=result.page, size=result.size, pages=result.pages, has_next=result.has_next,
    )


@router.post("", status_code=status.HTTP_201_CREATED)
async def invite_member(
    workspace_id: UUID,
    request: InviteRequest,
    bus: Annotated[MessageBus, Depends(get_message_bus)],
    principal: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
) -> dict[str, UUID]:
    membership_id = await bus.send(InviteWorkspaceMember(_tenant(principal), WorkspaceId(workspace_id), UserId(request.user_id), request.role))
    return {"membership_id": membership_id.value}
