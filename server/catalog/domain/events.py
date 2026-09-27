from __future__ import annotations

# Immutable domain-event declarations.
# ruff: noqa

from dataclasses import dataclass
from datetime import datetime

from ...kernel.domain.event import DomainEvent
from .value_objects import (
    NodeId,
    NodeType,
    WorkspaceId,
    WorkspaceMembershipId,
    WorkspaceRole,
)


@dataclass(frozen=True, slots=True)
class WorkspaceCreated(DomainEvent):
    workspace_id: WorkspaceId
    tenant_id: object
    display_name: str


@dataclass(frozen=True, slots=True)
class WorkspaceDisabled(DomainEvent):
    workspace_id: WorkspaceId


@dataclass(frozen=True, slots=True)
class WorkspaceRestored(DomainEvent):
    workspace_id: WorkspaceId


@dataclass(frozen=True, slots=True)
class WorkspaceRenamed(DomainEvent):
    workspace_id: WorkspaceId
    display_name: str


@dataclass(frozen=True, slots=True)
class WorkspaceMembershipInvited(DomainEvent):
    membership_id: WorkspaceMembershipId
    workspace_id: WorkspaceId
    user_id: object


@dataclass(frozen=True, slots=True)
class WorkspaceMembershipAccepted(DomainEvent):
    membership_id: WorkspaceMembershipId


@dataclass(frozen=True, slots=True)
class WorkspaceMembershipRoleChanged(DomainEvent):
    membership_id: WorkspaceMembershipId
    role: WorkspaceRole


@dataclass(frozen=True, slots=True)
class WorkspaceMembershipDisabled(DomainEvent):
    membership_id: WorkspaceMembershipId


@dataclass(frozen=True, slots=True)
class WorkspaceMembershipRestored(DomainEvent):
    membership_id: WorkspaceMembershipId


@dataclass(frozen=True, slots=True)
class WorkspaceMembershipRemoved(DomainEvent):
    membership_id: WorkspaceMembershipId


@dataclass(frozen=True, slots=True)
class NodeCreated(DomainEvent):
    node_id: NodeId
    workspace_id: WorkspaceId
    node_type: NodeType
    display_name: str


@dataclass(frozen=True, slots=True)
class NodeRenamed(DomainEvent):
    node_id: NodeId
    display_name: str


@dataclass(frozen=True, slots=True)
class NodeMoved(DomainEvent):
    node_id: NodeId
    parent_id: NodeId | None


@dataclass(frozen=True, slots=True)
class NodeUpdated(DomainEvent):
    node_id: NodeId


@dataclass(frozen=True, slots=True)
class NodeDeleted(DomainEvent):
    node_id: NodeId
