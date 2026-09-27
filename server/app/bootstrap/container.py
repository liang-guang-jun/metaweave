"""Dependency-injector container owned by the application composition root."""

from __future__ import annotations

from dependency_injector import containers, providers
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from ...kernel.application.event.publisher import EventPublisher
from ...kernel.application.messaging.bus import MessageBus
from ...kernel.application.messaging.registry import BehaviorRegistry, HandlerRegistry
from ...kernel.infrastructure.messaging.dispatcher import OutboxDispatcher
from .config import AppConfig


class Container(containers.DeclarativeContainer):
    """Application dependencies shared by HTTP, CLI, and background adapters."""

    config = providers.Object(AppConfig())
    engine = providers.Singleton(AsyncEngine)
    session_factory = providers.Singleton(async_sessionmaker[AsyncSession])
    handlers = providers.Singleton(HandlerRegistry)
    behaviors = providers.Singleton(BehaviorRegistry)
    message_bus = providers.Singleton(
        MessageBus,
        handlers=handlers,
        behaviors=behaviors,
    )
    publisher = providers.Singleton(EventPublisher)
    dispatcher = providers.Singleton(OutboxDispatcher)
