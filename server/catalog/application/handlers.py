"""Catalog command and query handlers."""
# mypy: ignore-errors

from __future__ import annotations

# ruff: noqa

from ...iam.domain.errors import IamDomainError
from ...iam.domain.value_objects import (
    Action,
    AclScope,
    Effect,
    Subject,
    SubjectType,
    TenantId,
    UserId,
)
from ...kernel.application.common.page import Page
from ...kernel.application.context import current_context_or_none
from ...kernel.application.messaging.handler import CommandHandler, QueryHandler
from ...kernel.application.unit_of_work import UnitOfWork
from ..domain.entities import Node, Workspace, WorkspaceMembership
from ..domain.errors import CatalogDomainError
from ..domain.value_objects import CatalogAction, NodeType, WorkspaceRole
from .dto import NodeDTO, NodePage, PermissionSourceDTO
from .messages import *
from .ports import *


def _uow(uow: UnitOfWork | None) -> UnitOfWork:
    if uow is None:
        raise RuntimeError("Catalog command requires an active UnitOfWork")
    return uow


def _actor() -> UserId:
    context = current_context_or_none()
    value = context.metadata.user_id if context else None
    if not value:
        raise CatalogDomainError("authenticated principal required")
    return UserId(value)


async def _workspace(
    repos: RepositoryFactory[WorkspaceRepository],
    transaction: UnitOfWork,
    tenant_id: TenantId,
    workspace_id: WorkspaceId,
) -> Workspace:
    value = await repos(transaction).get(tenant_id, workspace_id)
    if value is None or not value.active:
        raise CatalogDomainError("workspace not found")
    return value


async def _require_admin(
    memberships: RepositoryFactory[WorkspaceMembershipRepository],
    transaction: UnitOfWork,
    workspace_id: WorkspaceId,
) -> WorkspaceMembership:
    membership = await memberships(transaction).find(workspace_id, _actor())
    if (
        membership is None
        or not membership.active
        or membership.role is not WorkspaceRole.ADMIN
    ):
        raise CatalogDomainError("workspace administrator required")
    return membership


async def _require_action(
    acl,
    transaction: UnitOfWork,
    tenant_id: TenantId,
    workspace_id: WorkspaceId,
    action: CatalogAction,
    node_id: NodeId | None = None,
) -> None:
    scopes = []
    if node_id is not None:
        scopes.append(AclScope(tenant_id, "node", str(node_id)))
    scopes.append(AclScope(tenant_id, "workspace", str(workspace_id)))
    decision = await acl.check(
        subject=Subject(_actor(), SubjectType.USER),
        tenant_id=tenant_id,
        action=Action(action.value),
        scopes=scopes,
        uow=transaction,
    )
    if not decision.permit:
        raise CatalogDomainError("catalog permission denied")


class CreateWorkspaceHandler(CommandHandler[CreateWorkspace, WorkspaceId]):
    def __init__(self, workspaces, memberships, acl, ids, clock):
        self.workspaces, self.memberships, self.acl, self.ids, self.clock = (
            workspaces,
            memberships,
            acl,
            ids,
            clock,
        )

    async def handle(
        self, message: CreateWorkspace, uow: UnitOfWork | None = None
    ) -> WorkspaceId:
        transaction = _uow(uow)
        repo = self.workspaces(transaction)
        if await repo.exists_name(message.tenant_id, message.display_name):
            raise CatalogDomainError("workspace name already exists")
        workspace = Workspace.create(
            WorkspaceId(self.ids.new()),
            message.tenant_id,
            message.display_name,
            message.description,
        )
        await repo.add(workspace)
        membership = WorkspaceMembership.invite(
            WorkspaceMembershipId(self.ids.new()),
            workspace.id,
            workspace.tenant_id,
            _actor(),
            WorkspaceRole.ADMIN,
        )
        membership.accept(self.clock.now())
        await self.memberships(transaction).add(membership)
        for action in (CatalogAction.READ, CatalogAction.WRITE, CatalogAction.DELETE):
            await self.acl.grant(
                tenant_id=workspace.tenant_id,
                resource_type="workspace",
                resource_id=str(workspace.id),
                subject=Subject(membership.user_id, SubjectType.USER),
                action=Action(action.value),
                effect=Effect.ALLOW,
                uow=transaction,
            )
        return workspace.id


