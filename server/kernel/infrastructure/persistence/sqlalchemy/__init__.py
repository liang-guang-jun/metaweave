"""SQLAlchemy adapters configured for SQLite as the first storage engine."""

from .backend import (
    DatabaseConfigurationError,
    DatabricksLakebaseCredentialProvider,
    create_database_backend,
)
from .database import (
    create_async_engine,
    create_session_factory,
)
from .outbox import SqlAlchemyOutbox
from .repository import SqlAlchemyAggregateRepository
from .unit_of_work import SqlAlchemyUnitOfWork

__all__ = [
    "DatabaseConfigurationError",
    "DatabricksLakebaseCredentialProvider",
    "SqlAlchemyAggregateRepository",
    "SqlAlchemyOutbox",
    "SqlAlchemyUnitOfWork",
    "create_async_engine",
    "create_database_backend",
    "create_session_factory",
]
