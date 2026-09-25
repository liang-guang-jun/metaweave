# application/page.py
"""Pagination value objects for queries."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PageRequest:
    """Pagination request parameters."""

    page: int = 1
    size: int = 20

    def __post_init__(self) -> None:
        """Validate page and size bounds."""
        if self.page < 1:
            raise ValueError("page must be >= 1")
        if self.size < 1:
            raise ValueError("size must be >= 1")

    @property
    def offset(self) -> int:
        """Return the zero-based offset for the current page."""
        return (self.page - 1) * self.size

    @property
    def limit(self) -> int:
        """Return the maximum number of items per page."""
        return self.size


@dataclass(frozen=True, slots=True)
class Page[TDto]:
    """A page of results with pagination metadata."""

    items: Sequence[TDto]
    total: int
    page: int
    size: int

    @property
    def pages(self) -> int:
        """Return the total number of pages."""
        return (self.total + self.size - 1) // self.size

    @property
    def has_next(self) -> bool:
        """Return True if there is a page after the current one."""
        return self.page < self.pages
