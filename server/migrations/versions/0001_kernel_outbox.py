"""Create durable outbox and projection-deduplication tables.

Revision ID: 0001_kernel_outbox
Revises: None
Create Date: 2026-09-26
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0001_kernel_outbox"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create kernel-owned SQLite-compatible persistence tables and indexes."""
    op.create_table(
        "kernel_outbox",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("event_id", sa.String(length=36), nullable=False, unique=True),
        sa.Column("event_type", sa.String(length=255), nullable=False),
        sa.Column("schema_version", sa.Integer(), nullable=False),
        sa.Column("aggregate_type", sa.String(length=255), nullable=False),
        sa.Column("aggregate_id", sa.String(length=255), nullable=False),
        sa.Column("aggregate_version", sa.Integer(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("correlation_id", sa.String(length=255)),
        sa.Column("causation_id", sa.String(length=255)),
        sa.Column("tenant_id", sa.String(length=255)),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column(
            "status", sa.String(length=16), nullable=False, server_default="pending"
        ),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True)),
        sa.Column("last_error", sa.Text()),
    )
    op.create_index("ix_kernel_outbox_event_id", "kernel_outbox", ["event_id"])
    op.create_index(
        "ix_kernel_outbox_pending",
        "kernel_outbox",
        ["status", "next_attempt_at", "id"],
    )
    op.create_table(
        "kernel_projection_checkpoint",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("projection_name", sa.String(length=255), nullable=False),
        sa.Column("event_id", sa.String(length=36), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("projection_name", "event_id"),
    )
    op.create_index(
        "ix_kernel_projection_checkpoint_projection_name",
        "kernel_projection_checkpoint",
        ["projection_name"],
    )


def downgrade() -> None:
    """Remove only tables introduced by this initial kernel revision."""
    op.drop_index(
        "ix_kernel_projection_checkpoint_projection_name",
        table_name="kernel_projection_checkpoint",
    )
    op.drop_table("kernel_projection_checkpoint")
    op.drop_index("ix_kernel_outbox_pending", table_name="kernel_outbox")
    op.drop_index("ix_kernel_outbox_event_id", table_name="kernel_outbox")
    op.drop_table("kernel_outbox")
