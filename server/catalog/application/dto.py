from __future__ import annotations

# Catalog DTOs are intentionally lightweight data carriers.
# ruff: noqa

from dataclasses import dataclass
from datetime import datetime

from ...iam.domain.value_objects import Action, Effect, Subject, TenantId, UserId
from ..domain.value_objects import NodeId, NodeType, WorkspaceId, WorkspaceMembershipId, WorkspaceRole


@dataclass(frozen=True, slots=True)
class WorkspaceDTO:
    workspace_id: WorkspaceId
    tenant_id: TenantId
    display_name: str
    description: str
    active: bool


@dataclass(frozen=True, slots=True)
class WorkspaceMembershipDTO:
    membership_id: WorkspaceMembershipId
    workspace_id: WorkspaceId
    user_id: UserId
    role: WorkspaceRole
    active: bool
    joined_at: datetime | None


@dataclass(frozen=True, slots=True)
class NodeDTO:
    node_id: NodeId
    workspace_id: WorkspaceId
    parent_id: NodeId | None
    node_type: NodeType
    display_name: str
    description: str
    properties: dict[str, object]
    is_deleted: bool


@dataclass(frozen=True, slots=True)
class PermissionSourceDTO:
    subject: Subject
    action: Action
    effect: Effect
    scope_resource_type: str
    scope_resource_id: str
    inherited: bool


@dataclass(frozen=True, slots=True)
class NodePermissionDTO:
    node_id: NodeId
    permissions: tuple[PermissionSourceDTO, ...]


@dataclass(frozen=True, slots=True)
class NodePage:
    items: tuple[NodeDTO, ...]
    total: int
    page: int
    size: int

    @property
    def pages(self) -> int:
        return (self.total + self.size - 1) // self.size if self.size else 0

    @property
    def has_next(self) -> bool:
        return self.page < self.pages
