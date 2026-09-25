from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Self, cast

import pytest

from server.kernel.application.context import (
    ExecutionContext,
    MessageMetadata,
    execution_context,
)
from server.kernel.application.event.integration import IntegrationEvent
from server.kernel.application.event.mapper import FunctionalDomainEventMapper
from server.kernel.application.event.outbox import Outbox
from server.kernel.application.messaging.behavior import Behavior
from server.kernel.application.messaging.bus import MessageBus
from server.kernel.application.messaging.handler import CommandHandler
from server.kernel.application.messaging.message import Command
from server.kernel.application.messaging.registry import (
    BehaviorRegistry,
    HandlerRegistry,
)
from server.kernel.application.messaging.transaction import TransactionBehavior
from server.kernel.application.unit_of_work import UnitOfWork
from server.kernel.domain import Aggregate, DomainEvent, EntityId, VersionedAggregate


@dataclass(frozen=True, slots=True)
class AccountId(EntityId[str]):
    value: str


@dataclass(frozen=True, slots=True)
class AccountOpened(DomainEvent):
    account_id: str


class Account(VersionedAggregate[str]):
    def __init__(self, account_id: AccountId) -> None:
        super().__init__()
        self._id = account_id

    @property
    def id(self) -> AccountId:
        return self._id

    def open(self) -> None:
        self._record_state_change(AccountOpened(self.id.value))


@dataclass(frozen=True, slots=True)
class OpenAccount(Command[str]):
    account_id: str


class MemoryOutbox(Outbox):
    def __init__(self) -> None:
        self.events: list[IntegrationEvent] = []

    async def append(self, event: IntegrationEvent) -> None:
        self.events.append(event)

    async def pending(self, limit: int) -> list[IntegrationEvent]:
        return self.events[:limit]

    async def mark_as_published(self, event_id: str) -> None:
        return None

    async def mark_failed(self, event_id: str, error: str) -> None:
        return None


class MemoryUow(UnitOfWork):
    def __init__(self) -> None:
        self._outbox = MemoryOutbox()
        self.aggregates: list[Account] = []
        self.committed = False

    @property
    def outbox(self) -> MemoryOutbox:
        return self._outbox

    async def __aenter__(self) -> Self:
        """Enter the test unit of work."""
        return self

    async def __aexit__(self, *args: object) -> None:
        """Exit the test unit of work."""
        return None

    def track(self, aggregate: Aggregate[Any]) -> None:
        self.aggregates.append(cast(Account, aggregate))

    def pull_events(self) -> list[DomainEvent]:
        return [
            event for aggregate in self.aggregates for event in aggregate.pull_events()
        ]

    async def commit(self) -> None:
        self.committed = True

    async def rollback(self) -> None:
        return None


class OpenAccountHandler(CommandHandler[OpenAccount, str]):
    def __init__(self) -> None:
        self.aggregate: Account | None = None

    async def handle(self, message: OpenAccount, uow: UnitOfWork | None = None) -> str:
        assert uow is not None
        self.aggregate = Account(AccountId(message.account_id))
        self.aggregate.open()
        uow.track(self.aggregate)
        return message.account_id


def test_aggregate_versions_events_and_identity() -> None:
    account = Account(AccountId("one"))
    same = Account(AccountId("one"))
    account.open()

    assert account == same
    assert account.version == 1
    assert account.pull_events() == [AccountOpened("one")]
    assert account.pull_events() == []


@pytest.mark.asyncio
async def test_command_pipeline_commits_mapped_integration_event() -> None:
    uow = MemoryUow()
    mapper = FunctionalDomainEventMapper()
    mapper.register(
        AccountOpened,
        lambda event, metadata: [
            IntegrationEvent(
                event_type="accounts.opened",
                aggregate_type="Account",
                aggregate_id=event.account_id,
                aggregate_version=1,
                payload={"account_id": event.account_id},
                correlation_id=metadata.correlation_id if metadata else None,
            )
        ],
    )
    handlers = HandlerRegistry()
    handler = OpenAccountHandler()
    handlers.register(OpenAccount, handler)
    behaviors = BehaviorRegistry()
    behaviors.register_for(
        OpenAccount,
        cast(Behavior[OpenAccount, str], TransactionBehavior(lambda: uow, mapper)),
    )
    bus = MessageBus(handlers, behaviors)
    metadata = MessageMetadata(
        message_id="message-1",
        correlation_id="correlation-1",
        causation_id=None,
        user_id=None,
        tenant_id=None,
        occurred_at=datetime.now(UTC),
    )

    with execution_context(ExecutionContext(metadata)):
        assert await bus.send(OpenAccount("one")) == "one"

    assert uow.committed
    assert uow.outbox.events[0].correlation_id == "correlation-1"
    assert uow.outbox.events[0].payload == {"account_id": "one"}
