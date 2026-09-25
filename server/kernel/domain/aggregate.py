"""Aggregate abstraction: the root of a consistency boundary."""

from __future__ import annotations

from collections.abc import Hashable

from .entity import Entity
from .event import DomainEvent


class Aggregate[TId: Hashable](Entity[TId]):
    """Base class for aggregate roots.

    An aggregate is a transactional boundary. All external access
    must go through the aggregate root. Domain events are collected
    by the root and published by the application layer after commit.
    """

    def __init__(self) -> None:
        """Initialize the domain event buffer."""
        self._domain_events: list[DomainEvent] = []

    def _record_event(self, event: DomainEvent) -> None:
        """Record a domain event to be published later."""
        self._domain_events.append(event)

    def pull_events(self) -> list[DomainEvent]:
        """Return and clear all recorded domain events."""
        events = self._domain_events
        self._domain_events = []
        return events


class VersionedAggregate[TId: Hashable](Aggregate[TId]):
    """Base class for aggregates with a version number.

    The version is incremented on every state change and used by
    the persistence layer to detect concurrent modifications
    (optimistic locking) or to support event sourcing.
    """

    def __init__(self, *, version: int = 0) -> None:
        """Initialize the aggregate with version zero."""
        super().__init__()
        self._version = version

    @property
    def version(self) -> int:
        """Return the current version of this aggregate."""
        return self._version

    def _record_state_change(self, event: DomainEvent) -> None:
        """Advance version and retain the event after a state mutation."""
        self._version += 1

        self._record_event(event)

    def _restore_version(self, version: int) -> None:
        """Set a persisted version without creating an event."""
        if version < 0:
            raise ValueError("version must be non-negative")
        self._version = version
