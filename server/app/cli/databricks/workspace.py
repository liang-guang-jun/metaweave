"""Remote workspace folder: source uploads and the deployment manifest."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock
from time import monotonic, sleep
from typing import TYPE_CHECKING

from .manifest import MANIFEST_NAME, Manifest, ManifestCodec
from .progress import NullProgressReporter, ProgressReporter
from .source import SourceFile

if TYPE_CHECKING:  # pragma: no cover
    from databricks.sdk import WorkspaceClient
    from tenacity import RetryCallState, Retrying

    from .progress import ProgressTask

_WORKSPACE_ROOT = "/Workspace"
_LEGACY_WORKSPACE_ROOTS = ("/Shared", "/Users", "/Repos")

#: Number of files transferred at the same time. The SDK client is synchronous,
#: so each transfer gets its own thread; ``--jobs 1`` keeps them sequential.
DEFAULT_JOBS = 8
#: How often one throttled transfer is attempted before the run fails.
DEFAULT_ATTEMPTS = 5
_RETRY_INITIAL_SECONDS = 1.0
_RETRY_MAX_SECONDS = 30.0
_PAUSE_POLL_SECONDS = 0.5


class WorkspaceError(RuntimeError):
    """Raised when the app source folder cannot be read or written."""


class WorkspaceUploadError(WorkspaceError):
    """Raised when one source file cannot be uploaded."""

    def __init__(self, target: str, error: Exception) -> None:
        """Record the failed target and the SDK error behind it."""
        self.target = target
        self.error = error
        super().__init__(f"unable to upload into '{target}': {error}")


class WorkspaceDeleteError(WorkspaceError):
    """Raised when one remote file cannot be deleted."""

    def __init__(self, target: str, error: Exception) -> None:
        """Record the failed target and the SDK error behind it."""
        self.target = target
        self.error = error
        super().__init__(f"unable to delete '{target}': {error}")


def normalize_workspace_path(path: str) -> str:
    """Return the canonical ``/Workspace`` form of a workspace path.

    The workspace file API accepts the legacy aliases ``/Shared``, ``/Users``
    and ``/Repos``, but the Apps deployment API rejects them with
    "Source code path must be a valid workspace path".
    """
    normalized = "/" + path.strip("/")
    if normalized == _WORKSPACE_ROOT or normalized.startswith(f"{_WORKSPACE_ROOT}/"):
        return normalized
    for legacy in _LEGACY_WORKSPACE_ROOTS:
        if normalized == legacy or normalized.startswith(f"{legacy}/"):
            return f"{_WORKSPACE_ROOT}{normalized}"
    return normalized


def is_rate_limited(error: BaseException) -> bool:
    """Report whether a failed transfer was the workspace throttling us."""
    if not isinstance(error, WorkspaceUploadError | WorkspaceDeleteError):
        return False
    return _is_throttled_response(error.error)


def _is_throttled_response(error: BaseException) -> bool:
    """Report whether the SDK error is a throttle the retry policy waits out."""
    return isinstance(error, _throttled_error_types())


class WorkspaceThrottle:
    """Shared pause that keeps parallel workers inside the workspace's limits.

    A throttle response means the workspace is already at its request limit, so
    letting the other workers keep firing only deepens the problem: all of them
    wait out the pause before their next call.
    """

    def __init__(self) -> None:
        """Start with no pause scheduled."""
        self._lock = Lock()
        self._resume_at = 0.0

    def wait(self) -> None:
        """Block until the next call is allowed to go out."""
        while True:
            with self._lock:
                remaining = self._resume_at - monotonic()
            if remaining <= 0:
                return
            sleep(min(remaining, _PAUSE_POLL_SECONDS))

    def pause(self, seconds: float) -> None:
        """Delay every worker by at least ``seconds``."""
        with self._lock:
            self._resume_at = max(self._resume_at, monotonic() + seconds)


def build_retryer(attempts: int, throttle: WorkspaceThrottle) -> Retrying:
    """Return the retry policy of one repository.

    The workspace file API answers a burst of parallel transfers with HTTP 429
    and the SDK does not retry them, so they are retried here with exponential
    jitter. Every attempt waits out the shared throttle, and ``Retry-After`` is
    honoured when the platform sends one.
    """
    from tenacity import (
        Retrying,
        retry_if_exception_type,
        stop_after_attempt,
        wait_exponential_jitter,
    )

    def back_off(state: RetryCallState) -> None:
        """Pause every worker for as long as this attempt has to wait."""
        error = state.outcome.exception() if state.outcome else None
        advised = getattr(error, "retry_after_secs", None)
        throttle.pause(max(float(advised or 0), state.upcoming_sleep))

    return Retrying(
        stop=stop_after_attempt(attempts),
        wait=wait_exponential_jitter(
            initial=_RETRY_INITIAL_SECONDS, max=_RETRY_MAX_SECONDS
        ),
        retry=retry_if_exception_type(_throttled_error_types()),
        before=lambda _state: throttle.wait(),
        before_sleep=back_off,
        reraise=True,
    )


def _throttled_error_types() -> tuple[type[BaseException], ...]:
    """Return the SDK errors the retry policy waits out.

    HTTP 429 arrives as :class:`TooManyRequests`; the other names are the
    platform's request-limit error codes, which mean the same thing here.
    """
    from databricks.sdk.errors import (
        DeadlineExceeded,
        InternalError,
        RequestLimitExceeded,
        ResourceExhausted,
        TemporarilyUnavailable,
        TooManyRequests,
    )

    return (
        TooManyRequests,
        RequestLimitExceeded,
        ResourceExhausted,
        TemporarilyUnavailable,
        InternalError,
        DeadlineExceeded,
    )


class WorkspaceSourceRepository:
    """Read and write the app source folder through the Databricks SDK."""

    def __init__(
        self,
        client: WorkspaceClient,
        root: str,
        progress: ProgressReporter | None = None,
        jobs: int = DEFAULT_JOBS,
        attempts: int = DEFAULT_ATTEMPTS,
    ) -> None:
        """Bind the repository to one app source folder."""
        self.client = client
        self.root = root
        self._progress = progress or NullProgressReporter()
        self._jobs = max(1, jobs)
        self._attempts = max(1, attempts)
        self._created_directories: set[str] = set()
        self._directory_lock = Lock()
        self._throttle = WorkspaceThrottle()
        self._retryer: Retrying | None = None
        self._codec = ManifestCodec()

    def upload_all(self, files: Sequence[SourceFile]) -> int:
        """Upload every file in parallel, reporting progress and creating folders.

        The parent folders are created in one serial pass first, so the workers
        never race on the workspace tree; a failure in any worker stops the
        remaining uploads and propagates its own error.
        """
        for source in files:
            self._ensure_directory(self._parent_of(source.relative_path))
        with self._progress.uploading(len(files)) as task:
            self._in_parallel(files, self.upload, task)
        return len(files)

    def upload(self, source: SourceFile) -> None:
        """Upload one file, creating its parent folder when it is new."""
        from databricks.sdk.errors.base import DatabricksError
        from databricks.sdk.service.workspace import ImportFormat

        target = self._target(source.relative_path)
        self._ensure_directory(self._parent_of(source.relative_path))

        def send() -> None:
            """Send the file, re-opened so a retry gets a fresh stream."""
            with source.absolute_path.open("rb") as stream:
                self.client.workspace.upload(
                    target, stream, format=ImportFormat.AUTO, overwrite=True
                )

        try:
            self._retrying(send)
        except DatabricksError as error:
            raise WorkspaceUploadError(target, error) from error

    def delete_all(self, relative_paths: Sequence[str]) -> int:
        """Delete several remote files in parallel, reporting progress."""
        with self._progress.deleting(len(relative_paths)) as task:
            self._in_parallel(relative_paths, self.delete, task)
        return len(relative_paths)

    def delete(self, relative_path: str) -> None:
        """Delete one remote file, tolerating a file that is already gone."""
        from databricks.sdk.errors import ResourceDoesNotExist
        from databricks.sdk.errors.base import DatabricksError

        target = self._target(relative_path)
        try:
            self._retrying(lambda: self.client.workspace.delete(target))
        except ResourceDoesNotExist:
            # A previous run or a manual cleanup already removed it; the end
            # state is the one this deployment asked for.
            return
        except DatabricksError as error:
            raise WorkspaceDeleteError(target, error) from error

    def load_manifest(self) -> Manifest:
        """Return the manifest of the last deployment, empty when there is none.

        Only a missing manifest is treated as "nothing deployed yet", so a first
        deployment uploads every local file and deletes nothing. Any other
        failure (transport, corrupt JSON, unsupported version) is reported
        instead of being mistaken for an empty remote folder.
        """
        from databricks.sdk.errors import ResourceDoesNotExist

        path = f"{self.root}/{MANIFEST_NAME}"
        try:
            with self.client.workspace.download(path) as stream:
                content = stream.read()
        except ResourceDoesNotExist:
            return Manifest.empty()
        return self._codec.loads(content, source=path)

    def save_manifest(self, manifest: Manifest) -> None:
        """Store the manifest of a fully applied deployment."""
        from databricks.sdk.service.workspace import ImportFormat

        self._ensure_directory(self.root)
        self.client.workspace.upload(
            f"{self.root}/{MANIFEST_NAME}",
            self._codec.dumps(manifest),
            format=ImportFormat.AUTO,
            overwrite=True,
        )

    def _ensure_directory(self, directory: str) -> None:
        """Create a parent folder once per repository lifetime, thread-safely."""
        with self._directory_lock:
            if directory in self._created_directories:
                return
            self.client.workspace.mkdirs(directory)
            self._created_directories.add(directory)

    def _retrying[T](self, action: Callable[[], T]) -> T:
        """Run one SDK call through the retry policy of this repository."""
        if self._retryer is None:
            self._retryer = build_retryer(self._attempts, self._throttle)
        return self._retryer(action)

    def _target(self, relative_path: str) -> str:
        """Return the workspace path of one source-relative path."""
        return f"{self.root}/{relative_path}"

    def _parent_of(self, relative_path: str) -> str:
        """Return the workspace folder holding one source-relative path."""
        return self._target(relative_path).rsplit("/", 1)[0]

    def _in_parallel[T](
        self,
        items: Sequence[T],
        action: Callable[[T], None],
        task: ProgressTask,
    ) -> None:
        """Run one remote call per item, at most ``jobs`` of them at a time.

        The first failure cancels the queued calls and is re-raised, so a
        partial transfer stops early instead of running through a broken
        workspace folder.
        """
        workers = min(self._jobs, len(items))
        if workers <= 1:
            for item in items:
                action(item)
                task.advance()
            return
        with ThreadPoolExecutor(
            max_workers=workers, thread_name_prefix="dbr-transfer"
        ) as pool:
            futures = [pool.submit(action, item) for item in items]
            for future in as_completed(futures):
                try:
                    future.result()
                except BaseException:
                    for pending in futures:
                        pending.cancel()
                    raise
                task.advance()
