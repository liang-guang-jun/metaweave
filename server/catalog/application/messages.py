from __future__ import annotations

# Immutable CQRS message declarations.
# ruff: noqa

from dataclasses import dataclass, field

from ...iam.domain.value_objects import Action, Effect, Subject, TenantId, UserId
from ...kernel.application.common.page import Page, PageRequest
from ...kernel.application.messaging.message import Command, Query
from ..domain.value_objects import NodeId, NodeType, WorkspaceId, WorkspaceMembershipId, WorkspaceRole
from .dto import NodeDTO, NodePage, NodePermissionDTO, WorkspaceDTO, WorkspaceMembershipDTO


@dataclass(frozen=True, slots=True)
class CreateWorkspace(Command[WorkspaceId]):
    tenant_id: TenantId
    display_name: str
    description: str = ""


@dataclass(frozen=True, slots=True)
class RenameWorkspace(Command[None]):
    tenant_id: TenantId
    workspace_id: WorkspaceId
    display_name: str


@dataclass(frozen=True, slots=True)
class DisableWorkspace(Command[None]):
    tenant_id: TenantId
    workspace_id: WorkspaceId


@dataclass(frozen=True, slots=True)
class RestoreWorkspace(Command[None]):
    tenant_id: TenantId
    workspace_id: WorkspaceId


@dataclass(frozen=True, slots=True)
class InviteWorkspaceMember(Command[WorkspaceMembershipId]):
    tenant_id: TenantId
    workspace_id: WorkspaceId
    user_id: UserId
    role: WorkspaceRole = WorkspaceRole.VIEWER


@dataclass(frozen=True, slots=True)
class AcceptWorkspaceInvitation(Command[None]):
    membership_id: WorkspaceMembershipId


@dataclass(frozen=True, slots=True)
class ChangeWorkspaceMemberRole(Command[None]):
    tenant_id: TenantId
    membership_id: WorkspaceMembershipId
    role: WorkspaceRole


@dataclass(frozen=True, slots=True)
class DisableWorkspaceMember(Command[None]):
    tenant_id: TenantId
    membership_id: WorkspaceMembershipId


@dataclass(frozen=True, slots=True)
class RestoreWorkspaceMember(Command[None]):
    tenant_id: TenantId
    membership_id: WorkspaceMembershipId


@dataclass(frozen=True, slots=True)
class RemoveWorkspaceMember(Command[None]):
    tenant_id: TenantId
    membership_id: WorkspaceMembershipId


@dataclass(frozen=True, slots=True)
class CreateNode(Command[NodeId]):
    tenant_id: TenantId
    workspace_id: WorkspaceId
    parent_id: NodeId | None
    node_type: NodeType
    display_name: str
    description: str = ""
    properties: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class UpdateNode(Command[None]):
    tenant_id: TenantId
    workspace_id: WorkspaceId
    node_id: NodeId
    description: str
    properties: dict[str, object]


@dataclass(frozen=True, slots=True)
class RenameNode(Command[None]):
    tenant_id: TenantId
    workspace_id: WorkspaceId
    node_id: NodeId
    display_name: str


@dataclass(frozen=True, slots=True)
class MoveNode(Command[None]):
    tenant_id: TenantId
    workspace_id: WorkspaceId
    node_id: NodeId
    parent_id: NodeId | None


@dataclass(frozen=True, slots=True)
class DeleteNode(Command[None]):
    tenant_id: TenantId
    workspace_id: WorkspaceId
    node_id: NodeId


@dataclass(frozen=True, slots=True)
class GrantNodeAccess(Command[None]):
    tenant_id: TenantId
    workspace_id: WorkspaceId
    node_id: NodeId
    subject: Subject
    action: Action
    effect: Effect = Effect.ALLOW


@dataclass(frozen=True, slots=True)
class RevokeNodeAccess(Command[None]):
    tenant_id: TenantId
    workspace_id: WorkspaceId
    node_id: NodeId
    subject: Subject
    action: Action


@dataclass(frozen=True, slots=True)
class GrantWorkspaceAccess(Command[None]):
    tenant_id: TenantId
    workspace_id: WorkspaceId
    subject: Subject
    action: Action
    effect: Effect = Effect.ALLOW


@dataclass(frozen=True, slots=True)
class RevokeWorkspaceAccess(Command[None]):
    tenant_id: TenantId
    workspace_id: WorkspaceId
    subject: Subject
    action: Action


@dataclass(frozen=True, slots=True)
class ListWorkspaces(Query[Page[WorkspaceDTO]]):
    tenant_id: TenantId
    keyword: str = ""
    page: PageRequest = field(default_factory=PageRequest)


@dataclass(frozen=True, slots=True)
class GetWorkspace(Query[WorkspaceDTO | None]):
    tenant_id: TenantId
    workspace_id: WorkspaceId


@dataclass(frozen=True, slots=True)
class ListWorkspaceMembers(Query[Page[WorkspaceMembershipDTO]]):
    workspace_id: WorkspaceId
    page: PageRequest = field(default_factory=PageRequest)


@dataclass(frozen=True, slots=True)
class ListNodes(Query[NodePage]):
    tenant_id: TenantId
    workspace_id: WorkspaceId
    parent_id: NodeId | None = None
    keyword: str = ""
    node_type: NodeType | None = None
    page: PageRequest = field(default_factory=PageRequest)


@dataclass(frozen=True, slots=True)
class GetNode(Query[NodeDTO | None]):
    tenant_id: TenantId
    workspace_id: WorkspaceId
    node_id: NodeId


@dataclass(frozen=True, slots=True)
class GetNodePath(Query[tuple[NodeDTO, ...]]):
    tenant_id: TenantId
    workspace_id: WorkspaceId
    node_id: NodeId


@dataclass(frozen=True, slots=True)
class GetNodePermissions(Query[NodePermissionDTO]):
    tenant_id: TenantId
    workspace_id: WorkspaceId
    node_id: NodeId
