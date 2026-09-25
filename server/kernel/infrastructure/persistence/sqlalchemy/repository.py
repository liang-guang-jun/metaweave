"""Base class for write-side SQLAlchemy aggregate repositories."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Hashable
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from ....application.ports import AggregateRepository
from ....domain import Aggregate, EntityId
from .unit_of_work import SqlAlchemyUnitOfWork


class SqlAlchemyAggregateRepository[TAggregate: Aggregate[Any], TId: Hashable](
    AggregateRepository[TAggregate, TId], ABC
):
    """Attach write-model aggregates to the current SQLAlchemy unit of work.

    Concrete repositories supply the mapping between a domain aggregate and
    their SQLAlchemy model, keeping SQLAlchemy annotations out of the domain.
    """

    def __init__(self, uow: SqlAlchemyUnitOfWork) -> None:
        """Bind this repository to a command's active unit of work."""
        self._uow = uow

    async def get(self, id: EntityId[TId]) -> TAggregate | None:
        """Load and track an aggregate when it exists."""
        aggregate = await self._load(self._uow.session, id)
        if aggregate is not None:
            self._uow.track(aggregate)
        return aggregate

    async def add(self, aggregate: TAggregate) -> None:
        """Persist and track a newly created aggregate."""
        await self._insert(self._uow.session, aggregate)
        self._uow.track(aggregate)

    async def remove(self, aggregate: TAggregate) -> None:
        """Delete an aggregate through its infrastructure-specific mapping."""
        await self._delete(self._uow.session, aggregate)

    @abstractmethod
    async def _load(
        self, session: AsyncSession, id: EntityId[TId]
    ) -> TAggregate | None:
        """Reconstitute one aggregate from persistence without emitting events."""
        raise NotImplementedError

    @abstractmethod
    async def _insert(self, session: AsyncSession, aggregate: TAggregate) -> None:
        """Write a new aggregate using persistence models owned by this adapter."""
        raise NotImplementedError

    @abstractmethod
    async def _delete(self, session: AsyncSession, aggregate: TAggregate) -> None:
        """Delete an aggregate through persistence models owned by this adapter."""
        raise NotImplementedError
