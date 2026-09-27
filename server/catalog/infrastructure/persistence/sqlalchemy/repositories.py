from __future__ import annotations

# SQLAlchemy adapter implementations intentionally mirror the existing IAM
# adapters; their public contracts are typed by catalog application ports.
# mypy: ignore-errors
# ruff: noqa

from sqlalchemy import delete, func, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from .....kernel.application.common.page import Page, PageRequest
from .....kernel.application.unit_of_work import UnitOfWork
from .....kernel.infrastructure.persistence.sqlalchemy.unit_of_work import SqlAlchemyUnitOfWork
from ....application.dto import NodeDTO, NodePage, WorkspaceDTO, WorkspaceMembershipDTO
from ....application.ports import *
from ....domain.entities import Node, Workspace, WorkspaceMembership
from ....domain.value_objects import *
from .....iam.domain.value_objects import TenantId, UserId
from .models import *


def _session(uow: UnitOfWork) -> AsyncSession:
    if not isinstance(uow, SqlAlchemyUnitOfWork):
        raise TypeError("Catalog repositories require SqlAlchemyUnitOfWork")
    return uow.session


class SqlAlchemyWorkspaceRepository(WorkspaceRepository):
    def __init__(self, uow): self.session, self.uow = _session(uow), uow
    async def get(self, tenant_id, workspace_id):
        row = await self.session.scalar(select(CatalogWorkspaceRecord).where(CatalogWorkspaceRecord.id == str(workspace_id), CatalogWorkspaceRecord.tenant_id == str(tenant_id)))
        if row is None: return None
        value = Workspace.restore(WorkspaceId(row.id), TenantId(row.tenant_id), row.display_name, row.description, row.active, row.version); self.uow.track(value); return value
    async def add(self, workspace):
        self.session.add(CatalogWorkspaceRecord(id=str(workspace.id), tenant_id=str(workspace.tenant_id), display_name=workspace.display_name, description=workspace.description, active=workspace.active, version=workspace.version))
        # Workspace memberships reference this row. The catalog models do not
        # define an ORM relationship, so flush the parent before subsequent
        # membership/ACL queries can trigger an autoflush.
        await self.session.flush()
        self.uow.track(workspace)
    async def save(self, workspace):
        row = await self.session.get(CatalogWorkspaceRecord, str(workspace.id))
        if row is None: return await self.add(workspace)
        row.display_name, row.description, row.active, row.version = workspace.display_name, workspace.description, workspace.active, workspace.version
    async def exists_name(self, tenant_id, display_name, exclude=None):
        query = select(func.count()).select_from(CatalogWorkspaceRecord).where(CatalogWorkspaceRecord.tenant_id == str(tenant_id), CatalogWorkspaceRecord.display_name == display_name.strip())
        if exclude: query = query.where(CatalogWorkspaceRecord.id != str(exclude))
        return bool(await self.session.scalar(query))


class SqlAlchemyWorkspaceMembershipRepository(WorkspaceMembershipRepository):
    def __init__(self, uow): self.session, self.uow = _session(uow), uow
    @staticmethod
    def _value(row): return WorkspaceMembership.restore(WorkspaceMembershipId(row.id), WorkspaceId(row.workspace_id), TenantId(row.tenant_id), UserId(row.user_id), WorkspaceRole(row.role), row.active, row.joined_at, row.version)
    async def get(self, membership_id):
        row = await self.session.get(CatalogWorkspaceMembershipRecord, str(membership_id));
        if row is None: return None
        value = self._value(row); self.uow.track(value); return value
    async def find(self, workspace_id, user_id):
        row = await self.session.scalar(select(CatalogWorkspaceMembershipRecord).where(CatalogWorkspaceMembershipRecord.workspace_id == str(workspace_id), CatalogWorkspaceMembershipRecord.user_id == str(user_id)))
        if row is None: return None
        value = self._value(row); self.uow.track(value); return value
    async def list_active_admins(self, workspace_id):
        rows = (await self.session.scalars(select(CatalogWorkspaceMembershipRecord).where(CatalogWorkspaceMembershipRecord.workspace_id == str(workspace_id), CatalogWorkspaceMembershipRecord.active.is_(True), CatalogWorkspaceMembershipRecord.role == WorkspaceRole.ADMIN.value))).all()
        return [self._value(row) for row in rows]
    async def add(self, membership):
        self.session.add(CatalogWorkspaceMembershipRecord(id=str(membership.id), tenant_id=str(membership.tenant_id), workspace_id=str(membership.workspace_id), user_id=str(membership.user_id), role=membership.role.value, active=membership.active, joined_at=membership.joined_at, version=membership.version)); self.uow.track(membership)
    async def save(self, membership):
        row = await self.session.get(CatalogWorkspaceMembershipRecord, str(membership.id))
        if row is None: return await self.add(membership)
        row.role, row.active, row.joined_at, row.version = membership.role.value, membership.active, membership.joined_at, membership.version
    async def remove(self, membership): await self.session.execute(delete(CatalogWorkspaceMembershipRecord).where(CatalogWorkspaceMembershipRecord.id == str(membership.id)))


