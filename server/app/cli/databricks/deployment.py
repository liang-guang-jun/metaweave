"""Public API of the Databricks deployment subsystem."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from .apps import DatabricksAppDeployer
from .models import (
    DeploymentResult,
    DeployResult,
    FileDigest,
    SyncDiff,
    SyncResult,
    UploadResult,
)
from .progress import NullProgressReporter, ProgressReporter
from .source import SourceScanner, SourceScanOptions
from .sync import SourceSyncService
from .workspace import DEFAULT_JOBS, WorkspaceSourceRepository

if TYPE_CHECKING:  # pragma: no cover
    from databricks.sdk import WorkspaceClient


@dataclass(frozen=True, slots=True)
class UploadRequest:
    """Copy a local directory into the app source folder without comparing."""

    local_root: Path
    remote_root: str
    scan: SourceScanOptions = field(default_factory=SourceScanOptions)
    dry_run: bool = False
    force: bool = False


@dataclass(frozen=True, slots=True)
class SyncRequest:
    """Reconcile the app source folder against the last deployment."""

    local_root: Path
    remote_root: str
    scan: SourceScanOptions = field(default_factory=SourceScanOptions)
    dry_run: bool = False


@dataclass(frozen=True, slots=True)
class DeployRequest:
    """A reconciliation followed by a snapshot deployment."""

    app_name: str
    sync: SyncRequest


class DatabricksDeploymentService:
    """Facade used by the CLI (or any other caller) to move and deploy sources."""

    def __init__(
        self,
        client: WorkspaceClient,
        app_deployer: DatabricksAppDeployer,
        sync_service: SourceSyncService,
        progress: ProgressReporter | None = None,
        jobs: int = DEFAULT_JOBS,
    ) -> None:
        """Compose the facade from an authenticated client and its services."""
        self._client = client
        self._app_deployer = app_deployer
        self._sync_service = sync_service
        self._progress = progress or NullProgressReporter()
        self._jobs = jobs

    def upload(self, request: UploadRequest) -> UploadResult:
        """Transfer the selected files without comparing or deleting anything."""
        return self._sync_service.upload(
            SourceScanner(request.local_root, request.scan),
            self._repository(request.remote_root),
            force=request.force,
            dry_run=request.dry_run,
        )

    def reconcile(self, request: SyncRequest) -> SyncResult:
        """Apply the difference between local sources and the last deployment."""
        return self._sync_service.sync(
            SourceScanner(request.local_root, request.scan),
            self._repository(request.remote_root),
            dry_run=request.dry_run,
        )

    def deploy_app(self, app_name: str, remote_root: str) -> DeploymentResult:
        """Trigger the snapshot deployment of one app."""
        return self._app_deployer.deploy(app_name, remote_root)

    def deploy(self, request: DeployRequest) -> DeployResult:
        """Reconcile the sources, then deploy the app unless this is a dry run."""
        sync_result = self.reconcile(request.sync)
        if request.sync.dry_run:
            return DeployResult(sync=sync_result, deployment=None)
        return DeployResult(
            sync=sync_result,
            deployment=self.deploy_app(request.app_name, request.sync.remote_root),
        )

    def _repository(self, remote_root: str) -> WorkspaceSourceRepository:
        """Return the remote repository for one app source folder."""
        return WorkspaceSourceRepository(
            self._client, remote_root, self._progress, jobs=self._jobs
        )


__all__ = [
    "DEFAULT_JOBS",
    "DatabricksAppDeployer",
    "DatabricksDeploymentService",
    "DeployRequest",
    "DeployResult",
    "DeploymentResult",
    "FileDigest",
    "SourceScanOptions",
    "SourceScanner",
    "SourceSyncService",
    "SyncDiff",
    "SyncRequest",
    "SyncResult",
    "UploadRequest",
    "UploadResult",
    "WorkspaceSourceRepository",
]
