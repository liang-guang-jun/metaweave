"""Create catalog workspaces, memberships and directory nodes."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0010_catalog"
down_revision = "0009_principal_lifecycle"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "catalog_workspaces",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("iam_tenants.id"), nullable=False),
        sa.Column("display_name", sa.String(255), nullable=False),
        sa.Column("description", sa.String(2000), nullable=False, server_default=""),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("version", sa.Integer(), nullable=False, server_default="0"),
        sa.UniqueConstraint("tenant_id", "display_name", name="uq_catalog_workspace_name"),
    )
    op.create_index("ix_catalog_workspace_tenant", "catalog_workspaces", ["tenant_id", "active"])
    op.create_table(
        "catalog_workspace_memberships",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("iam_tenants.id"), nullable=False),
        sa.Column("workspace_id", sa.String(36), sa.ForeignKey("catalog_workspaces.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("iam_users.id"), nullable=False),
        sa.Column("role", sa.String(16), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("joined_at", sa.DateTime(timezone=True)),
        sa.Column("version", sa.Integer(), nullable=False, server_default="0"),
        sa.UniqueConstraint("workspace_id", "user_id", name="uq_catalog_workspace_member"),
    )
    op.create_index("ix_catalog_workspace_member_workspace", "catalog_workspace_memberships", ["workspace_id", "active"])
    op.create_table(
        "catalog_nodes",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("iam_tenants.id"), nullable=False),
        sa.Column("workspace_id", sa.String(36), sa.ForeignKey("catalog_workspaces.id", ondelete="CASCADE"), nullable=False),
        sa.Column("parent_id", sa.String(36), sa.ForeignKey("catalog_nodes.id")),
        sa.Column("node_type", sa.String(32), nullable=False),
        sa.Column("display_name", sa.String(255), nullable=False),
        sa.Column("description", sa.String(2000), nullable=False, server_default=""),
        sa.Column("properties", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("version", sa.Integer(), nullable=False, server_default="0"),
        sa.UniqueConstraint("workspace_id", "parent_id", "node_type", "display_name", name="uq_catalog_node_sibling_name"),
    )
    op.create_index("ix_catalog_node_lookup", "catalog_nodes", ["workspace_id", "parent_id", "is_deleted", "node_type"])


def downgrade() -> None:
    op.drop_index("ix_catalog_node_lookup", table_name="catalog_nodes")
    op.drop_table("catalog_nodes")
    op.drop_index("ix_catalog_workspace_member_workspace", table_name="catalog_workspace_memberships")
    op.drop_table("catalog_workspace_memberships")
    op.drop_index("ix_catalog_workspace_tenant", table_name="catalog_workspaces")
    op.drop_table("catalog_workspaces")
