"""Stage-level progress contract shared by the deployment services.

The services report progress but never render it: whatever observes them lives in
the CLI presentation layer, so this module and everything it names stay free of
``rich`` and ``typer``.
"""

from __future__ import annotations

from contextlib import AbstractContextManager, nullcontext
from typing import Protocol


class ProgressTask(Protocol):
    """One in-flight progress stage."""

    def advance(self, count: int = 1) -> None:
        """Report that ``count`` more items of this stage are done."""


class ProgressReporter(Protocol):
    """Sink for the progress of hashing, uploading, deleting and deploying.

    Each stage is a context manager so an implementation can render a live
    display only while the stage runs and fall back to plain log lines when no
    terminal is attached.
    """

    def hashing(self, total: int) -> AbstractContextManager[ProgressTask]:
        """Track hashing ``total`` local files."""

    def uploading(self, total: int) -> AbstractContextManager[ProgressTask]:
        """Track uploading ``total`` files."""

    def deleting(self, total: int) -> AbstractContextManager[ProgressTask]:
        """Track deleting ``total`` remote files."""

    def deploying(self, description: str) -> AbstractContextManager[None]:
        """Track one indeterminate remote step, such as a deployment."""


class _NullTask:
    """Progress task that discards every update."""

    def advance(self, count: int = 1) -> None:
        """Discard one progress update."""


class NullProgressReporter:
    """Reporter used when nothing observes progress, for example in tests."""

    def hashing(self, total: int) -> AbstractContextManager[ProgressTask]:
        """Return a no-op hashing stage."""
        return nullcontext(_NullTask())

    def uploading(self, total: int) -> AbstractContextManager[ProgressTask]:
        """Return a no-op uploading stage."""
        return nullcontext(_NullTask())

    def deleting(self, total: int) -> AbstractContextManager[ProgressTask]:
        """Return a no-op deleting stage."""
        return nullcontext(_NullTask())

    def deploying(self, description: str) -> AbstractContextManager[None]:
        """Return a no-op deployment stage."""
        return nullcontext(None)
