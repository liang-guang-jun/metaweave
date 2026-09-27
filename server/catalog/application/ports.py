from __future__ import annotations

# ruff: noqa

from abc import ABC, abstractmethod
from collections.abc import Sequence
from datetime import datetime
from typing import Protocol

from ...iam.application.ports import RepositoryFactory
from ...iam.domain.services import AccessDecision
from ...iam.domain.value_objects import (
    AccessControlEntry,
    Action,
    AclScope,
    Effect,
    Subject,
    TenantId,
    UserId,
)
from ...kernel.application.common.page import Page, PageRequest
from ...kernel.application.unit_of_work import UnitOfWork
from .dto import (
    NodeDTO,
    NodePage,
    PermissionSourceDTO,
    WorkspaceDTO,
    WorkspaceMembershipDTO,
)
from ..domain.entities import Node, Workspace, WorkspaceMembership
from ..domain.value_objects import NodeId, NodeType, WorkspaceId, WorkspaceMembershipId


class WorkspaceRepository(ABC):
    @abstractmethod
    async def get(
        self, tenant_id: TenantId, workspace_id: WorkspaceId
    ) -> Workspace | None: ...
    @abstractmethod
    async def add(self, workspace: Workspace) -> None: ...
    @abstractmethod
    async def save(self, workspace: Workspace) -> None: ...
    @abstractmethod
    async def exists_name(
        self, tenant_id: TenantId, display_name: str, exclude: WorkspaceId | None = None
    ) -> bool: ...


class WorkspaceMembershipRepository(ABC):
    @abstractmethod
    async def get(
        self, membership_id: WorkspaceMembershipId
    ) -> WorkspaceMembership | None: ...
    @abstractmethod
    async def find(
        self, workspace_id: WorkspaceId, user_id: UserId
    ) -> WorkspaceMembership | None: ...
    @abstractmethod
    async def list_active_admins(
        self, workspace_id: WorkspaceId
    ) -> list[WorkspaceMembership]: ...
    @abstractmethod
    async def add(self, membership: WorkspaceMembership) -> None: ...
    @abstractmethod
    async def save(self, membership: WorkspaceMembership) -> None: ...
    @abstractmethod
    async def remove(self, membership: WorkspaceMembership) -> None: ...


class NodeRepository(ABC):
    @abstractmethod
    async def get(self, workspace_id: WorkspaceId, node_id: NodeId) -> Node | None: ...
    @abstractmethod
    async def add(self, node: Node) -> None: ...
    @abstractmethod
    async def save(self, node: Node) -> None: ...
    @abstractmethod
    async def exists_sibling_name(
        self,
        workspace_id: WorkspaceId,
        parent_id: NodeId | None,
        node_type: NodeType,
        display_name: str,
        exclude: NodeId | None = None,
    ) -> bool: ...
    @abstractmethod
    async def has_descendant(
        self, workspace_id: WorkspaceId, ancestor_id: NodeId, candidate_id: NodeId
    ) -> bool: ...
    @abstractmethod
    async def soft_delete_subtree(
        self, workspace_id: WorkspaceId, node_id: NodeId
    ) -> None: ...


class NodeReadStore(Protocol):
    async def get(
        self, workspace_id: WorkspaceId, node_id: NodeId
    ) -> NodeDTO | None: ...
    async def search(
        self,
        workspace_id: WorkspaceId,
        parent_id: NodeId | None,
        keyword: str,
        node_type: NodeType | None,
        page: PageRequest,
    ) -> NodePage: ...
    async def path(
        self, workspace_id: WorkspaceId, node_id: NodeId
    ) -> tuple[NodeDTO, ...]: ...


class WorkspaceReadStore(Protocol):
    async def get(
        self, tenant_id: TenantId, workspace_id: WorkspaceId
    ) -> WorkspaceDTO | None: ...
    async def list(
        self, tenant_id: TenantId, keyword: str, page: PageRequest
    ) -> Page[WorkspaceDTO]: ...


class WorkspaceMembershipReadStore(Protocol):
    async def list(
        self, workspace_id: WorkspaceId, page: PageRequest
    ) -> Page[WorkspaceMembershipDTO]: ...


class CatalogAclAuthorizationService(Protocol):
    async def check(
        self,
        *,
        subject: Subject,
        tenant_id: TenantId,
        action: Action,
        scopes: Sequence[AclScope],
        uow: UnitOfWork,
    ) -> AccessDecision: ...
    async def list_permissions(
        self, *, tenant_id: TenantId, scopes: Sequence[AclScope], uow: UnitOfWork
    ) -> tuple[PermissionSourceDTO, ...]: ...
    async def grant(
        self,
        *,
        tenant_id: TenantId,
        resource_type: str,
        resource_id: str,
        subject: Subject,
        action: Action,
        effect: Effect,
        uow: UnitOfWork,
    ) -> None: ...
    async def revoke(
        self,
        *,
        tenant_id: TenantId,
        resource_type: str,
        resource_id: str,
        subject: Subject,
        action: Action,
        uow: UnitOfWork,
    ) -> None: ...


class CatalogDependencies(Protocol):
    workspaces: RepositoryFactory[WorkspaceRepository]
    memberships: RepositoryFactory[WorkspaceMembershipRepository]
    nodes: RepositoryFactory[NodeRepository]
    acl: CatalogAclAuthorizationService
    ids: object
    clock: object
