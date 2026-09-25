from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncEngine

from server.kernel.application import IntegrationEvent
from server.kernel.application.event.handler import EventHandler
from server.kernel.domain import DomainEvent
from server.kernel.infrastructure.messaging import (
    InMemoryIntegrationEventPublisher,
    OutboxDispatcher,
)
from server.kernel.infrastructure.persistence.sqlalchemy import (
    SqlAlchemyUnitOfWork,
    create_async_engine,
    create_kernel_schema,
    create_session_factory,
)
from server.kernel.infrastructure.persistence.sqlalchemy.models import OutboxRecord
from server.kernel.infrastructure.projection import claim_projection_event


@dataclass(frozen=True, slots=True)
class Registered(DomainEvent):
    account_id: str


async def _new_uow_factory() -> tuple[AsyncEngine, Callable[[], SqlAlchemyUnitOfWork]]:
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:", sqlite_busy_timeout_ms=5000
    )
    await create_kernel_schema(engine)
    return engine, lambda: SqlAlchemyUnitOfWork(create_session_factory(engine))


def _event(domain_event: Registered) -> IntegrationEvent:
    return IntegrationEvent(
        event_type="accounts.registered",
        aggregate_type="Account",
        aggregate_id=domain_event.account_id,
        aggregate_version=1,
        payload={"account_id": domain_event.account_id},
    )


@pytest.mark.asyncio
async def test_outbox_commits_event_and_rolls_back_failure() -> None:
    engine, new_uow = await _new_uow_factory()
    try:
        async with new_uow() as uow:
            await uow.outbox.append(_event(Registered("one")))
            await uow.commit()

        with pytest.raises(RuntimeError):
            async with new_uow() as uow:
                await uow.outbox.append(_event(Registered("two")))
                raise RuntimeError("force rollback")

        async with create_session_factory(engine)() as session:
            count = await session.scalar(select(func.count()).select_from(OutboxRecord))
        assert count == 1
    finally:
        await engine.dispose()


class _FailsOnce(EventHandler[IntegrationEvent]):
    def __init__(self) -> None:
        self.calls = 0

    async def handle(self, event: IntegrationEvent) -> None:
        self.calls += 1
        if self.calls == 1:
            raise RuntimeError("temporary failure")


@pytest.mark.asyncio
async def test_dispatcher_retries_then_marks_event_published() -> None:
    engine, new_uow = await _new_uow_factory()
    try:
        async with new_uow() as uow:
            await uow.outbox.append(_event(Registered("one")))
            await uow.commit()

        handler = _FailsOnce()
        dispatcher = OutboxDispatcher(
            new_uow, InMemoryIntegrationEventPublisher([handler])
        )
        assert await dispatcher.dispatch_once() == 0

        async with create_session_factory(engine)() as session:
            failed = await session.scalar(select(OutboxRecord))
            assert failed is not None
            assert failed.attempts == 1
            assert failed.status == "pending"
            failed.next_attempt_at = failed.next_attempt_at.replace(year=2000)
            await session.commit()

        assert await dispatcher.dispatch_once() == 1
        async with create_session_factory(engine)() as session:
            record = await session.scalar(select(OutboxRecord))
            assert record is not None
            assert record.status == "published"
            assert record.published_at is not None
        assert handler.calls == 2
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_projection_checkpoint_deduplicates_replayed_event() -> None:
    engine, _ = await _new_uow_factory()
    try:
        factory = create_session_factory(engine)
        async with factory() as session:
            async with session.begin():
                assert await claim_projection_event(session, "account-list", "event-1")

        async with factory() as session:
            async with session.begin():
                assert not await claim_projection_event(
                    session, "account-list", "event-1"
                )
    finally:
        await engine.dispose()