class _WorkspaceMutation(CommandHandler):
    def __init__(self, workspaces, memberships):
        self.workspaces, self.memberships = workspaces, memberships

    async def _get(self, message, uow):
        transaction = _uow(uow)
        workspace = await _workspace(
            self.workspaces, transaction, message.tenant_id, message.workspace_id
        )
        await _require_admin(self.memberships, transaction, workspace.id)
        return transaction, workspace


class RenameWorkspaceHandler(_WorkspaceMutation, CommandHandler[RenameWorkspace, None]):
    async def handle(self, message, uow=None):
        transaction, workspace = await self._get(message, uow)
        if await self.workspaces(transaction).exists_name(
            message.tenant_id, message.display_name, workspace.id
        ):
            raise CatalogDomainError("workspace name already exists")
        workspace.rename(message.display_name)
        await self.workspaces(transaction).save(workspace)


class DisableWorkspaceHandler(
    _WorkspaceMutation, CommandHandler[DisableWorkspace, None]
):
    async def handle(self, message, uow=None):
        transaction, workspace = await self._get(message, uow)
        workspace.disable()
        await self.workspaces(transaction).save(workspace)


class RestoreWorkspaceHandler(CommandHandler[RestoreWorkspace, None]):
    def __init__(self, workspaces, memberships):
        self.workspaces, self.memberships = workspaces, memberships

    async def handle(self, message, uow=None):
        transaction = _uow(uow)
        row = await self.workspaces(transaction).get(
            message.tenant_id, message.workspace_id
        )
        if row is None:
            raise CatalogDomainError("workspace not found")
        await _require_admin(self.memberships, transaction, row.id)
        row.restore_workspace()
        await self.workspaces(transaction).save(row)


class InviteWorkspaceMemberHandler(
    CommandHandler[InviteWorkspaceMember, WorkspaceMembershipId]
):
    def __init__(self, workspaces, memberships, ids):
        self.workspaces, self.memberships, self.ids = workspaces, memberships, ids

    async def handle(self, message, uow=None):
        transaction = _uow(uow)
        workspace = await _workspace(
            self.workspaces, transaction, message.tenant_id, message.workspace_id
        )
        await _require_admin(self.memberships, transaction, workspace.id)
        repo = self.memberships(transaction)
        if await repo.find(workspace.id, message.user_id):
            raise CatalogDomainError("workspace membership already exists")
        membership = WorkspaceMembership.invite(
            WorkspaceMembershipId(self.ids.new()),
            workspace.id,
            workspace.tenant_id,
            message.user_id,
            message.role,
        )
        await repo.add(membership)
        return membership.id


class AcceptWorkspaceInvitationHandler(CommandHandler[AcceptWorkspaceInvitation, None]):
    def __init__(self, memberships, clock, acl):
        self.memberships, self.clock, self.acl = memberships, clock, acl

    async def handle(self, message, uow=None):
        transaction = _uow(uow)
        membership = await self.memberships(transaction).get(message.membership_id)
        if membership is None or membership.user_id != _actor():
            raise CatalogDomainError("workspace membership not found")
        membership.accept(self.clock.now())
        await self.memberships(transaction).save(membership)
        await _sync_role(self.acl, transaction, membership)


async def _sync_role(acl, transaction, membership: WorkspaceMembership) -> None:
    subject = Subject(membership.user_id, SubjectType.USER)
    for action in (CatalogAction.READ, CatalogAction.WRITE, CatalogAction.DELETE):
        enabled = membership.active and (
            action is CatalogAction.READ
            or (
                action is CatalogAction.WRITE
                and membership.role in {WorkspaceRole.CONTRIBUTOR, WorkspaceRole.ADMIN}
            )
            or (
                action is CatalogAction.DELETE
                and membership.role is WorkspaceRole.ADMIN
            )
        )
        if enabled:
            await acl.grant(
                tenant_id=membership.tenant_id,
                resource_type="workspace",
                resource_id=str(membership.workspace_id),
                subject=subject,
                action=Action(action.value),
                effect=Effect.ALLOW,
                uow=transaction,
            )
        else:
            await acl.revoke(
                tenant_id=membership.tenant_id,
                resource_type="workspace",
                resource_id=str(membership.workspace_id),
                subject=subject,
                action=Action(action.value),
                uow=transaction,
            )


class _MembershipMutation(CommandHandler):
    def __init__(self, memberships, acl):
        self.memberships, self.acl = memberships, acl

    async def _get(self, message, uow):
        transaction = _uow(uow)
        membership = await self.memberships(transaction).get(message.membership_id)
        if membership is None or membership.tenant_id != message.tenant_id:
            raise CatalogDomainError("workspace membership not found")
        await _require_admin(self.memberships, transaction, membership.workspace_id)
        return transaction, membership


