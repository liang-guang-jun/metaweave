"""Move the active lifecycle flag to the polymorphic principal root.

Both human users and service principals are joined-table polymorphic rows.  A
single root-level state makes lifecycle checks consistent for every principal.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0009_principal_lifecycle"
down_revision = "0008_drop_system_admin_table"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "iam_principals",
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    connection = op.get_bind()
    connection.execute(
        sa.text(
            "UPDATE iam_principals SET active = ("
            "SELECT active FROM iam_service_principals "
            "WHERE iam_service_principals.id = iam_principals.id"
            ") WHERE principal_type = 'SERVICE_PRINCIPAL'"
        )
    )
    # SQLite does not support DROP COLUMN on all supported versions; batch
    # recreation also preserves the joined-table foreign key.
    with op.batch_alter_table("iam_service_principals", recreate="always") as batch:
        batch.drop_column("active")


def downgrade() -> None:
    with op.batch_alter_table("iam_service_principals", recreate="always") as batch:
        batch.add_column(
            sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true())
        )
    connection = op.get_bind()
    connection.execute(
        sa.text(
            "UPDATE iam_service_principals SET active = ("
            "SELECT active FROM iam_principals "
            "WHERE iam_principals.id = iam_service_principals.id"
            ")"
        )
    )
    op.drop_column("iam_principals", "active")
