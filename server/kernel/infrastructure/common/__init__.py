"""Concrete cross-cutting infrastructure adapters."""

from .clock import SystemClock
from .uid import UuidGenerator

__all__ = ["SystemClock", "UuidGenerator"]