class SqlAlchemyNodeRepository(NodeRepository):
    def __init__(self, uow): self.session, self.uow = _session(uow), uow
    @staticmethod
    def _value(row): return Node.restore(NodeId(row.id), TenantId(row.tenant_id), WorkspaceId(row.workspace_id), NodeId(row.parent_id) if row.parent_id else None, NodeType(row.node_type), row.display_name, row.description, row.properties or {}, row.is_deleted, row.version)
    async def get(self, workspace_id, node_id):
        row = await self.session.scalar(select(CatalogNodeRecord).where(CatalogNodeRecord.id == str(node_id), CatalogNodeRecord.workspace_id == str(workspace_id)))
        if row is None: return None
        value = self._value(row); self.uow.track(value); return value
    async def add(self, node):
        self.session.add(CatalogNodeRecord(id=str(node.id), tenant_id=str(node.tenant_id), workspace_id=str(node.workspace_id), parent_id=str(node.parent_id) if node.parent_id else None, node_type=node.node_type.value, display_name=node.display_name, description=node.description, properties=node.properties, is_deleted=node.is_deleted, version=node.version)); self.uow.track(node)
    async def save(self, node):
        row = await self.session.get(CatalogNodeRecord, str(node.id))
        if row is None: return await self.add(node)
        row.parent_id, row.display_name, row.description, row.properties, row.is_deleted, row.version = str(node.parent_id) if node.parent_id else None, node.display_name, node.description, node.properties, node.is_deleted, node.version
    async def exists_sibling_name(self, workspace_id, parent_id, node_type, display_name, exclude=None):
        query = select(func.count()).select_from(CatalogNodeRecord).where(CatalogNodeRecord.workspace_id == str(workspace_id), CatalogNodeRecord.node_type == node_type.value, CatalogNodeRecord.display_name == display_name.strip(), CatalogNodeRecord.is_deleted.is_(False))
        query = query.where(CatalogNodeRecord.parent_id.is_(None) if parent_id is None else CatalogNodeRecord.parent_id == str(parent_id))
        if exclude: query = query.where(CatalogNodeRecord.id != str(exclude))
        return bool(await self.session.scalar(query))
    async def has_descendant(self, workspace_id, ancestor_id, candidate_id):
        sql = text("WITH RECURSIVE tree(id) AS (SELECT id FROM catalog_nodes WHERE id=:root UNION ALL SELECT n.id FROM catalog_nodes n JOIN tree t ON n.parent_id=t.id) SELECT 1 FROM tree WHERE id=:candidate LIMIT 1")
        return (await self.session.scalar(sql, {"root": str(ancestor_id), "candidate": str(candidate_id)})) is not None
    async def soft_delete_subtree(self, workspace_id, node_id):
        await self.session.execute(text("WITH RECURSIVE tree(id) AS (SELECT id FROM catalog_nodes WHERE id=:root AND workspace_id=:workspace UNION ALL SELECT n.id FROM catalog_nodes n JOIN tree t ON n.parent_id=t.id) UPDATE catalog_nodes SET is_deleted=1 WHERE id IN (SELECT id FROM tree)"), {"root": str(node_id), "workspace": str(workspace_id)})


