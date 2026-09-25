"""Application-owned ports for persistence and independently shaped reads."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Hashable
from typing import Any

from ..domain import Aggregate, EntityId


class AggregateRepository[TAggregate: Aggregate[Any], TId: Hashable](ABC):
    """Write-side persistence port for one aggregate root type."""

    @abstractmethod
    async def get(self, id: EntityId[TId]) -> TAggregate | None:
        """Load and attach an aggregate to the current unit of work."""
        raise NotImplementedError

    @abstractmethod
    async def add(self, aggregate: TAggregate) -> None:
        """Attach a newly created aggregate to the current unit of work."""
        raise NotImplementedError

    @abstractmethod
    async def remove(self, aggregate: TAggregate) -> None:
        """Mark an aggregate for deletion in the current unit of work."""
        raise NotImplementedError


class ReadStore[TQuery, TResult](ABC):
    """Read-side port returning DTOs rather than aggregates."""

    @abstractmethod
    async def query(self, query: TQuery) -> TResult:
        """Return a projection shaped for the query use case."""
        raise NotImplementedError
