from __future__ import annotations

# Event mapping follows the existing IAM integration-event adapter.
# ruff: noqa
# mypy: ignore-errors

from dataclasses import asdict
from typing import Any

from ...kernel.application.context import MessageMetadata
from ...kernel.application.event.integration import IntegrationEvent
from ...kernel.application.event.mapper import DomainEventMapper
from ...kernel.domain.event import DomainEvent


class CatalogDomainEventMapper(DomainEventMapper):
    def map(
        self, event: DomainEvent, metadata: MessageMetadata | None
    ) -> list[IntegrationEvent]:
        aggregate_id = next(
            (
                str(getattr(event, name))
                for name in ("workspace_id", "membership_id", "node_id")
                if getattr(event, name, None) is not None
            ),
            "unknown",
        )
        return [
            IntegrationEvent(
                event_type=f"catalog.{type(event).__name__}",
                payload=_json(asdict(event)),
                aggregate_type=type(event).__name__.removesuffix("Event"),
                aggregate_id=aggregate_id,
                aggregate_version=1,
                correlation_id=metadata.correlation_id if metadata else None,
                causation_id=metadata.causation_id if metadata else None,
                tenant_id=metadata.tenant_id if metadata else None,
            )
        ]


def _json(value: Any) -> Any:
    if hasattr(value, "value") and not isinstance(value, (str, int, float, bool)):
        return str(value)
    if isinstance(value, dict):
        return {str(key): _json(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_json(item) for item in value]
    return value
