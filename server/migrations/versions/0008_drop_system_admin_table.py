"""Remove the obsolete system-administrator relationship table.

Instance administration is represented exclusively by the system ACL scope:
``(SYSTEM_TENANT_ID, "system", "instance")`` and the
``system.super_admin`` action.
"""

from __future__ import annotations

from alembic import op

revision = "0008_drop_system_admin_table"
down_revision = "0007_system_admin_roles"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_index("ix_iam_system_admins_user_id", table_name="iam_system_admins")
    op.drop_table("iam_system_admins")


def downgrade() -> None:
    # The prior table was derived state. Restoring its structure does not
    # recreate ACL-derived grants, which remain the authorization source.
    import sqlalchemy as sa

    op.create_table(
        "iam_system_admins",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("role", sa.String(32), nullable=False, server_default="SUPER_ADMIN"),
        sa.Column("version", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("user_id", name="uq_iam_system_admin_user"),
    )
    op.create_index("ix_iam_system_admins_user_id", "iam_system_admins", ["user_id"])
