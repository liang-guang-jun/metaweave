from __future__ import annotations

import importlib
from types import SimpleNamespace
from typing import Any

import pytest
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql, sqlite


class OperationsRecorder:
    def __init__(self, dialect_name: str = "postgresql") -> None:
        self.calls: list[tuple[str, tuple[object, ...], dict[str, object]]] = []
        self.executed: list[object] = []

        def execute(statement: object, *_: object, **__: object) -> None:
            self.executed.append(statement)

        self.bind = SimpleNamespace(
            dialect=SimpleNamespace(name=dialect_name),
            execute=execute,
        )

    def get_bind(self) -> object:
        return self.bind

    def batch_alter_table(self, *_: object, **__: object) -> object:
        raise AssertionError("PostgreSQL migrations must not recreate this table")

    def __getattr__(self, name: str) -> Any:
        """Record arbitrary Alembic operation calls."""

        def record(*args: object, **kwargs: object) -> None:
            self.calls.append((name, args, kwargs))

        return record


def test_0004_uses_native_postgresql_foreign_keys(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    migration = importlib.import_module(
        "server.migrations.versions.0004_iam_tenant_context"
    )
    operations = OperationsRecorder()
    monkeypatch.setattr(migration, "op", operations)

    migration.upgrade()

    assert [
        call[0] for call in operations.calls if call[0] == "create_foreign_key"
    ] == [
        "create_foreign_key",
        "create_foreign_key",
    ]
    assert [
        call[1][1] for call in operations.calls if call[0] == "create_foreign_key"
    ] == [
        "iam_service_principals",
        "iam_users",
    ]
    assert not any(call[0] == "drop_table" for call in operations.calls)


def test_0009_drops_the_service_principal_column_natively_on_postgresql(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    migration = importlib.import_module(
        "server.migrations.versions.0009_principal_lifecycle"
    )
    operations = OperationsRecorder()
    monkeypatch.setattr(migration, "op", operations)

    migration.upgrade()

    assert ("drop_column", ("iam_service_principals", "active"), {}) in operations.calls
    assert not any(
        call[0] in {"drop_constraint", "drop_table"} for call in operations.calls
    )


def test_0007_acl_backfill_uses_cross_dialect_idempotent_sql() -> None:
    migration = importlib.import_module(
        "server.migrations.versions.0007_system_admin_roles"
    )
    statements = [
        value
        for value in migration.upgrade.__code__.co_consts
        if isinstance(value, str) and "INSERT INTO iam_acl_entries" in value
    ]

    assert statements
    for statement in statements:
        compiled_sqlite = str(sa.text(statement).compile(dialect=sqlite.dialect()))
        compiled_postgresql = str(
            sa.text(statement).compile(dialect=postgresql.dialect())
        )
        assert "INSERT OR IGNORE" not in compiled_sqlite
        assert "WHERE NOT EXISTS" in compiled_sqlite
        assert "INSERT INTO iam_acl_entries" in compiled_postgresql
        assert "WHERE NOT EXISTS" in compiled_postgresql

    active_queries = [
        value
        for value in migration.upgrade.__code__.co_consts
        if isinstance(value, str) and "active = TRUE" in value
    ]
    assert len(active_queries) == 2
    assert all("active = 1" not in query for query in active_queries)


class Inspector:
    def __init__(self, *, has_foreign_keys: bool, has_active: bool) -> None:
        self.has_foreign_keys = has_foreign_keys
        self.has_active = has_active

    def has_table(self, _: str) -> bool:
        return True

    def get_foreign_keys(self, _: str) -> list[dict[str, object]]:
        if not self.has_foreign_keys:
            return []
        return [
            {
                "referred_table": "iam_principals",
                "constrained_columns": ["id"],
                "referred_columns": ["id"],
            }
        ]

    def get_columns(self, _: str) -> list[dict[str, str]]:
        return [{"name": "active"}] if self.has_active else []


@pytest.mark.parametrize(
    ("has_foreign_keys", "has_active", "expected_calls"),
    [
        (True, False, []),
        (
            False,
            True,
            ["create_foreign_key", "create_foreign_key", "drop_column"],
        ),
    ],
)
def test_0011_repairs_only_schema_drift(
    monkeypatch: pytest.MonkeyPatch,
    has_foreign_keys: bool,
    has_active: bool,
    expected_calls: list[str],
) -> None:
    migration = importlib.import_module(
        "server.migrations.versions.0011_postgresql_migration_compatibility"
    )
    operations = OperationsRecorder()
    monkeypatch.setattr(migration, "op", operations)
    monkeypatch.setattr(migration.context, "is_offline_mode", lambda: False)
    monkeypatch.setattr(
        migration.sa,
        "inspect",
        lambda _: Inspector(
            has_foreign_keys=has_foreign_keys,
            has_active=has_active,
        ),
    )

    migration.upgrade()

    assert [call[0] for call in operations.calls] == expected_calls
    assert [str(statement) for statement in operations.executed] == [
        "ALTER TABLE alembic_version ALTER COLUMN version_num TYPE VARCHAR(64)"
    ]
