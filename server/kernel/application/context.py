"""Execution context: per-request metadata for cross-cutting concerns."""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from contextvars import ContextVar, Token
from dataclasses import dataclass, replace
from datetime import datetime
from typing import Any


@dataclass(frozen=True, slots=True)
class MessageMetadata:
    """Metadata attached to every message execution."""

    message_id: str
    correlation_id: str | None
    causation_id: str | None
    user_id: str | None
    tenant_id: str | None
    occurred_at: datetime


@dataclass(frozen=True, slots=True)
class ExecutionContext:
    """Per-request context available to behaviors and handlers."""

    metadata: MessageMetadata

    def with_metadata(self, **changes: Any) -> ExecutionContext:
        """Return a new context with updated metadata fields."""
        return ExecutionContext(metadata=replace(self.metadata, **changes))


_current: ContextVar[ExecutionContext | None] = ContextVar(
    "execution_context",
    default=None,
)


def current_context() -> ExecutionContext:
    """Return the execution context for the current task.

    Raises:
        LookupError: If no context is active.
    """
    ctx = _current.get()
    if ctx is None:
        raise LookupError("No active execution context")
    return ctx


def current_context_or_none() -> ExecutionContext | None:
    """Return the current context, or None if none is active."""
    return _current.get()


@contextmanager
def execution_context(ctx: ExecutionContext) -> Generator[ExecutionContext]:
    """Install the given context for the current task scope."""
    token: Token[ExecutionContext | None] = _current.set(ctx)
    try:
        yield ctx
    finally:
        _current.reset(token)