class ChangeWorkspaceMemberRoleHandler(
    _MembershipMutation, CommandHandler[ChangeWorkspaceMemberRole, None]
):
    async def handle(self, message, uow=None):
        transaction, membership = await self._get(message, uow)
        if (
            membership.role is WorkspaceRole.ADMIN
            and message.role is not WorkspaceRole.ADMIN
            and len(
                await self.memberships(transaction).list_active_admins(
                    membership.workspace_id
                )
            )
            <= 1
        ):
            raise CatalogDomainError("cannot remove the last workspace administrator")
        membership.change_role(message.role)
        await self.memberships(transaction).save(membership)
        await _sync_role(self.acl, transaction, membership)


class DisableWorkspaceMemberHandler(
    _MembershipMutation, CommandHandler[DisableWorkspaceMember, None]
):
    async def handle(self, message, uow=None):
        transaction, membership = await self._get(message, uow)
        if (
            membership.role is WorkspaceRole.ADMIN
            and len(
                await self.memberships(transaction).list_active_admins(
                    membership.workspace_id
                )
            )
            <= 1
        ):
            raise CatalogDomainError("cannot remove the last workspace administrator")
        membership.disable()
        await self.memberships(transaction).save(membership)
        await _sync_role(self.acl, transaction, membership)


class RestoreWorkspaceMemberHandler(
    _MembershipMutation, CommandHandler[RestoreWorkspaceMember, None]
):
    async def handle(self, message, uow=None):
        transaction, membership = await self._get(message, uow)
        membership.restore_membership()
        await self.memberships(transaction).save(membership)
        await _sync_role(self.acl, transaction, membership)


class RemoveWorkspaceMemberHandler(DisableWorkspaceMemberHandler):
    async def handle(self, message, uow=None):
        return await super().handle(
            DisableWorkspaceMember(message.tenant_id, message.membership_id), uow
        )


class CreateNodeHandler(CommandHandler[CreateNode, NodeId]):
    def __init__(self, workspaces, memberships, nodes, acl, ids):
        self.workspaces, self.memberships, self.nodes, self.acl, self.ids = (
            workspaces,
            memberships,
            nodes,
            acl,
            ids,
        )

    async def handle(self, message, uow=None):
        transaction = _uow(uow)
        workspace = await _workspace(
            self.workspaces, transaction, message.tenant_id, message.workspace_id
        )
        await _require_action(
            self.acl,
            transaction,
            workspace.tenant_id,
            workspace.id,
            CatalogAction.WRITE,
        )
        if message.parent_id:
            parent = await self.nodes(transaction).get(workspace.id, message.parent_id)
            if (
                parent is None
                or parent.is_deleted
                or (
                    message.node_type is NodeType.TERM
                    and parent.node_type not in {NodeType.GLOSSARY_BOOK, NodeType.TERM}
                )
            ):
                raise CatalogDomainError("invalid node parent")
        elif message.node_type is NodeType.TERM:
            raise CatalogDomainError("term must belong to a glossary book or term")
        if await self.nodes(transaction).exists_sibling_name(
            workspace.id, message.parent_id, message.node_type, message.display_name
        ):
            raise CatalogDomainError("node name already exists")
        node = Node.create(
            NodeId(self.ids.new()),
            workspace.tenant_id,
            workspace.id,
            message.parent_id,
            message.node_type,
            message.display_name,
            message.description,
            message.properties,
        )
        await self.nodes(transaction).add(node)
        return node.id


class _NodeMutation(CommandHandler):
    def __init__(self, workspaces, memberships, nodes, acl):
        self.workspaces, self.memberships, self.nodes, self.acl = (
            workspaces,
            memberships,
            nodes,
            acl,
        )

    async def _get(self, message, uow):
        transaction = _uow(uow)
        workspace = await _workspace(
            self.workspaces, transaction, message.tenant_id, message.workspace_id
        )
        node = await self.nodes(transaction).get(workspace.id, message.node_id)
        if node is None or node.is_deleted:
            raise CatalogDomainError("node not found")
        await _require_action(
            self.acl,
            transaction,
            workspace.tenant_id,
            workspace.id,
            CatalogAction.WRITE,
            node.id,
        )
        return transaction, workspace, node


