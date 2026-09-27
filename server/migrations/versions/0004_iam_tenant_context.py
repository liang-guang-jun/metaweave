"""Make tenant context explicit and add instance administrator identities."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0004_iam_tenant_context"
down_revision = "0003_iam_identity_extensions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Rename tenant membership storage and add system/principal identity roots."""
    op.rename_table("iam_memberships", "iam_tenant_memberships")
    op.add_column(
        "iam_sso_providers",
        sa.Column(
            "client_secret", sa.String(1024), nullable=False, server_default=""
        ),
    )
    op.create_table(
        "iam_system_admins",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "user_id", sa.String(36), sa.ForeignKey("iam_users.id"), nullable=False
        ),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("user_id", name="uq_iam_system_admin_user"),
    )
    op.create_index("ix_iam_system_admins_user_id", "iam_system_admins", ["user_id"])
    op.create_table(
        "iam_principals",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("principal_type", sa.String(32), nullable=False),
    )
    op.execute(
        sa.text(
            "INSERT INTO iam_principals (id, principal_type) "
            "SELECT id, 'USER' FROM iam_users"
            " UNION ALL SELECT id, 'SERVICE_PRINCIPAL' FROM iam_service_principals"
        )
    )
    with op.batch_alter_table("iam_service_principals", recreate="always") as batch:
        batch.create_foreign_key(
            "fk_iam_service_principal_principal", "iam_principals", ["id"], ["id"]
        )
    with op.batch_alter_table("iam_users", recreate="always") as batch:
        batch.create_foreign_key("fk_iam_user_principal", "iam_principals", ["id"], ["id"])


def downgrade() -> None:
    """Restore the previous tenant membership and identity schema."""
    with op.batch_alter_table("iam_service_principals", recreate="always") as batch:
        batch.drop_constraint("fk_iam_service_principal_principal", type_="foreignkey")
    with op.batch_alter_table("iam_users", recreate="always") as batch:
        batch.drop_constraint("fk_iam_user_principal", type_="foreignkey")
    op.drop_table("iam_principals")
    op.drop_index("ix_iam_system_admins_user_id", table_name="iam_system_admins")
    op.drop_table("iam_system_admins")
    op.drop_column("iam_sso_providers", "client_secret")
    op.rename_table("iam_tenant_memberships", "iam_memberships")
