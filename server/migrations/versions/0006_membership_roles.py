"""Persist explicit tenant membership role types."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0006_membership_roles"
down_revision = "0005_membership_lifecycle"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "iam_tenant_memberships",
        sa.Column(
            "membership_type", sa.String(16), nullable=False, server_default="MEMBER"
        ),
    )
    op.execute(
        "UPDATE iam_tenant_memberships SET membership_type = "
        "CASE WHEN is_admin = 1 THEN 'ADMIN' ELSE 'MEMBER' END"
    )


def downgrade() -> None:
    op.drop_column("iam_tenant_memberships", "membership_type")
