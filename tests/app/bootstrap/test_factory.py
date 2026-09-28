from __future__ import annotations

from server.app.bootstrap import AppConfig, create_container
from server.kernel.infrastructure.logging import LoggingBehavior


def test_container_exposes_config_and_sqlite_dependencies() -> None:
    config = AppConfig.model_validate(
        {
            "app": {"name": "test"},
            "database": {
                "provider": "sqlite",
                "driver": "aiosqlite",
                "database": ":memory:",
                "auth": {"type": "none"},
            },
            "logging": {"colors": False},
        }
    )

    container = create_container(config)

    assert container.config().app.name == "test"
    assert str(container.engine().url) == "sqlite+aiosqlite:///:memory:"
    assert isinstance(container.behaviors()._global[0], LoggingBehavior)
    container.engine().sync_engine.dispose()
