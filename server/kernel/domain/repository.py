"""Domain collection contract without persistence concerns."""

from abc import ABC, abstractmethod
from collections.abc import Hashable
from typing import Any

from .aggregate import Aggregate
from .entity import EntityId


class AggregateCollection[TAggregate: Aggregate[Any], TId: Hashable](ABC):
    """Synchronous collection-shaped contract useful to domain services."""

    @abstractmethod
    def get(self, id: EntityId[TId]) -> TAggregate | None:
        """Return an aggregate if it is already available to the domain."""
        raise NotImplementedError
