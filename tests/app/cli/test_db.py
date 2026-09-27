from __future__ import annotations

import asyncio
from collections.abc import Callable
from pathlib import Path

import pytest
from alembic import command
from sqlalchemy import inspect
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from typer.testing import CliRunner

from server.app.cli import db

runner = CliRunner()


def _record_calls(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    calls: list[str] = []

    def recorder(name: str) -> Callable[..., None]:
        def call(*_: object, **__: object) -> None:
            calls.append(name)

        return call

    for name in (
        "revision",
        "upgrade",
        "downgrade",
        "current",
        "history",
        "heads",
        "branches",
        "show",
        "stamp",
        "check",
        "merge",
    ):
        monkeypatch.setattr(command, name, recorder(name))
    return calls


def test_next_revision_id_uses_four_digit_prefixes(tmp_path: Path) -> None:
    (tmp_path / "0001_first.py").touch()
    (tmp_path / "0012_second.py").touch()
    (tmp_path / "not_a_revision.py").touch()

    assert db.next_revision_id(tmp_path) == "0013"


async def _table_names(engine: AsyncEngine) -> list[str]:
    async with engine.connect() as connection:
        return await connection.run_sync(inspect_tables)


def inspect_tables(connection: Connection) -> list[str]:
    """Read the table names visible through one synchronous facade."""
    return inspect(connection).get_table_names()


def test_apply_migrations_shares_the_caller_engine() -> None:
    # An in-memory database only exists for the process and pool that created
    # it, so Alembic must reuse the caller's engine instead of opening its own.
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")

    db.apply_migrations(engine)
    tables = asyncio.run(_table_names(engine))
    asyncio.run(engine.dispose())

    assert {
        "iam_principals",
        "iam_users",
        "kernel_outbox",
    } <= set(tables)


def test_apply_migrations_is_idempotent() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")

    db.apply_migrations(engine)
    db.apply_migrations(engine)
    asyncio.run(engine.dispose())


def test_db_commands_proxy_to_alembic(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = _record_calls(monkeypatch)
    monkeypatch.setattr(db, "next_revision_id", lambda: "0002")

    arguments = (
        ["revision", "create accounts"],
        ["revision", "manual", "--empty"],
        ["upgrade"],
        ["downgrade", "--", "-1"],
        ["current"],
        ["history"],
        ["heads"],
        ["branches"],
        ["show", "0001_kernel_outbox"],
        ["stamp", "head"],
        ["check"],
        ["merge", "0001", "0002", "-m", "merge heads"],
    )
    for arguments_for_command in arguments:
        result = runner.invoke(db.app, list(arguments_for_command))
        assert result.exit_code == 0, result.output

    assert calls == [
        "revision",
        "revision",
        "upgrade",
        "downgrade",
        "current",
        "history",
        "heads",
        "branches",
        "show",
        "stamp",
        "check",
        "merge",
    ]


def test_db_help_is_exposed_through_main_cli() -> None:
    from server.app.cli.main import app

    result = runner.invoke(app, ["db", "--help"])

    assert result.exit_code == 0
    assert "revision" in result.output
