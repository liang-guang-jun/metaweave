"""Pipeline: composes behaviors around a handler into a callable chain."""

from __future__ import annotations

from ..unit_of_work import UnitOfWork
from .behavior import Behavior
from .handler import Handler
from .message import Message


class Pipeline[TMessage: Message, TResult]:
    """Composes behaviors around a handler into a callable chain.

    Behaviors are invoked from index 0 (outermost) to the last
    (innermost). The handler is the tail of the chain.
    """

    def __init__(
        self,
        handler: Handler[TMessage, TResult],
        behaviors: list[Behavior[TMessage, TResult]],
    ) -> None:
        """Store the handler and the ordered behavior list."""
        self._handler = handler
        self._behaviors = behaviors

    async def execute(
        self, message: TMessage, uow: UnitOfWork | None = None
    ) -> TResult:
        """Run the pipeline for the given message."""
        return await self._invoke(0, message, uow)

    async def _invoke(
        self, index: int, message: TMessage, uow: UnitOfWork | None
    ) -> TResult:
        """Invoke the behavior at index, or the handler at the tail."""
        if index >= len(self._behaviors):
            return await self._handler.handle(message, uow)

        behavior = self._behaviors[index]

        async def next_(msg: TMessage, next_uow: UnitOfWork | None = uow) -> TResult:
            return await self._invoke(index + 1, msg, next_uow)

        return await behavior.handle(message, next_, uow)
