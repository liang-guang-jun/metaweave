from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime

import pytest

from server.app.bootstrap.config import LoggingConfig
from server.kernel.application.context import (
    ExecutionContext,
    MessageMetadata,
    execution_context,
)
from server.kernel.application.messaging.message import Query
from server.kernel.application.unit_of_work import UnitOfWork
from server.kernel.infrastructure.logging import (
    LoggingBehavior,
    bind_context,
    configure_logging,
    get_logger,
)


@dataclass(frozen=True, slots=True)
class FindAccount(Query[str]):
    account_id: str


def test_console_logger_renders_second_precision_segments_and_attributes(
    capsys: pytest.CaptureFixture[str],
) -> None:
    configure_logging(LoggingConfig(colors=False))

    with bind_context(correlation_id="correlation-1"):
        get_logger("server.test").info("account.found", account_id="account-1")

    output = capsys.readouterr().out
    assert output.startswith("[")
    assert "][INFO][server.test] account.found" in output
    assert "account_id='account-1'" in output
    assert "correlation_id='correlation-1'" in output


def test_configure_logging_silences_named_standard_logger() -> None:
    configure_logging(LoggingConfig(silenced_loggers=("uvicorn",)))

    handler = logging.getLogger().handlers[0]
    record = logging.LogRecord(
        "uvicorn.error", logging.INFO, __file__, 0, "hidden", (), None
    )
    assert not handler.filter(record)


@pytest.mark.asyncio
async def test_logging_behavior_records_success_with_execution_context(
    capsys: pytest.CaptureFixture[str],
) -> None:
    configure_logging(LoggingConfig(colors=False))
    behavior: LoggingBehavior[FindAccount, str] = LoggingBehavior("server.message")
    metadata = MessageMetadata(
        message_id="message-1",
        correlation_id="correlation-1",
        causation_id="cause-1",
        user_id="user-1",
        tenant_id="tenant-1",
        occurred_at=datetime.now(UTC),
    )

    async def next_(message: FindAccount, uow: UnitOfWork | None) -> str:
        assert uow is None
        return message.account_id

    with execution_context(ExecutionContext(metadata)):
        assert await behavior.handle(FindAccount("account-1"), next_) == "account-1"

    output = capsys.readouterr().out
    assert "message.started" in output
    assert "message.finished" in output
    assert "success=True" in output
    assert "message_id='message-1'" in output
    assert "duration_ms=" in output


@pytest.mark.asyncio
async def test_logging_behavior_records_failure_and_reraises(
    capsys: pytest.CaptureFixture[str],
) -> None:
    configure_logging(LoggingConfig(colors=False))
    behavior: LoggingBehavior[FindAccount, str] = LoggingBehavior("server.message")

    async def fail(_: FindAccount, __: UnitOfWork | None) -> str:
        raise ValueError("not found")

    with pytest.raises(ValueError, match="not found"):
        await behavior.handle(FindAccount("missing"), fail)

    output = capsys.readouterr().out
    assert "message.finished" in output
    assert "success=False" in output
    assert "ValueError: not found" in output
