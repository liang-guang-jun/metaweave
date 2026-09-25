"""Stable, serializable contracts emitted outside a bounded context."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import uuid4

type JsonValue = (
    bool | int | float | str | list[JsonValue] | dict[str, JsonValue] | None
)


@dataclass(frozen=True, slots=True)
class IntegrationEvent:
    """Versioned integration-event envelope persisted by the outbox."""

    event_type: str
    payload: dict[str, JsonValue]
    aggregate_type: str
    aggregate_id: str
    aggregate_version: int
    schema_version: int = 1
    event_id: str = field(default_factory=lambda: str(uuid4()))
    occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    correlation_id: str | None = None
    causation_id: str | None = None
    tenant_id: str | None = None

    def __post_init__(self) -> None:
        """Reject non-UTC or invalid stable-contract metadata."""
        if not self.event_type or self.schema_version < 1:
            raise ValueError("event_type and positive schema_version are required")
        if self.occurred_at.tzinfo is None:
            raise ValueError("occurred_at must be timezone-aware")
