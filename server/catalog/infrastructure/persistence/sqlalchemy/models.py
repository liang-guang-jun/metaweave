from __future__ import annotations

# ORM mappings are consumed through application ports.
# ruff: noqa
# mypy: ignore-errors

from datetime import datetime
from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column
from .....kernel.infrastructure.persistence.sqlalchemy.models import Base


class CatalogWorkspaceRecord(Base):
    __tablename__ = "catalog_workspaces"
    __table_args__ = (
        UniqueConstraint("tenant_id", "display_name", name="uq_catalog_workspace_name"),
        Index("ix_catalog_workspace_tenant", "tenant_id", "active"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("iam_tenants.id"), index=True
    )
    display_name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(String(2000), default="")
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class CatalogWorkspaceMembershipRecord(Base):
    __tablename__ = "catalog_workspace_memberships"
    __table_args__ = (
        UniqueConstraint("workspace_id", "user_id", name="uq_catalog_workspace_member"),
        Index("ix_catalog_workspace_member_workspace", "workspace_id", "active"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("iam_tenants.id"))
    workspace_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("catalog_workspaces.id", ondelete="CASCADE")
    )
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("iam_users.id"))
    role: Mapped[str] = mapped_column(String(16))
    active: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    joined_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    version: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class CatalogNodeRecord(Base):
    __tablename__ = "catalog_nodes"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id",
            "parent_id",
            "node_type",
            "display_name",
            name="uq_catalog_node_sibling_name",
        ),
        Index(
            "ix_catalog_node_lookup",
            "workspace_id",
            "parent_id",
            "is_deleted",
            "node_type",
        ),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("iam_tenants.id"), index=True
    )
    workspace_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("catalog_workspaces.id", ondelete="CASCADE"), index=True
    )
    parent_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("catalog_nodes.id"), nullable=True, index=True
    )
    node_type: Mapped[str] = mapped_column(String(32))
    display_name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(String(2000), default="")
    properties: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
