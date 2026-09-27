"""Persist lifecycle state for tenant group memberships."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0005_membership_lifecycle"
down_revision = "0004_iam_tenant_context"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "iam_group_members",
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.add_column(
        "iam_group_members",
        sa.Column("version", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("iam_group_members", "version")
    op.drop_column("iam_group_members", "active")
