"""Add IAM groups, federated identities, service principals and API keys."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0003_iam_identity_extensions"
down_revision = "0002_iam_acl"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create identity-extension tables and graph lookup indexes."""
    op.create_table(
        "iam_groups",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "tenant_id", sa.String(36), sa.ForeignKey("iam_tenants.id"), nullable=False
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="0"),
        sa.UniqueConstraint("tenant_id", "name", name="uq_iam_group_tenant_name"),
    )
    op.create_index("ix_iam_group_tenant", "iam_groups", ["tenant_id"])
    op.create_table(
        "iam_group_members",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "group_id",
            sa.String(36),
            sa.ForeignKey("iam_groups.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("member_type", sa.String(16), nullable=False),
        sa.Column("member_id", sa.String(36), nullable=False),
        sa.UniqueConstraint(
            "group_id", "member_type", "member_id", name="uq_iam_group_member"
        ),
    )
    op.create_index("ix_iam_group_member_parent", "iam_group_members", ["group_id"])
    op.create_index(
        "ix_iam_group_member_child", "iam_group_members", ["member_type", "member_id"]
    )
    op.create_table(
        "iam_sso_providers",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "tenant_id", sa.String(36), sa.ForeignKey("iam_tenants.id"), nullable=False
        ),
        sa.Column("issuer", sa.String(512), nullable=False),
        sa.Column("client_id", sa.String(255), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("version", sa.Integer(), nullable=False, server_default="0"),
        sa.UniqueConstraint("tenant_id", "issuer", name="uq_iam_sso_provider_issuer"),
    )
    op.create_index("ix_iam_sso_provider_tenant", "iam_sso_providers", ["tenant_id"])
    op.create_table(
        "iam_external_sso_identities",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "user_id", sa.String(36), sa.ForeignKey("iam_users.id"), nullable=False
        ),
        sa.Column(
            "provider_id",
            sa.String(36),
            sa.ForeignKey("iam_sso_providers.id"),
            nullable=False,
        ),
        sa.Column("external_subject", sa.String(512), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="0"),
        sa.UniqueConstraint(
            "provider_id", "external_subject", name="uq_iam_sso_subject"
        ),
    )
    op.create_index(
        "ix_iam_sso_identity_user", "iam_external_sso_identities", ["user_id"]
    )
    op.create_table(
        "iam_service_principals",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "tenant_id", sa.String(36), sa.ForeignKey("iam_tenants.id"), nullable=False
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("version", sa.Integer(), nullable=False, server_default="0"),
        sa.UniqueConstraint("tenant_id", "name", name="uq_iam_service_principal_name"),
    )
    op.create_index(
        "ix_iam_service_principal_tenant", "iam_service_principals", ["tenant_id"]
    )
    op.create_table(
        "iam_api_keys",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "principal_id",
            sa.String(36),
            sa.ForeignKey("iam_service_principals.id"),
            nullable=False,
        ),
        sa.Column("secret_hash", sa.String(512), nullable=False),
        sa.Column("revoked", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("version", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_index(
        "ix_iam_api_key_principal", "iam_api_keys", ["principal_id", "revoked"]
    )


def downgrade() -> None:
    """Drop only identity-extension tables."""
    op.drop_index("ix_iam_api_key_principal", table_name="iam_api_keys")
    op.drop_table("iam_api_keys")
    op.drop_index(
        "ix_iam_service_principal_tenant", table_name="iam_service_principals"
    )
    op.drop_table("iam_service_principals")
    op.drop_index("ix_iam_sso_identity_user", table_name="iam_external_sso_identities")
    op.drop_table("iam_external_sso_identities")
    op.drop_index("ix_iam_sso_provider_tenant", table_name="iam_sso_providers")
    op.drop_table("iam_sso_providers")
    op.drop_index("ix_iam_group_tenant", table_name="iam_groups")
    op.drop_index("ix_iam_group_member_child", table_name="iam_group_members")
    op.drop_index("ix_iam_group_member_parent", table_name="iam_group_members")
    op.drop_table("iam_group_members")
    op.drop_table("iam_groups")
