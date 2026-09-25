"""Reusable event-id deduplication primitive for SQLite read projections."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import DateTime, Integer, String, UniqueConstraint, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from .persistence.sqlalchemy.models import Base


class ProjectionCheckpoint(Base):
    """Per-projection event receipt used to make at-least-once delivery idempotent."""

    __tablename__ = "kernel_projection_checkpoint"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    projection_name: Mapped[str] = mapped_column(String(255), index=True)
    event_id: Mapped[str] = mapped_column(String(36))
    processed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    __table_args__ = (UniqueConstraint("projection_name", "event_id"),)


async def claim_projection_event(
    session: AsyncSession, projection_name: str, event_id: str
) -> bool:
    """Record receipt in the caller's transaction; return false for duplicates."""
    exists = await session.scalar(
        select(ProjectionCheckpoint.id).where(
            ProjectionCheckpoint.projection_name == projection_name,
            ProjectionCheckpoint.event_id == event_id,
        )
    )
    if exists is not None:
        return False
    try:
        async with session.begin_nested():
            session.add(
                ProjectionCheckpoint(
                    projection_name=projection_name,
                    event_id=event_id,
                    processed_at=datetime.now(UTC),
                )
            )
            await session.flush()
    except IntegrityError:
        return False
    return True
