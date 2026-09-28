"""Repair schemas affected by earlier PostgreSQL-compatible migrations.

Historical revisions 0004 and 0009 used SQLite's batch-table strategy for
every dialect.  On PostgreSQL-compatible databases, replacing
``iam_service_principals`` can fail because ``iam_api_keys`` references its
primary key.  This revision repairs only databases which reached 0010 with a
missing joined-table foreign key or a leftover lifecycle column.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import context, op

revision = "0011_postgresql_migration_compatibility"
down_revision = "0010_catalog"
branch_labels = None
depends_on = None


_PRINCIPAL_FOREIGN_KEYS = (
    ("iam_service_principals", "fk_iam_service_principal_principal"),
    ("iam_users", "fk_iam_user_principal"),
)


def _has_principal_foreign_key(inspector: sa.Inspector, table_name: str) -> bool:
    """Return whether ``table_name.id`` references ``iam_principals.id``."""
    return any(
        foreign_key["referred_table"] == "iam_principals"
        and foreign_key["constrained_columns"] == ["id"]
        and foreign_key["referred_columns"] == ["id"]
        for foreign_key in inspector.get_foreign_keys(table_name)
    )


def _create_principal_foreign_key(table_name: str, constraint_name: str) -> None:
    """Add a joined-table principal foreign key without needless recreation."""
    if op.get_bind().dialect.name == "sqlite":
        with op.batch_alter_table(table_name, recreate="always") as batch:
            batch.create_foreign_key(constraint_name, "iam_principals", ["id"], ["id"])
    else:
        op.create_foreign_key(
            constraint_name,
            table_name,
            "iam_principals",
            ["id"],
            ["id"],
        )


def _drop_service_principal_active() -> None:
    """Remove the lifecycle column left behind by the old 0009 revision."""
    if op.get_bind().dialect.name == "sqlite":
        with op.batch_alter_table("iam_service_principals", recreate="always") as batch:
            batch.drop_column("active")
    else:
        op.drop_column("iam_service_principals", "active")


def upgrade() -> None:
    """Bring historical PostgreSQL/Lakebase schemas in line with the ORM."""
    if context.is_offline_mode():
        if op.get_context().dialect.name != "sqlite":
            op.execute(
                "ALTER TABLE alembic_version ALTER COLUMN version_num TYPE VARCHAR(64)"
            )
        return
    connection = op.get_bind()
    if connection.dialect.name != "sqlite":
        # Alembic's default version table is VARCHAR(32), while this
        # descriptive revision identifier is longer.  Widen it before Alembic
        # records the new revision at the end of this migration.
        connection.execute(
            sa.text(
                "ALTER TABLE alembic_version ALTER COLUMN version_num TYPE VARCHAR(64)"
            )
        )
    inspector = sa.inspect(connection)
    if not inspector.has_table("iam_principals"):
        return

    for table_name, constraint_name in _PRINCIPAL_FOREIGN_KEYS:
        if inspector.has_table(table_name) and not _has_principal_foreign_key(
            inspector, table_name
        ):
            _create_principal_foreign_key(table_name, constraint_name)

    if inspector.has_table("iam_service_principals") and any(
        column["name"] == "active"
        for column in inspector.get_columns("iam_service_principals")
    ):
        _drop_service_principal_active()


def downgrade() -> None:
    """Keep compatibility repairs when returning to the catalog revision."""
