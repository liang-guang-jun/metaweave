# application/clock.py
"""Clock abstraction for testable time access."""

from __future__ import annotations

from datetime import UTC, datetime


# todo: 移动到infrastructure/common
class Clock:
    """Provides the current time."""

    @classmethod
    def now(cls) -> datetime:
        """Return UTC now datetime."""
        return datetime.now(UTC)
