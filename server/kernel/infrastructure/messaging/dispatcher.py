"""Single-process polling dispatcher for a SQLite transactional outbox."""

from __future__ import annotations

from collections.abc import Callable

from ...application.event.integration import IntegrationEvent
from ...application.event.publisher import EventPublisher
from ...application.unit_of_work import UnitOfWork


class OutboxDispatcher:
    """Publish ready events outside a transaction and persist delivery outcome."""

    def __init__(
        self,
        uow_factory: Callable[[], UnitOfWork],
        publisher: EventPublisher,
        *,
        batch_size: int = 100,
    ) -> None:
        """Configure the single-node dispatcher and its maximum batch size."""
        if batch_size < 1:
            raise ValueError("batch_size must be positive")
        self._uow_factory = uow_factory
        self._publisher = publisher
        self._batch_size = batch_size

    async def dispatch_once(self) -> int:
        """Dispatch a ready batch and return the number successfully published."""
        async with self._uow_factory() as uow:
            events = await uow.outbox.pending(self._batch_size)
        published = 0
        for event in events:
            try:
                await self._publisher.publish(event)
            except Exception as error:
                await self._mark_failed(event, str(error))
            else:
                await self._mark_published(event)
                published += 1
        return published

    async def _mark_published(self, event: IntegrationEvent) -> None:
        async with self._uow_factory() as uow:
            await uow.outbox.mark_as_published(event.event_id)
            await uow.commit()

    async def _mark_failed(self, event: IntegrationEvent, error: str) -> None:
        async with self._uow_factory() as uow:
            await uow.outbox.mark_failed(event.event_id, error)
            await uow.commit()
