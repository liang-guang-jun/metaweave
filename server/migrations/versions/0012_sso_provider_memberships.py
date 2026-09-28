"""Separate SSO provider definitions from tenant memberships."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0012_sso_provider_memberships"
down_revision = "0011_postgresql_migration_compatibility"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if op.get_bind().dialect.name == "sqlite":
        op.execute("PRAGMA foreign_keys=OFF")
    op.create_table(
        "iam_sso_provider_memberships",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "provider_id",
            sa.String(36),
            sa.ForeignKey("iam_sso_providers.id"),
            nullable=False,
        ),
        sa.Column(
            "tenant_id", sa.String(36), sa.ForeignKey("iam_tenants.id"), nullable=False
        ),
        sa.UniqueConstraint(
            "provider_id", "tenant_id", name="uq_iam_sso_provider_membership"
        ),
    )
    bind = op.get_bind()
    rows = bind.execute(sa.text("SELECT id, tenant_id FROM iam_sso_providers")).all()
    from uuid import uuid4

    for provider_id, tenant_id in rows:
        bind.execute(
            sa.text(
                "INSERT INTO iam_sso_provider_memberships (id, provider_id, tenant_id) VALUES (:id, :provider_id, :tenant_id)"
            ),
            {"id": str(uuid4()), "provider_id": provider_id, "tenant_id": tenant_id},
        )
    with op.batch_alter_table("iam_sso_providers") as batch:
        batch.drop_constraint("uq_iam_sso_provider_issuer", type_="unique")
        batch.drop_index("ix_iam_sso_provider_tenant")
        batch.drop_column("tenant_id")
        batch.add_column(
            sa.Column(
                "is_global", sa.Boolean(), nullable=False, server_default=sa.false()
            )
        )
        batch.create_unique_constraint("uq_iam_sso_provider_issuer", ["issuer"])
    if op.get_bind().dialect.name == "sqlite":
        op.execute("PRAGMA foreign_keys=ON")


def downgrade() -> None:
    raise RuntimeError(
        "SSO provider membership migration cannot be reversed without losing shared provider data"
    )
