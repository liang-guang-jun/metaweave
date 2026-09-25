"""Command-only transaction behavior."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from ..context import current_context_or_none
from ..event.mapper import DomainEventMapper
from ..unit_of_work import UnitOfWork
from .behavior import Behavior
from .message import Command


class TransactionBehavior[TResult](Behavior[Command[TResult], TResult]):
    """Commit a command's write model and integration outbox atomically."""

    def __init__(
        self, uow_factory: Callable[[], UnitOfWork], mapper: DomainEventMapper
    ) -> None:
        """Store the transactional UoW factory and event-contract mapper."""
        self._uow_factory = uow_factory
        self._mapper = mapper

    async def handle(
        self,
        message: Command[TResult],
        next_: Callable[[Command[TResult], UnitOfWork | None], Awaitable[TResult]],
        uow: UnitOfWork | None = None,
    ) -> TResult:
        """Run handler then map all captured facts before the UoW commits."""
        if uow is not None:
            raise RuntimeError(
                "TransactionBehavior must be the outermost transaction owner"
            )
        async with self._uow_factory() as transaction:
            result = await next_(message, transaction)
            context = current_context_or_none()
            metadata = context.metadata if context is not None else None
            for event in transaction.pull_events():
                for integration_event in self._mapper.map(event, metadata):
                    await transaction.outbox.append(integration_event)
            await transaction.commit()
            return result
