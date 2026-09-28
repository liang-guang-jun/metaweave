from __future__ import annotations

from pathlib import Path

import pytest

from server.app.bootstrap.loader import ConfigError, deep_merge, load_config


def _write_config(directory: Path, name: str, content: str) -> None:
    (directory / name).write_text(content, encoding="utf-8")


def test_deep_merge_preserves_unoverridden_nested_values() -> None:
    assert deep_merge(
        {"database": {"database": "base", "echo": False}, "values": [1]},
        {"database": {"echo": True}, "values": [2]},
    ) == {"database": {"database": "base", "echo": True}, "values": [2]}


def test_loader_applies_selected_profiles_by_priority(tmp_path: Path) -> None:
    _write_config(
        tmp_path,
        "config.default.yaml",
        """
configuration:
  profiles:
    dev: {priority: 10}
    uat: {priority: 20}
    prod: {priority: 30}
app: {name: metaweave, debug: false}
database: {provider: sqlite, driver: aiosqlite, database: base.db, auth: {type: none}, echo: false}
logging: {level: INFO, json: false}
""",
    )
    _write_config(
        tmp_path,
        "config.dev.yaml",
        "database: {echo: true}\nlogging: {level: DEBUG}\n",
    )
    _write_config(
        tmp_path,
        "config.uat.yaml",
        "database: {database: uat.db}\n",
    )
    _write_config(
        tmp_path,
        "config.prod.yaml",
        "logging: {level: WARNING, json: true}\n",
    )

    config = load_config(config_dir=tmp_path)

    assert config.database.database == "uat.db"
    assert config.database.echo is True
    assert config.logging.level == "WARNING"
    assert config.logging.json_output is True


def test_loader_skips_missing_profiles_and_rejects_registry_override(
    tmp_path: Path,
) -> None:
    _write_config(
        tmp_path,
        "config.default.yaml",
        """
configuration: {profiles: {dev: {priority: 10}}}
app: {name: metaweave, debug: false}
database: {provider: sqlite, driver: aiosqlite, database: base.db, auth: {type: none}, echo: false}
logging: {level: INFO, json: false}
""",
    )
    _write_config(
        tmp_path,
        "config.dev.yaml",
        "configuration: {profiles: {prod: {priority: 1}}}\n",
    )
    with pytest.raises(ConfigError, match="default-only"):
        load_config(config_dir=tmp_path)


def test_loader_skips_registered_profile_when_its_file_is_missing(
    tmp_path: Path,
) -> None:
    _write_config(
        tmp_path,
        "config.default.yaml",
        """
configuration: {profiles: {missing: {priority: 10}}}
app: {name: metaweave, debug: false}
database: {provider: sqlite, driver: aiosqlite, database: base.db, auth: {type: none}, echo: false}
logging: {level: INFO, json: false}
""",
    )

    assert load_config(config_dir=tmp_path).app.name == "metaweave"
