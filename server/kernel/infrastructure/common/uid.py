"""UUID generator adapter."""

from __future__ import annotations

from uuid import UUID, uuid4


class UuidGenerator:
    """Generate UUID identities for application use cases."""

    def new(self) -> UUID:
        """Return a new random UUID."""
        return uuid4()
