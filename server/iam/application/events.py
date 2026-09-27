"""IAM domain-event integration mapping."""
# mypy: ignore-errors

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from ...kernel.application.context import MessageMetadata
from ...kernel.application.event.integration import IntegrationEvent
from ...kernel.application.event.mapper import DomainEventMapper
from ...kernel.domain.event import DomainEvent
from ..domain.events import *


class IamDomainEventMapper(DomainEventMapper):
    """Map IAM facts to stable versioned envelopes."""

    def map(
        self, event: DomainEvent, metadata: MessageMetadata | None
    ) -> list[IntegrationEvent]:
        aggregate_id = _aggregate_id(event)
        payload = _json(asdict(event))
        return [
            IntegrationEvent(
                event_type=f"iam.{type(event).__name__}",
                payload=payload,
                aggregate_type=type(event).__name__.removesuffix("Event"),
                aggregate_id=aggregate_id,
                aggregate_version=1,
                correlation_id=metadata.correlation_id if metadata else None,
                causation_id=metadata.causation_id if metadata else None,
                tenant_id=metadata.tenant_id if metadata else None,
            )
        ]


def _aggregate_id(event: DomainEvent) -> str:
    for name in (
        "acl_id",
        "membership_id",
        "group_id",
        "session_id",
        "tenant_id",
        "user_id",
        "provider_id",
        "identity_id",
        "principal_id",
        "api_key_id",
    ):
        value = getattr(event, name, None)
        if value is not None:
            return str(value)
    return "unknown"


def _json(value: Any) -> Any:
    if hasattr(value, "value") and not isinstance(value, (str, int, float, bool)):
        return str(value)
    if isinstance(value, dict):
        return {str(key): _json(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json(item) for item in value]
    return value
