"""Application layer kernel abstractions."""

from .common.clock import Clock
from .common.page import Page, PageRequest
from .common.uid import UID
from .context import ExecutionContext
from .event.handler import EventHandler
from .event.integration import IntegrationEvent
from .event.mapper import DomainEventMapper, FunctionalDomainEventMapper
from .event.outbox import Outbox
from .event.publisher import EventPublisher
from .messaging.behavior import Behavior
from .messaging.bus import MessageBus
from .messaging.handler import CommandHandler, Handler, QueryHandler
from .messaging.message import Command, Message, Query
from .messaging.pipeline import Pipeline
from .messaging.transaction import TransactionBehavior
from .ports import AggregateRepository, ReadStore
from .unit_of_work import UnitOfWork

__all__ = [
    "UID",
    "AggregateRepository",
    "Behavior",
    "Clock",
    "Command",
    "CommandHandler",
    "DomainEventMapper",
    "EventHandler",
    "EventPublisher",
    "ExecutionContext",
    "FunctionalDomainEventMapper",
    "Handler",
    "IntegrationEvent",
    "Message",
    "MessageBus",
    "Outbox",
    "Page",
    "PageRequest",
    "Pipeline",
    "Query",
    "QueryHandler",
    "ReadStore",
    "TransactionBehavior",
    "UnitOfWork",
]
