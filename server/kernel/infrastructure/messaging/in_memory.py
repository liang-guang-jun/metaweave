"""In-process publisher for the single-node SQLite deployment."""

from __future__ import annotations

from collections.abc import Iterable

from ...application.event.handler import EventHandler
from ...application.event.integration import IntegrationEvent
from ...application.event.publisher import EventPublisher


class InMemoryIntegrationEventPublisher(EventPublisher):
    """Fan out events sequentially, allowing dispatcher retries on failure."""

    def __init__(self, handlers: Iterable[EventHandler[IntegrationEvent]] = ()) -> None:
        """Store ordered event consumers supplied by the composition root."""
        self._handlers = list(handlers)

    async def publish(self, event: IntegrationEvent) -> None:
        """Deliver to each registered consumer in registration order."""
        for handler in self._handlers:
            await handler.handle(event)

    async def publish_all(self, events: list[IntegrationEvent]) -> None:
        """Publish events in their durable outbox order."""
        for event in events:
            await self.publish(event)
