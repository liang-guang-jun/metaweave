"""Mapping from internal domain facts to published integration contracts."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable, Iterable

from ...domain import DomainEvent
from ..context import MessageMetadata
from .integration import IntegrationEvent


class DomainEventMapper(ABC):
    """Maps a domain event within a command transaction."""

    @abstractmethod
    def map(
        self, event: DomainEvent, metadata: MessageMetadata | None
    ) -> Iterable[IntegrationEvent]:
        """Return contracts to persist atomically with the write model."""
        raise NotImplementedError


class FunctionalDomainEventMapper(DomainEventMapper):
    """Small registry-based mapper suitable for a composition root."""

    def __init__(self) -> None:
        """Initialize an empty concrete-domain-event mapper registry."""
        self._mappers: dict[
            type[DomainEvent],
            Callable[[DomainEvent, MessageMetadata | None], Iterable[IntegrationEvent]],
        ] = {}

    def register[TEvent: DomainEvent](
        self,
        event_type: type[TEvent],
        mapper: Callable[[TEvent, MessageMetadata | None], Iterable[IntegrationEvent]],
    ) -> None:
        """Register exactly one mapper for a concrete domain event type."""
        if event_type in self._mappers:
            raise ValueError(f"Mapper already registered: {event_type!r}")
        self._mappers[event_type] = mapper  # type: ignore[assignment]

    def map(
        self, event: DomainEvent, metadata: MessageMetadata | None
    ) -> Iterable[IntegrationEvent]:
        """Map an event or fail the command rather than silently lose it."""
        try:
            return self._mappers[type(event)](event, metadata)
        except KeyError as error:
            raise LookupError(f"No integration mapper for {type(event)!r}") from error