class RenameNodeHandler(_NodeMutation, CommandHandler[RenameNode, None]):
    async def handle(self, message, uow=None):
        transaction, workspace, node = await self._get(message, uow)
        if await self.nodes(transaction).exists_sibling_name(
            workspace.id, node.parent_id, node.node_type, message.display_name, node.id
        ):
            raise CatalogDomainError("node name already exists")
        node.rename(message.display_name)
        await self.nodes(transaction).save(node)


class UpdateNodeHandler(_NodeMutation, CommandHandler[UpdateNode, None]):
    async def handle(self, message, uow=None):
        transaction, _, node = await self._get(message, uow)
        node.update(message.description, message.properties)
        await self.nodes(transaction).save(node)


class MoveNodeHandler(_NodeMutation, CommandHandler[MoveNode, None]):
    async def handle(self, message, uow=None):
        transaction, workspace, node = await self._get(message, uow)
        if message.parent_id:
            parent = await self.nodes(transaction).get(workspace.id, message.parent_id)
            if (
                parent is None
                or parent.is_deleted
                or (
                    node.node_type is NodeType.TERM
                    and parent.node_type not in {NodeType.GLOSSARY_BOOK, NodeType.TERM}
                )
            ):
                raise CatalogDomainError("invalid node parent")
            if await self.nodes(transaction).has_descendant(
                workspace.id, node.id, parent.id
            ):
                raise CatalogDomainError("node cannot be moved into its descendant")
        if await self.nodes(transaction).exists_sibling_name(
            workspace.id, message.parent_id, node.node_type, node.display_name, node.id
        ):
            raise CatalogDomainError("node name already exists")
        node.move(message.parent_id)
        await self.nodes(transaction).save(node)


class DeleteNodeHandler(_NodeMutation, CommandHandler[DeleteNode, None]):
    async def handle(self, message, uow=None):
        transaction = _uow(uow)
        workspace = await _workspace(
            self.workspaces, transaction, message.tenant_id, message.workspace_id
        )
        node = await self.nodes(transaction).get(workspace.id, message.node_id)
        if node is None or node.is_deleted:
            raise CatalogDomainError("node not found")
        await _require_action(
            self.acl,
            transaction,
            workspace.tenant_id,
            workspace.id,
            CatalogAction.DELETE,
            node.id,
        )
        await self.nodes(transaction).soft_delete_subtree(workspace.id, node.id)
        node.delete()
        await self.nodes(transaction).save(node)


class _AclMutation(CommandHandler):
    def __init__(self, workspaces, memberships, nodes, acl):
        self.workspaces, self.memberships, self.nodes, self.acl = (
            workspaces,
            memberships,
            nodes,
            acl,
        )

    async def _authorize(self, message, uow):
        transaction = _uow(uow)
        await _workspace(
            self.workspaces, transaction, message.tenant_id, message.workspace_id
        )
        await _require_admin(self.memberships, transaction, message.workspace_id)
        return transaction


class GrantNodeAccessHandler(_AclMutation, CommandHandler[GrantNodeAccess, None]):
    async def handle(self, message, uow=None):
        transaction = await self._authorize(message, uow)
        if (
            await self.nodes(transaction).get(message.workspace_id, message.node_id)
            is None
        ):
            raise CatalogDomainError("node not found")
        await self.acl.grant(
            tenant_id=message.tenant_id,
            resource_type="node",
            resource_id=str(message.node_id),
            subject=message.subject,
            action=message.action,
            effect=message.effect,
            uow=transaction,
        )


class RevokeNodeAccessHandler(_AclMutation, CommandHandler[RevokeNodeAccess, None]):
    async def handle(self, message, uow=None):
        transaction = await self._authorize(message, uow)
        await self.acl.revoke(
            tenant_id=message.tenant_id,
            resource_type="node",
            resource_id=str(message.node_id),
            subject=message.subject,
            action=message.action,
            uow=transaction,
        )


class GrantWorkspaceAccessHandler(
    _AclMutation, CommandHandler[GrantWorkspaceAccess, None]
):
    async def handle(self, message, uow=None):
        transaction = await self._authorize(message, uow)
        await self.acl.grant(
            tenant_id=message.tenant_id,
            resource_type="workspace",
            resource_id=str(message.workspace_id),
            subject=message.subject,
            action=message.action,
            effect=message.effect,
            uow=transaction,
        )


class RevokeWorkspaceAccessHandler(
    _AclMutation, CommandHandler[RevokeWorkspaceAccess, None]
):
    async def handle(self, message, uow=None):
        transaction = await self._authorize(message, uow)
        await self.acl.revoke(
            tenant_id=message.tenant_id,
            resource_type="workspace",
            resource_id=str(message.workspace_id),
            subject=message.subject,
            action=message.action,
            uow=transaction,
        )


