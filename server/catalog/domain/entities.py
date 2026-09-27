from __future__ import annotations

# Domain aggregate declarations use the same compact event imports as IAM.
# ruff: noqa

from datetime import datetime
from typing import Any
from uuid import UUID

from ...iam.domain.value_objects import TenantId, UserId
from ...kernel.domain.aggregate import VersionedAggregate
from .errors import CatalogDomainError
from .events import *
from .value_objects import *


class Workspace(VersionedAggregate[UUID]):
    def __init__(
        self,
        workspace_id: WorkspaceId,
        tenant_id: TenantId,
        display_name: str,
        description: str = "",
        *,
        active: bool = True,
        version: int = 0,
    ) -> None:
        super().__init__(version=version)
        if not display_name.strip():
            raise CatalogDomainError("workspace display name is required")
        self._id, self.tenant_id, self.display_name, self.description = (
            workspace_id,
            tenant_id,
            display_name.strip(),
            description,
        )
        self.active = active

    @property
    def id(self) -> WorkspaceId:
        return self._id

    @classmethod
    def create(
        cls,
        workspace_id: WorkspaceId,
        tenant_id: TenantId,
        display_name: str,
        description: str = "",
    ) -> Workspace:
        value = cls(workspace_id, tenant_id, display_name, description)
        value._record_state_change(
            WorkspaceCreated(value.id, tenant_id, value.display_name)
        )
        return value

    @classmethod
    def restore(
        cls,
        workspace_id: WorkspaceId,
        tenant_id: TenantId,
        display_name: str,
        description: str,
        active: bool,
        version: int,
    ) -> Workspace:
        return cls(
            workspace_id,
            tenant_id,
            display_name,
            description,
            active=active,
            version=version,
        )

    def rename(self, display_name: str) -> None:
        if not display_name.strip():
            raise CatalogDomainError("workspace display name is required")
        if display_name.strip() != self.display_name:
            self.display_name = display_name.strip()
            self._record_state_change(WorkspaceRenamed(self.id, self.display_name))

    def disable(self) -> None:
        if self.active:
            self.active = False
            self._record_state_change(WorkspaceDisabled(self.id))

    def restore_workspace(self) -> None:
        if not self.active:
            self.active = True
            self._record_state_change(WorkspaceRestored(self.id))


class WorkspaceMembership(VersionedAggregate[UUID]):
    def __init__(
        self,
        membership_id: WorkspaceMembershipId,
        workspace_id: WorkspaceId,
        tenant_id: TenantId,
        user_id: UserId,
        role: WorkspaceRole,
        *,
        active: bool = False,
        joined_at: datetime | None = None,
        version: int = 0,
    ) -> None:
        super().__init__(version=version)
        self._id, self.workspace_id, self.tenant_id, self.user_id = (
            membership_id,
            workspace_id,
            tenant_id,
            user_id,
        )
        self.role, self.active, self.joined_at = role, active, joined_at

    @property
    def id(self) -> WorkspaceMembershipId:
        return self._id

    @classmethod
    def invite(
        cls,
        membership_id: WorkspaceMembershipId,
        workspace_id: WorkspaceId,
        tenant_id: TenantId,
        user_id: UserId,
        role: WorkspaceRole,
    ) -> WorkspaceMembership:
        value = cls(membership_id, workspace_id, tenant_id, user_id, role)
        value._record_state_change(
            WorkspaceMembershipInvited(value.id, workspace_id, user_id)
        )
        return value

    @classmethod
    def restore(
        cls,
        membership_id: WorkspaceMembershipId,
        workspace_id: WorkspaceId,
        tenant_id: TenantId,
        user_id: UserId,
        role: WorkspaceRole,
        active: bool,
        joined_at: datetime | None,
        version: int,
    ) -> WorkspaceMembership:
        return cls(
            membership_id,
            workspace_id,
            tenant_id,
            user_id,
            role,
            active=active,
            joined_at=joined_at,
            version=version,
        )

    def accept(self, now: datetime) -> None:
        if not self.active:
            self.active, self.joined_at = True, now
            self._record_state_change(WorkspaceMembershipAccepted(self.id))

    def change_role(self, role: WorkspaceRole) -> None:
        if role != self.role:
            self.role = role
            self._record_state_change(WorkspaceMembershipRoleChanged(self.id, role))

    def disable(self) -> None:
        if self.active:
            self.active = False
            self._record_state_change(WorkspaceMembershipDisabled(self.id))

    def restore_membership(self) -> None:
        if not self.active:
            self.active = True
            self._record_state_change(WorkspaceMembershipRestored(self.id))

    def remove(self) -> None:
        if self.active:
            self.active = False
            self._record_state_change(WorkspaceMembershipRemoved(self.id))


class Node(VersionedAggregate[UUID]):
    def __init__(
        self,
        node_id: NodeId,
        tenant_id: TenantId,
        workspace_id: WorkspaceId,
        parent_id: NodeId | None,
        node_type: NodeType,
        display_name: str,
        description: str = "",
        properties: dict[str, Any] | None = None,
        *,
        is_deleted: bool = False,
        version: int = 0,
    ) -> None:
        super().__init__(version=version)
        if not display_name.strip():
            raise CatalogDomainError("node display name is required")
        self._id, self.tenant_id, self.workspace_id, self.parent_id = (
            node_id,
            tenant_id,
            workspace_id,
            parent_id,
        )
        self.node_type, self.display_name, self.description = (
            node_type,
            display_name.strip(),
            description,
        )
        self.properties, self.is_deleted = dict(properties or {}), is_deleted

    @property
    def id(self) -> NodeId:
        return self._id

    @classmethod
    def create(
        cls,
        node_id: NodeId,
        tenant_id: TenantId,
        workspace_id: WorkspaceId,
        parent_id: NodeId | None,
        node_type: NodeType,
        display_name: str,
        description: str = "",
        properties: dict[str, Any] | None = None,
    ) -> Node:
        value = cls(
            node_id,
            tenant_id,
            workspace_id,
            parent_id,
            node_type,
            display_name,
            description,
            properties,
        )
        value._record_state_change(
            NodeCreated(value.id, workspace_id, node_type, value.display_name)
        )
        return value

    @classmethod
    def restore(
        cls,
        node_id: NodeId,
        tenant_id: TenantId,
        workspace_id: WorkspaceId,
        parent_id: NodeId | None,
        node_type: NodeType,
        display_name: str,
        description: str,
        properties: dict[str, Any],
        is_deleted: bool,
        version: int,
    ) -> Node:
        return cls(
            node_id,
            tenant_id,
            workspace_id,
            parent_id,
            node_type,
            display_name,
            description,
            properties,
            is_deleted=is_deleted,
            version=version,
        )

    def rename(self, display_name: str) -> None:
        if not display_name.strip():
            raise CatalogDomainError("node display name is required")
        if display_name.strip() != self.display_name:
            self.display_name = display_name.strip()
            self._record_state_change(NodeRenamed(self.id, self.display_name))

    def move(self, parent_id: NodeId | None) -> None:
        if parent_id == self.id:
            raise CatalogDomainError("node cannot be moved into itself")
        if parent_id != self.parent_id:
            self.parent_id = parent_id
            self._record_state_change(NodeMoved(self.id, parent_id))

    def update(self, description: str, properties: dict[str, Any]) -> None:
        self.description, self.properties = description, dict(properties)
        self._record_state_change(NodeUpdated(self.id))

    def delete(self) -> None:
        if not self.is_deleted:
            self.is_deleted = True
            self._record_state_change(NodeDeleted(self.id))
