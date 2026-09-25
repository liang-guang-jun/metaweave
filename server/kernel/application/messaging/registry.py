"""Registries for handlers and behaviors."""

from __future__ import annotations

from typing import Any, cast

from .behavior import Behavior
from .handler import Handler
from .message import Message


class HandlerRegistry:
    """Maps message types to their handlers.

    Registration is performed once at startup by the composition root.
    Resolution is called on every message dispatch.
    """

    def __init__(self) -> None:
        """Initialize an empty handler registry."""
        self._handlers: dict[type[Message], Handler[Message, Any]] = {}

    def register[TMessage: Message, TResult](
        self,
        message_type: type[TMessage],
        handler: Handler[TMessage, TResult],
    ) -> None:
        """Register a handler for the given message type."""
        if message_type in self._handlers:
            raise ValueError(f"Handler already registered: {message_type!r}")
        self._handlers[message_type] = cast(Handler[Message, Any], handler)

    def resolve[TResult](self, message: Message) -> Handler[Message, TResult]:
        """Return the handler registered for the message's type."""
        handler = self._handlers.get(type(message))
        if handler is None:
            raise LookupError(f"No handler registered: {type(message)!r}")
        return cast(Handler[Message, TResult], handler)


class BehaviorRegistry:
    """Maps message types to ordered behavior chains.

    Supports a global chain plus optional per-message chains.
    The final chain is the global list followed by the message-specific
    list, so global behaviors are the outermost layers.
    """

    def __init__(self) -> None:
        """Initialize empty global and per-message behavior lists."""
        self._global: list[Behavior[Message, Any]] = []
        self._per_message: dict[type[Message], list[Behavior[Message, Any]]] = {}

    def register_global[TMessage: Message, TResult](
        self,
        behavior: Behavior[TMessage, TResult],
    ) -> None:
        """Append a behavior to the global chain."""
        self._global.append(cast(Behavior[Message, Any], behavior))

    def register_for[TMessage: Message, TResult](
        self,
        message_type: type[TMessage],
        behavior: Behavior[TMessage, TResult],
    ) -> None:
        """Append a behavior to a specific message type's chain."""
        self._per_message.setdefault(message_type, []).append(
            cast(Behavior[Message, Any], behavior),
        )

    def for_message[TResult](
        self, message: Message
    ) -> list[Behavior[Message, TResult]]:
        """Return the composed behavior list for the message."""
        specific = self._per_message.get(type(message), [])
        return [cast(Behavior[Message, TResult], b) for b in (*self._global, *specific)]
