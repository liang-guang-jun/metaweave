"""Outbox abstraction: reliable event publication."""

from __future__ import annotations

from abc import ABC, abstractmethod

from .integration import IntegrationEvent


class Outbox(ABC):
    """Stores events transactionally before publishing them."""

    @abstractmethod
    async def append(self, event: IntegrationEvent) -> None:
        """Append an event to the outbox in the current transaction."""
        raise NotImplementedError

    @abstractmethod
    async def pending(self, limit: int) -> list[IntegrationEvent]:
        """Return unpublished events up to the given limit."""
        raise NotImplementedError

    @abstractmethod
    async def mark_as_published(self, event_id: str) -> None:
        """Mark an event as successfully published."""
        raise NotImplementedError

    @abstractmethod
    async def mark_failed(self, event_id: str, error: str) -> None:
        """Schedule a failed delivery retry and retain its diagnostic error."""
        raise NotImplementedError
