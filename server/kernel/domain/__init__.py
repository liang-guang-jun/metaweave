"""Domain layer kernel abstractions."""

from .aggregate import Aggregate, VersionedAggregate
from .entity import Entity, EntityId
from .error import BusinessRuleViolationError, DomainError, InvariantViolationError
from .event import DomainEvent
from .repository import AggregateCollection
from .specification import Specification
from .value_object import ValueObject

__all__ = [
    "Aggregate",
    "AggregateCollection",
    "BusinessRuleViolationError",
    "DomainError",
    "DomainEvent",
    "Entity",
    "EntityId",
    "InvariantViolationError",
    "Specification",
    "ValueObject",
    "VersionedAggregate",
]
