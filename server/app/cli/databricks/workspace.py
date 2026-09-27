"""Remote workspace folder: source uploads and the deployment manifest."""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING

from .manifest import MANIFEST_NAME, Manifest, ManifestCodec
from .progress import NullProgressReporter, ProgressReporter
from .source import SourceFile

if TYPE_CHECKING:  # pragma: no cover
    from databricks.sdk import WorkspaceClient

_WORKSPACE_ROOT = "/Workspace"
_LEGACY_WORKSPACE_ROOTS = ("/Shared", "/Users", "/Repos")


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


class WorkspaceSourceRepository:
    """Read and write the app source folder through the Databricks SDK."""

    def __init__(
        self,
        client: WorkspaceClient,
        root: str,
        progress: ProgressReporter | None = None,
    ) -> None:
        """Bind the repository to one app source folder."""
        self.client = client
        self.root = root
        self._progress = progress or NullProgressReporter()
        self._created_directories: set[str] = set()
        self._codec = ManifestCodec()

    def upload_all(self, files: Sequence[SourceFile]) -> int:
        """Upload every file, reporting progress and creating parent folders."""
        with self._progress.uploading(len(files)) as task:
            for source in files:
                self.upload(source)
                task.advance()
        return len(files)

    def upload(self, source: SourceFile) -> None:
        """Upload one file, creating its parent folder when it is new."""
        from databricks.sdk.errors.base import DatabricksError
        from databricks.sdk.service.workspace import ImportFormat

        target = f"{self.root}/{source.relative_path}"
        self._ensure_directory(target.rsplit("/", 1)[0])
        try:
            with source.absolute_path.open("rb") as stream:
                self.client.workspace.upload(
                    target, stream, format=ImportFormat.AUTO, overwrite=True
                )
        except DatabricksError as error:
            raise WorkspaceUploadError(target, error) from error

    def delete_all(self, relative_paths: Sequence[str]) -> int:
        """Delete several remote files, reporting progress."""
        with self._progress.deleting(len(relative_paths)) as task:
            for relative in relative_paths:
                self.delete(relative)
                task.advance()
        return len(relative_paths)

    def delete(self, relative_path: str) -> None:
        """Delete one remote file, tolerating a file that is already gone."""
        from databricks.sdk.errors import ResourceDoesNotExist
        from databricks.sdk.errors.base import DatabricksError

        target = f"{self.root}/{relative_path}"
        try:
            self.client.workspace.delete(target)
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
        """Create a parent folder once per repository lifetime."""
        if directory in self._created_directories:
            return
        self.client.workspace.mkdirs(directory)
        self._created_directories.add(directory)
