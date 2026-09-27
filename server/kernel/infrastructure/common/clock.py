"""System clock adapter."""

from __future__ import annotations

from datetime import UTC, datetime


class SystemClock:
    """Return the current UTC timestamp."""

    def now(self) -> datetime:
        """Return an aware UTC timestamp."""
        return datetime.now(UTC)
