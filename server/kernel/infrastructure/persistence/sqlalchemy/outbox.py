"""SQLAlchemy persistence adapter for the transactional integration outbox."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ....application.event.integration import IntegrationEvent
from ....application.event.outbox import Outbox
from .models import OutboxRecord


class SqlAlchemyOutbox(Outbox):
    """Store integration events in the session's current database transaction."""

    def __init__(self, session: AsyncSession) -> None:
        """Bind this outbox adapter to the active SQLAlchemy session."""
        self._session = session

    async def append(self, event: IntegrationEvent) -> None:
        """Add an event without committing the caller's transaction."""
        self._session.add(
            OutboxRecord(
                event_id=event.event_id,
                event_type=event.event_type,
                schema_version=event.schema_version,
                aggregate_type=event.aggregate_type,
                aggregate_id=event.aggregate_id,
                aggregate_version=event.aggregate_version,
                occurred_at=event.occurred_at,
                correlation_id=event.correlation_id,
                causation_id=event.causation_id,
                tenant_id=event.tenant_id,
                payload=event.payload,
                next_attempt_at=datetime.now(UTC),
            )
        )

    async def pending(self, limit: int) -> list[IntegrationEvent]:
        """Read ready records ordered by creation ID for a single dispatcher."""
        if limit < 1:
            raise ValueError("limit must be positive")
        result = await self._session.scalars(
            select(OutboxRecord)
            .where(
                OutboxRecord.status == "pending",
                OutboxRecord.next_attempt_at <= datetime.now(UTC),
            )
            .order_by(OutboxRecord.id)
            .limit(limit)
        )
        return [self._to_event(record) for record in result]

    async def mark_as_published(self, event_id: str) -> None:
        """Mark a delivered event without committing the surrounding transaction."""
        await self._session.execute(
            update(OutboxRecord)
            .where(OutboxRecord.event_id == event_id)
            .values(status="published", published_at=datetime.now(UTC), last_error=None)
        )

    async def mark_failed(self, event_id: str, error: str) -> None:
        """Increase attempt count and apply capped exponential backoff."""
        record = await self._session.scalar(
            select(OutboxRecord).where(OutboxRecord.event_id == event_id)
        )
        if record is None:
            raise LookupError(f"No outbox event: {event_id}")
        record.attempts += 1
        record.next_attempt_at = datetime.now(UTC) + timedelta(
            seconds=min(300, 2 ** min(record.attempts, 8))
        )
        record.last_error = error[:4000]

    @staticmethod
    def _to_event(record: OutboxRecord) -> IntegrationEvent:
        occurred_at = (
            record.occurred_at.replace(tzinfo=UTC)
            if record.occurred_at.tzinfo is None
            else record.occurred_at
        )
        return IntegrationEvent(
            event_id=record.event_id,
            event_type=record.event_type,
            schema_version=record.schema_version,
            aggregate_type=record.aggregate_type,
            aggregate_id=record.aggregate_id,
            aggregate_version=record.aggregate_version,
            occurred_at=occurred_at,
            correlation_id=record.correlation_id,
            causation_id=record.causation_id,
            tenant_id=record.tenant_id,
            payload=record.payload,
        )
