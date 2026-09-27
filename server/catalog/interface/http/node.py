from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel, Field

from ...application.messages import CreateNode, GetNode, ListNodes
from ...domain.value_objects import NodeId, NodeType, WorkspaceId
from ....iam.domain.value_objects import TenantId
from ....app.http.dependencies import (
    AuthenticatedPrincipal,
    get_current_principal,
    get_message_bus,
)
from ....kernel.application.common.page import PageRequest
from ....kernel.application.messaging.bus import MessageBus

router = APIRouter(prefix="/workspaces/{workspace_id}/nodes", tags=["catalog.nodes"])


class NodeRequest(BaseModel):
    node_type: NodeType
    display_name: str
    parent_id: UUID | None = None
    description: str = ""
    properties: dict[str, object] = Field(default_factory=dict)


class NodeResponse(BaseModel):
    node_id: UUID
    workspace_id: UUID
    parent_id: UUID | None
    node_type: NodeType
    display_name: str
    description: str
    properties: dict[str, object]
    is_deleted: bool


class NodePageResponse(BaseModel):
    items: list[NodeResponse]
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


@router.post("", response_model=NodeResponse, status_code=status.HTTP_201_CREATED)
async def create_node(
    workspace_id: UUID,
    request: NodeRequest,
    bus: Annotated[MessageBus, Depends(get_message_bus)],
    principal: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
) -> NodeResponse:
    tenant_id = _tenant(principal)
    node_id = await bus.send(
        CreateNode(
            tenant_id,
            WorkspaceId(workspace_id),
            NodeId(request.parent_id) if request.parent_id else None,
            request.node_type,
            request.display_name,
            request.description,
            request.properties,
        )
    )
    result = await bus.ask(GetNode(tenant_id, WorkspaceId(workspace_id), node_id))
    assert result is not None
    return NodeResponse(
        node_id=result.node_id.value,
        workspace_id=result.workspace_id.value,
        parent_id=result.parent_id.value if result.parent_id else None,
        node_type=result.node_type,
        display_name=result.display_name,
        description=result.description,
        properties=result.properties,
        is_deleted=result.is_deleted,
    )


@router.get("", response_model=NodePageResponse)
async def list_nodes(
    workspace_id: UUID,
    bus: Annotated[MessageBus, Depends(get_message_bus)],
    principal: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
    parent_id: UUID | None = None,
    keyword: str = Query(default="", max_length=255),
    node_type: NodeType | None = None,
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
) -> NodePageResponse:
    result = await bus.ask(
        ListNodes(
            _tenant(principal),
            WorkspaceId(workspace_id),
            NodeId(parent_id) if parent_id else None,
            keyword,
            node_type,
            PageRequest(page, size),
        )
    )
    return NodePageResponse(
        items=[
            NodeResponse(
                node_id=x.node_id.value,
                workspace_id=x.workspace_id.value,
                parent_id=x.parent_id.value if x.parent_id else None,
                node_type=x.node_type,
                display_name=x.display_name,
                description=x.description,
                properties=x.properties,
                is_deleted=x.is_deleted,
            )
            for x in result.items
        ],
        total=result.total,
        page=result.page,
        size=result.size,
        pages=result.pages,
        has_next=result.has_next,
    )
