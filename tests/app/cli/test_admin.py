from __future__ import annotations

import pytest
from typer.testing import CliRunner

from server.app.cli import admin
from server.app.cli.main import app

runner = CliRunner()


def test_admin_create_prompts_and_bootstraps_user(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: dict[str, str] = {}

    async def create_system_admin(email: str, password: str) -> str:
        calls.update(email=email, password=password)
        return "e13e9189-5aee-4f14-b15f-2271908dc7c6"

    monkeypatch.setattr(admin, "create_system_admin", create_system_admin)

    result = runner.invoke(
        app,
        ["admin", "create"],
        input="admin@example.com\nPassword1!abc\nPassword1!abc\n",
    )

    assert result.exit_code == 0, result.output
    assert calls == {"email": "admin@example.com", "password": "Password1!abc"}
    assert "system.super_admin" in result.output


def test_admin_create_rejects_mismatched_passwords(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    called = False

    async def create_system_admin(_: str, __: str) -> str:
        nonlocal called
        called = True
        return "unused"

    monkeypatch.setattr(admin, "create_system_admin", create_system_admin)

    result = runner.invoke(
        app,
        ["admin", "create"],
        input="admin@example.com\nPassword1!abc\nDifferent1!abc\n",
    )

    assert result.exit_code == 1
    assert not called
    assert "Passwords do not match" in result.output
