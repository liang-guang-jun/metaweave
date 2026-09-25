"""SQLAlchemy adapters configured for SQLite as the first storage engine."""

from .database import (
    create_async_engine,
    create_kernel_schema,
    create_session_factory,
)
from .outbox import SqlAlchemyOutbox
from .repository import SqlAlchemyAggregateRepository
from .unit_of_work import SqlAlchemyUnitOfWork

__all__ = [
    "SqlAlchemyAggregateRepository",
    "SqlAlchemyOutbox",
    "SqlAlchemyUnitOfWork",
    "create_async_engine",
    "create_kernel_schema",
    "create_session_factory",
]
