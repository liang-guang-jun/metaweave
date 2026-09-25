"""EventHandler abstraction: consumer of domain or integration events."""

from __future__ import annotations

from abc import ABC, abstractmethod

from .integration import IntegrationEvent


class EventHandler[TEvent: IntegrationEvent](ABC):
    """Base class for event handlers.

    Event handlers consume integration events and return nothing. A failure
    propagates to the dispatcher so the outbox can retry delivery.
    """

    @abstractmethod
    async def handle(self, event: TEvent) -> None:
        """Handle the given event."""
        raise NotImplementedError