class SqlAlchemyCatalogReadStore:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self.session_factory = session_factory
    @staticmethod
    def _node(row): return NodeDTO(NodeId(row.id), WorkspaceId(row.workspace_id), NodeId(row.parent_id) if row.parent_id else None, NodeType(row.node_type), row.display_name, row.description, row.properties or {}, row.is_deleted)
    async def get(self, workspace_id, node_id):
        async with self.session_factory() as session:
            row = await session.scalar(select(CatalogNodeRecord).where(CatalogNodeRecord.workspace_id == str(workspace_id), CatalogNodeRecord.id == str(node_id), CatalogNodeRecord.is_deleted.is_(False)))
            return None if row is None else self._node(row)
    async def search(self, workspace_id, parent_id, keyword, node_type, page):
        async with self.session_factory() as session:
            query = select(CatalogNodeRecord).where(CatalogNodeRecord.workspace_id == str(workspace_id), CatalogNodeRecord.is_deleted.is_(False))
            query = query.where(CatalogNodeRecord.parent_id.is_(None) if parent_id is None else CatalogNodeRecord.parent_id == str(parent_id))
            if keyword.strip(): query = query.where(CatalogNodeRecord.display_name.ilike(f"%{keyword.strip()}%"))
            if node_type: query = query.where(CatalogNodeRecord.node_type == node_type.value)
            total = int(await session.scalar(select(func.count()).select_from(query.subquery())) or 0)
            rows = (await session.scalars(query.order_by(CatalogNodeRecord.display_name, CatalogNodeRecord.id).offset(page.offset).limit(page.limit))).all()
            return NodePage(tuple(self._node(row) for row in rows), total, page.page, page.size)
    async def path(self, workspace_id, node_id):
        async with self.session_factory() as session:
            rows = (await session.execute(text("WITH RECURSIVE path AS (SELECT * FROM catalog_nodes WHERE id=:node AND workspace_id=:workspace UNION ALL SELECT n.* FROM catalog_nodes n JOIN path p ON p.parent_id=n.id) SELECT * FROM path"), {"node": str(node_id), "workspace": str(workspace_id)})).mappings().all()
            return tuple(NodeDTO(NodeId(row["id"]), WorkspaceId(row["workspace_id"]), NodeId(row["parent_id"]) if row["parent_id"] else None, NodeType(row["node_type"]), row["display_name"], row["description"], row["properties"] or {}, row["is_deleted"]) for row in reversed(rows))


class SqlAlchemyWorkspaceReadStore:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self.session_factory = session_factory
    async def get(self, tenant_id, workspace_id):
        async with self.session_factory() as session:
            row = await session.scalar(select(CatalogWorkspaceRecord).where(CatalogWorkspaceRecord.tenant_id == str(tenant_id), CatalogWorkspaceRecord.id == str(workspace_id)))
            return None if row is None else WorkspaceDTO(WorkspaceId(row.id), TenantId(row.tenant_id), row.display_name, row.description, row.active)
    async def list(self, tenant_id, keyword, page):
        async with self.session_factory() as session:
            query = select(CatalogWorkspaceRecord).where(CatalogWorkspaceRecord.tenant_id == str(tenant_id), CatalogWorkspaceRecord.active.is_(True))
            if keyword.strip(): query = query.where(CatalogWorkspaceRecord.display_name.ilike(f"%{keyword.strip()}%"))
            total = int(await session.scalar(select(func.count()).select_from(query.subquery())) or 0)
            rows = (await session.scalars(query.order_by(CatalogWorkspaceRecord.display_name).offset(page.offset).limit(page.limit))).all()
            return Page(tuple(WorkspaceDTO(WorkspaceId(row.id), TenantId(row.tenant_id), row.display_name, row.description, row.active) for row in rows), total, page.page, page.size)


class SqlAlchemyWorkspaceMembershipReadStore:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self.session_factory = session_factory
    async def list(self, workspace_id, page):
        async with self.session_factory() as session:
            query = select(CatalogWorkspaceMembershipRecord).where(CatalogWorkspaceMembershipRecord.workspace_id == str(workspace_id))
            total = int(await session.scalar(select(func.count()).select_from(query.subquery())) or 0)
            rows = (await session.scalars(query.order_by(CatalogWorkspaceMembershipRecord.id).offset(page.offset).limit(page.limit))).all()
            return Page(tuple(WorkspaceMembershipDTO(WorkspaceMembershipId(row.id), WorkspaceId(row.workspace_id), UserId(row.user_id), WorkspaceRole(row.role), row.active, row.joined_at) for row in rows), total, page.page, page.size)
