"""UID abstraction for testable ID creation."""

from __future__ import annotations

from uuid import UUID, uuid4


class UID:
    """Generates new entity IDs."""

    @classmethod
    def new(cls) -> UUID:
        """Return a new, unique entity ID."""
        return uuid4()
