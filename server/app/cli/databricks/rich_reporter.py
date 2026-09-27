"""Rich presentation for the dbr commands: progress, diff, summary, errors.

This module is the only place in the subsystem that imports ``rich``. It exists
so the core services can stay ignorant of terminals: in a TTY they show live
progress and status, everywhere else they degrade to plain, log-friendly lines.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import AbstractContextManager, contextmanager
from typing import TYPE_CHECKING

from rich.console import Console
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TaskID,
    TextColumn,
    TimeRemainingColumn,
)

from .manifest import MANIFEST_NAME
from .models import DeploymentResult, SyncResult, UploadResult
from .workspace import WorkspaceDeleteError, WorkspaceError, WorkspaceUploadError

if TYPE_CHECKING:  # pragma: no cover
    from .progress import ProgressTask

_PROGRESS_COLUMNS = (
    SpinnerColumn(),
    TextColumn("[progress.description]{task.description}"),
    BarColumn(),
    MofNCompleteColumn(),
    TimeRemainingColumn(),
)

_UPLOAD_REMEDY = (
    "If the app's service principal cannot write to its default source folder, "
    "pass --source-code-path pointing at a workspace folder it can write, for "
    "example /Workspace/Shared/<app>."
)
_DELETE_REMEDY = (
    "The deployment manifest was not updated, so the next deploy retries this deletion."
)


class _RichTask:
    """Adapter that advances one task of a running Rich progress bar."""

    def __init__(self, progress: Progress, task_id: TaskID) -> None:
        """Bind the adapter to one task identifier."""
        self._progress = progress
        self._task_id = task_id

    def advance(self, count: int = 1) -> None:
        """Advance the underlying Rich task."""
        self._progress.advance(self._task_id, count)


class RichPresenter:
    """Render dbr progress, diffs, summaries and failures through Rich."""

    def __init__(
        self, console: Console | None = None, error_console: Console | None = None
    ) -> None:
        """Bind the presenter to a console, defaulting to stdout and stderr.

        Wrapping is disabled so messages and paths stay on one line, which keeps
        redirected logs (Jenkins) grep-able.
        """
        self.console = console or Console(soft_wrap=True)
        self.error_console = error_console or Console(stderr=True, soft_wrap=True)

    @property
    def is_terminal(self) -> bool:
        """Report whether live, self-refreshing output is appropriate."""
        return self.console.is_terminal

    def hashing(self, total: int) -> AbstractContextManager[ProgressTask]:
        """Track hashing ``total`` local files."""
        return self._stage("Hashing", "Hashed", total)

    def uploading(self, total: int) -> AbstractContextManager[ProgressTask]:
        """Track uploading ``total`` changed files."""
        return self._stage("Uploading", "Uploaded", total)

    def deleting(self, total: int) -> AbstractContextManager[ProgressTask]:
        """Track deleting ``total`` removed files."""
        return self._stage("Deleting", "Deleted", total)

    def deploying(self, description: str) -> AbstractContextManager[None]:
        """Track one indeterminate remote step with a spinner or a log line."""
        return self._status(description)

    def announce(self, remote_root: str) -> None:
        """Print the app source folder a command targets."""
        self.console.print("[cyan]Syncing Databricks App source:[/cyan]")
        self.console.print(f"  Remote: {remote_root}")
        self.console.print()

    def render_upload(self, result: UploadResult, remote_root: str) -> None:
        """Print the outcome of a plain transfer."""
        if result.dry_run:
            for relative in result.files:
                self.console.print(f"  [green]+[/green] {relative}")
            self.console.print()
            self._summary((("Would upload", len(result.files)),))
            self.console.print("Dry run: no files were uploaded.")
            return
        self.console.print(
            f"[green]Uploaded {result.uploaded} files to {remote_root}.[/green]"
        )
        if result.snapshot_refreshed:
            self.console.print(
                f"[green]{self._check()}Remote deployment snapshot refreshed[/green] "
                f"({MANIFEST_NAME})."
            )

    def render_sync(self, result: SyncResult, *, dry_run: bool) -> None:
        """Print the changed paths and the totals of one reconciliation."""
        if not result.diff.has_changes:
            self.console.print("No source changes detected.")
            self._summary((("Unchanged", result.unchanged),))
            return
        self.console.print("Changes:")
        for path in result.diff.added:
            self.console.print(f"  [green]+[/green] {path}")
        for path in result.diff.modified:
            self.console.print(f"  [yellow]M[/yellow] {path}")
        for path in result.diff.deleted:
            self.console.print(f"  [red]-[/red] {path}")
        self.console.print()
        if dry_run:
            self._summary(
                (
                    ("Would upload", result.uploaded),
                    ("Would delete", result.deleted),
                    ("Unchanged", result.unchanged),
                )
            )
        else:
            self._summary(
                (
                    ("Uploaded", result.uploaded),
                    ("Deleted", result.deleted),
                    ("Unchanged", result.unchanged),
                )
            )

    def render_deployment(self, deployment: DeploymentResult) -> None:
        """Print the finished deployment, compute start and app URL."""
        self.console.print(
            f"[green]{self._check()}Deployment {deployment.deployment_id} "
            f"completed with state {deployment.state}[/green]"
        )
        if deployment.started:
            self.console.print(f"[green]{self._check()}App compute started[/green]")
        if deployment.app_url:
            self.console.print(f"App URL: {deployment.app_url}")

    def render_dry_run_deploy(self) -> None:
        """Print the note that a dry run neither synced nor deployed."""
        self.console.print(
            "Dry run: no files changed and deployment was not triggered."
        )

    def render_skipped_deploy(self) -> None:
        """Print the note that an unchanged deployment was skipped."""
        self.console.print(
            "[yellow]Deployment skipped[/yellow]: no source changes; pass "
            "--force-deploy to deploy anyway."
        )

    def render_error(
        self, error: BaseException, *, identity: str | None = None
    ) -> None:
        """Print a failure on stderr together with its usual remedy."""
        message = self._describe(error, identity)
        self.error_console.print(f"[red]Error:[/red] {message}")

    @contextmanager
    def _stage(self, description: str, past: str, total: int) -> Iterator[ProgressTask]:
        """Run one deterministic stage, live in a TTY and as plain lines outside."""
        if total == 0:
            # Nothing to do means no bar at all: avoid empty, flickering stages.
            yield _NullStage()
            return
        if not self.is_terminal:
            self.console.print(f"{description} {self._files(total)}...")
            try:
                yield _NullStage()
            finally:
                self.console.print(f"{past} {self._files(total)}.")
            return
        progress = Progress(*_PROGRESS_COLUMNS, console=self.console, transient=False)
        with progress:
            task_id = progress.add_task(description, total=total)
            yield _RichTask(progress, task_id)

    @contextmanager
    def _status(self, description: str) -> Iterator[None]:
        """Show an indeterminate step, as a spinner in a TTY and a line elsewhere."""
        if not self.is_terminal:
            self.console.print(description)
            yield
            return
        with self.console.status(f"[bold cyan]{description}"):
            yield

    def _summary(self, rows: tuple[tuple[str, int], ...]) -> None:
        """Print aligned label/value rows without boxes or borders."""
        width = max(len(label) for label, _ in rows)
        values = max(len(str(value)) for _, value in rows)
        for label, value in rows:
            self.console.print(f"{label:<{width}}  {value:>{values}}")

    def _describe(self, error: BaseException, identity: str | None) -> str:
        """Return the message and the usual remedy for one failure."""
        if isinstance(error, WorkspaceUploadError):
            remedy = _UPLOAD_REMEDY
        elif isinstance(error, WorkspaceDeleteError):
            remedy = _DELETE_REMEDY
        elif isinstance(error, WorkspaceError):
            remedy = "The deployment manifest was not updated."
        else:
            return str(error)
        hint = f"{error} {remedy}"
        if identity:
            hint = f"{hint} Deployment identity: {identity}."
        return hint

    def _check(self) -> str:
        """Return a check mark and gap on a terminal, nothing in a plain log."""
        return "✓ " if self.is_terminal else ""

    @staticmethod
    def _files(total: int) -> str:
        """Return a correctly pluralized file count."""
        return f"{total} file" if total == 1 else f"{total} files"


class _NullStage:
    """Progress task used by the plain-text stage."""

    def advance(self, count: int = 1) -> None:
        """Discard one progress update."""
