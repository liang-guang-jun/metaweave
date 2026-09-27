from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel

from ...application.messages import GrantNodeAccess, GetNodePermissions, RevokeNodeAccess
from ...domain.value_objects import NodeId, WorkspaceId
from ....app.http.dependencies import AuthenticatedPrincipal, get_current_principal, get_message_bus
from ....iam.domain.value_objects import Action, Effect, Subject, TenantId, SubjectType, UserId
from ....kernel.application.messaging.bus import MessageBus

router = APIRouter(prefix="/workspaces/{workspace_id}/nodes/{node_id}/permissions", tags=["catalog.permissions"])


class PermissionRequest(BaseModel):
    user_id: UUID
    action: str
    effect: Effect = Effect.ALLOW


class PermissionResponse(BaseModel):
    subject_id: UUID
    action: str
    effect: Effect
    resource_type: str
    resource_id: str
    inherited: bool


@router.get("", response_model=list[PermissionResponse])
async def get_permissions(
    workspace_id: UUID,
    node_id: UUID,
    bus: Annotated[MessageBus, Depends(get_message_bus)],
    principal: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
) -> list[PermissionResponse]:
    if principal.tenant_id is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="tenant context required")
    result = await bus.ask(GetNodePermissions(TenantId(principal.tenant_id), WorkspaceId(workspace_id), NodeId(node_id)))
    return [PermissionResponse(subject_id=x.subject.subject_id.value, action=x.action.value, effect=x.effect, resource_type=x.scope_resource_type, resource_id=x.scope_resource_id, inherited=x.inherited) for x in result.permissions]


@router.post("", status_code=status.HTTP_204_NO_CONTENT)
async def grant_permission(
    workspace_id: UUID,
    node_id: UUID,
    request: PermissionRequest,
    bus: Annotated[MessageBus, Depends(get_message_bus)],
    principal: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
) -> None:
    if principal.tenant_id is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="tenant context required")
    await bus.send(GrantNodeAccess(TenantId(principal.tenant_id), WorkspaceId(workspace_id), NodeId(node_id), Subject(UserId(request.user_id), SubjectType.USER), Action(request.action), request.effect))


@router.delete("/{user_id}/{action}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_permission(
    workspace_id: UUID,
    node_id: UUID,
    user_id: UUID,
    action: str,
    bus: Annotated[MessageBus, Depends(get_message_bus)],
    principal: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
) -> None:
    if principal.tenant_id is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="tenant context required")
    await bus.send(RevokeNodeAccess(TenantId(principal.tenant_id), WorkspaceId(workspace_id), NodeId(node_id), Subject(UserId(user_id), SubjectType.USER), Action(action)))