class _CatalogQueries:
    def __init__(self, read, acl):
        self.read, self.acl = read, acl

    async def visible(
        self, tenant_id, workspace_id, node_id, action=CatalogAction.READ
    ):
        actor = _actor()
        path = await self.read.path(workspace_id, node_id)
        scopes = [
            AclScope(tenant_id, "node", str(item.node_id)) for item in reversed(path)
        ]
        scopes.append(AclScope(tenant_id, "workspace", str(workspace_id)))
        decision = await self.acl.check(
            subject=Subject(actor, SubjectType.USER),
            tenant_id=tenant_id,
            action=Action(action.value),
            scopes=scopes,
            uow=None,
        )
        if not decision.permit:
            raise CatalogDomainError("resource not found")


class ListWorkspacesHandler(QueryHandler[ListWorkspaces, Page[WorkspaceDTO]]):
    def __init__(self, store):
        self.store = store

    async def handle(self, message, uow=None):
        return await self.store.list(message.tenant_id, message.keyword, message.page)


class GetWorkspaceHandler(QueryHandler[GetWorkspace, WorkspaceDTO | None]):
    def __init__(self, store):
        self.store = store

    async def handle(self, message, uow=None):
        return await self.store.get(message.tenant_id, message.workspace_id)


class ListWorkspaceMembersHandler(
    QueryHandler[ListWorkspaceMembers, Page[WorkspaceMembershipDTO]]
):
    def __init__(self, store):
        self.store = store

    async def handle(self, message, uow=None):
        return await self.store.list(message.workspace_id, message.page)


class ListNodesHandler(QueryHandler[ListNodes, NodePage]):
    def __init__(self, store, acl=None):
        self.store, self.acl = store, acl

    async def handle(self, message, uow=None):
        result = await self.store.search(
            message.workspace_id,
            message.parent_id,
            message.keyword,
            message.node_type,
            message.page,
        )
        if self.acl is None:
            return result
        visible = []
        actor = _actor()
        for item in result.items:
            path = await self.store.path(message.workspace_id, item.node_id)
            scopes = [
                AclScope(message.tenant_id, "node", str(node.node_id))
                for node in reversed(path)
            ]
            scopes.append(
                AclScope(message.tenant_id, "workspace", str(message.workspace_id))
            )
            decision = await self.acl.check(
                subject=Subject(actor, SubjectType.USER),
                tenant_id=message.tenant_id,
                action=Action(CatalogAction.READ.value),
                scopes=scopes,
                uow=uow,
            )
            if decision.permit:
                visible.append(item)
        return NodePage(tuple(visible), len(visible), result.page, result.size)


class GetNodeHandler(QueryHandler[GetNode, NodeDTO | None]):
    def __init__(self, store, acl=None):
        self.store, self.acl = store, acl

    async def handle(self, message, uow=None):
        value = await self.store.get(message.workspace_id, message.node_id)
        if value is None or self.acl is None:
            return value
        path = await self.store.path(message.workspace_id, message.node_id)
        scopes = [
            AclScope(message.tenant_id, "node", str(node.node_id))
            for node in reversed(path)
        ]
        scopes.append(
            AclScope(message.tenant_id, "workspace", str(message.workspace_id))
        )
        decision = await self.acl.check(
            subject=Subject(_actor(), SubjectType.USER),
            tenant_id=message.tenant_id,
            action=Action(CatalogAction.READ.value),
            scopes=scopes,
            uow=uow,
        )
        return value if decision.permit else None


class GetNodePathHandler(QueryHandler[GetNodePath, tuple[NodeDTO, ...]]):
    def __init__(self, store):
        self.store = store

    async def handle(self, message, uow=None):
        return await self.store.path(message.workspace_id, message.node_id)


class GetNodePermissionsHandler(QueryHandler[GetNodePermissions, NodePermissionDTO]):
    def __init__(self, store, acl):
        self.store, self.acl = store, acl

    async def handle(self, message, uow=None):
        node = await self.store.get(message.workspace_id, message.node_id)
        if node is None:
            raise CatalogDomainError("node not found")
        scopes = [
            AclScope(message.tenant_id, "node", str(message.node_id)),
            AclScope(message.tenant_id, "workspace", str(message.workspace_id)),
        ]
        return NodePermissionDTO(
            message.node_id,
            await self.acl.list_permissions(
                tenant_id=message.tenant_id, scopes=scopes, uow=None
            ),
        )
