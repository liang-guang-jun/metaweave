"""Domain error hierarchy: semantic failures within the domain layer."""

from __future__ import annotations


class DomainError(Exception):
    """Base class for all domain errors.

    Domain errors describe business-level failures. They are raised
    by domain objects and translated into transport-level errors
    (HTTP, gRPC, etc.) by the application or infrastructure layer.
    """


class InvariantViolationError(DomainError):
    """Raised when an aggregate invariant is broken.

    Signals a state that should never be reachable, regardless of
    the operation being performed.
    """


class BusinessRuleViolationError(DomainError):
    """Raised when a business rule forbids the current operation.

    Signals that the operation is not allowed under the current
    state or context.
    """


class NotFoundError(DomainError):
    """Raised when a requested aggregate or entity does not exist."""


class ConflictError(DomainError):
    """Raised on concurrency conflicts or uniqueness violations."""
