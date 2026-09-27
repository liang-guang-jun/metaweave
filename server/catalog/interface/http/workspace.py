from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel

from ...application.messages import CreateWorkspace, GetWorkspace, ListWorkspaces
from ...domain.value_objects import WorkspaceId
from ....iam.domain.value_objects import TenantId
from ....app.http.dependencies import (
    AuthenticatedPrincipal,
    get_current_principal,
    get_message_bus,
)
from ....kernel.application.common.page import PageRequest
from ....kernel.application.messaging.bus import MessageBus

router = APIRouter(prefix="/workspaces", tags=["catalog.workspaces"])


class WorkspaceRequest(BaseModel):
    display_name: str
    description: str = ""


class WorkspaceResponse(BaseModel):
    workspace_id: UUID
    tenant_id: UUID
    display_name: str
    description: str
    active: bool


class WorkspacePageResponse(BaseModel):
    items: list[WorkspaceResponse]
    total: int
    page: int
    size: int
    pages: int
    has_next: bool


@router.post("", response_model=WorkspaceResponse, status_code=status.HTTP_201_CREATED)
async def create_workspace(
    request: WorkspaceRequest,
    bus: Annotated[MessageBus, Depends(get_message_bus)],
    principal: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
) -> WorkspaceResponse:
    tenant_id = principal.tenant_id
    if tenant_id is None:
        from fastapi import HTTPException

        raise HTTPException(status_code=400, detail="tenant context required")
    workspace_id = await bus.send(
        CreateWorkspace(TenantId(tenant_id), request.display_name, request.description)
    )
    result = await bus.ask(
        GetWorkspace(TenantId(tenant_id), WorkspaceId(workspace_id.value))
    )
    assert result is not None
    return WorkspaceResponse(
        workspace_id=result.workspace_id.value,
        tenant_id=result.tenant_id.value,
        display_name=result.display_name,
        description=result.description,
        active=result.active,
    )


@router.get("", response_model=WorkspacePageResponse)
async def list_workspaces(
    bus: Annotated[MessageBus, Depends(get_message_bus)],
    principal: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
    keyword: str = Query(default="", max_length=255),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
) -> WorkspacePageResponse:
    from fastapi import HTTPException

    if principal.tenant_id is None:
        raise HTTPException(status_code=400, detail="tenant context required")
    result = await bus.ask(
        ListWorkspaces(TenantId(principal.tenant_id), keyword, PageRequest(page, size))
    )
    return WorkspacePageResponse(
        items=[
            WorkspaceResponse(
                workspace_id=x.workspace_id.value,
                tenant_id=x.tenant_id.value,
                display_name=x.display_name,
                description=x.description,
                active=x.active,
            )
            for x in result.items
        ],
        total=result.total,
        page=result.page,
        size=result.size,
        pages=result.pages,
        has_next=result.has_next,
    )
