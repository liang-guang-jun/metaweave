"""Bootstrap configuration and application composition helpers."""

from .config import AppConfig
from .container import Container
from .loader import ConfigError, load_config

__all__ = [
    "AppConfig",
    "ConfigError",
    "Container",
    "create_container",
    "create_factory",
    "load_config",
]


def create_container(config: AppConfig | None = None) -> Container:
    """Lazily build a container without creating a bootstrap/logging import cycle."""
    from .factory import create_container as build_container

    return build_container(config)


def create_factory(config: AppConfig | None = None) -> Container:
    """Lazily build the application composition root."""
    from .factory import create_factory as build_factory

    return build_factory(config)
