"""Create IAM users, memberships, sessions and ACL tables."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0002_iam_acl"
down_revision = "0001_kernel_outbox"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "iam_users",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("email", sa.String(320), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(512), nullable=False),
        sa.Column("verified", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("version", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_index("ix_iam_users_email", "iam_users", ["email"])
    op.create_table(
        "iam_tenants",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("version", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_table(
        "iam_memberships",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "tenant_id", sa.String(36), sa.ForeignKey("iam_tenants.id"), nullable=False
        ),
        sa.Column(
            "user_id", sa.String(36), sa.ForeignKey("iam_users.id"), nullable=False
        ),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_admin", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("joined_at", sa.DateTime(timezone=True)),
        sa.Column("version", sa.Integer(), nullable=False, server_default="0"),
        sa.UniqueConstraint(
            "tenant_id", "user_id", name="uq_iam_membership_tenant_user"
        ),
    )
    op.create_index("ix_iam_memberships_tenant_id", "iam_memberships", ["tenant_id"])
    op.create_index("ix_iam_memberships_user_id", "iam_memberships", ["user_id"])
    op.create_index(
        "ix_iam_membership_tenant_active", "iam_memberships", ["tenant_id", "active"]
    )
    op.create_table(
        "iam_invitations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), nullable=False),
        sa.Column("user_id", sa.String(36), nullable=False),
        sa.Column("token_hash", sa.String(512), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("accepted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("revoked", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("version", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_table(
        "iam_sessions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), nullable=False),
        sa.Column("tenant_id", sa.String(36), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("version", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_index("ix_iam_sessions_user_id", "iam_sessions", ["user_id"])
    op.create_index("ix_iam_sessions_tenant_id", "iam_sessions", ["tenant_id"])
    op.create_table(
        "iam_acls",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), nullable=False),
        sa.Column("resource_type", sa.String(255), nullable=False),
        sa.Column("resource_id", sa.String(255), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="0"),
        sa.UniqueConstraint(
            "tenant_id", "resource_type", "resource_id", name="uq_iam_acl_scope"
        ),
    )
    op.create_index(
        "ix_iam_acl_scope", "iam_acls", ["tenant_id", "resource_type", "resource_id"]
    )
    op.create_table(
        "iam_acl_entries",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "acl_id",
            sa.String(36),
            sa.ForeignKey("iam_acls.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("subject_type", sa.String(32), nullable=False),
        sa.Column("subject_id", sa.String(36), nullable=False),
        sa.Column("action", sa.String(255), nullable=False),
        sa.Column("effect", sa.String(16), nullable=False),
        sa.UniqueConstraint(
            "acl_id", "subject_type", "subject_id", "action", name="uq_iam_acl_entry"
        ),
    )
    op.create_index(
        "ix_iam_acl_entry_lookup", "iam_acl_entries", ["acl_id", "subject_id", "action"]
    )
    op.create_table(
        "iam_acl_decision_entries",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.String(36), nullable=False),
        sa.Column("resource_type", sa.String(255), nullable=False),
        sa.Column("resource_id", sa.String(255), nullable=False),
        sa.Column("subject_type", sa.String(32), nullable=False),
        sa.Column("subject_id", sa.String(36), nullable=False),
        sa.Column("action", sa.String(255), nullable=False),
        sa.Column("effect", sa.String(16), nullable=False),
        sa.Column("source_event_id", sa.String(36)),
        sa.UniqueConstraint(
            "tenant_id",
            "resource_type",
            "resource_id",
            "subject_type",
            "subject_id",
            "action",
            name="uq_iam_acl_decision",
        ),
    )
    op.create_index(
        "ix_iam_acl_decision_lookup",
        "iam_acl_decision_entries",
        ["tenant_id", "resource_type", "resource_id", "subject_id", "action"],
    )


def downgrade() -> None:
    op.drop_index("ix_iam_acl_decision_lookup", table_name="iam_acl_decision_entries")
    op.drop_table("iam_acl_decision_entries")
    op.drop_index("ix_iam_acl_entry_lookup", table_name="iam_acl_entries")
    op.drop_table("iam_acl_entries")
    op.drop_index("ix_iam_acl_scope", table_name="iam_acls")
    op.drop_table("iam_acls")
    op.drop_index("ix_iam_sessions_tenant_id", table_name="iam_sessions")
    op.drop_index("ix_iam_sessions_user_id", table_name="iam_sessions")
    op.drop_table("iam_sessions")
    op.drop_table("iam_invitations")
    op.drop_index("ix_iam_membership_tenant_active", table_name="iam_memberships")
    op.drop_index("ix_iam_memberships_user_id", table_name="iam_memberships")
    op.drop_index("ix_iam_memberships_tenant_id", table_name="iam_memberships")
    op.drop_table("iam_memberships")
    op.drop_table("iam_tenants")
    op.drop_index("ix_iam_users_email", table_name="iam_users")
    op.drop_table("iam_users")
