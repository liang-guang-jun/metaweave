"""Databricks deployment subsystem: auth, source scanning, sync and deploys.

Nothing in this package imports Typer: the CLI layer translates the errors below
into exit codes and messages, so the same services can also be driven from a job,
an HTTP endpoint or a test.
"""

from __future__ import annotations

from .apps import AppSourcePathMissingError, DatabricksAppDeployer
from .auth import DatabricksAuthConfig, DatabricksAuthError, DatabricksClientFactory
from .deployment import (
    DEFAULT_JOBS,
    DatabricksDeploymentService,
    DeployRequest,
    SyncRequest,
    UploadRequest,
)
from .manifest import (
    HASH_CHUNK_SIZE,
    MANIFEST_NAME,
    MANIFEST_VERSION,
    Manifest,
    ManifestCodec,
    ManifestError,
    sha256_file,
)
from .models import (
    DeploymentResult,
    DeployResult,
    FileDigest,
    SyncDiff,
    SyncResult,
    UploadResult,
)
from .source import SourceFile, SourceScanner, SourceScanOptions
from .sync import SourceSyncService
from .workspace import (
    WorkspaceDeleteError,
    WorkspaceError,
    WorkspaceSourceRepository,
    WorkspaceUploadError,
    normalize_workspace_path,
)

__all__ = [
    "DEFAULT_JOBS",
    "HASH_CHUNK_SIZE",
    "MANIFEST_NAME",
    "MANIFEST_VERSION",
    "AppSourcePathMissingError",
    "DatabricksAppDeployer",
    "DatabricksAuthConfig",
    "DatabricksAuthError",
    "DatabricksClientFactory",
    "DatabricksDeploymentService",
    "DeployRequest",
    "DeployResult",
    "DeploymentResult",
    "FileDigest",
    "Manifest",
    "ManifestCodec",
    "ManifestError",
    "SourceFile",
    "SourceScanOptions",
    "SourceScanner",
    "SourceSyncService",
    "SyncDiff",
    "SyncRequest",
    "SyncResult",
    "UploadRequest",
    "UploadResult",
    "WorkspaceDeleteError",
    "WorkspaceError",
    "WorkspaceSourceRepository",
    "WorkspaceUploadError",
    "normalize_workspace_path",
    "sha256_file",
]
