"""Value objects shared across the Databricks deployment subsystem."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class FileDigest:
    """Content identity of one deployable file."""

    sha256: str
    size: int


@dataclass(frozen=True, slots=True)
class SyncDiff:
    """Difference between local sources and the last deployed remote state."""

    added: list[str]
    modified: list[str]
    deleted: list[str]
    unchanged: list[str]

    @property
    def has_changes(self) -> bool:
        """Report whether any file must be uploaded or deleted."""
        return bool(self.added or self.modified or self.deleted)


@dataclass(frozen=True, slots=True)
class SyncResult:
    """Outcome of reconciling local sources with the deployed manifest."""

    added: int
    modified: int
    deleted: int
    unchanged: int
    diff: SyncDiff

    @classmethod
    def from_diff(cls, diff: SyncDiff) -> SyncResult:
        """Summarize one diff."""
        return cls(
            added=len(diff.added),
            modified=len(diff.modified),
            deleted=len(diff.deleted),
            unchanged=len(diff.unchanged),
            diff=diff,
        )

    @property
    def uploaded(self) -> int:
        """Number of files an apply writes to the workspace."""
        return self.added + self.modified


@dataclass(frozen=True, slots=True)
class UploadResult:
    """Outcome of a plain directory transfer that compares nothing."""

    files: tuple[str, ...]
    uploaded: int
    dry_run: bool
    snapshot_refreshed: bool = False


@dataclass(frozen=True, slots=True)
class DeploymentResult:
    """Outcome of one Databricks Apps deployment."""

    deployment_id: str
    state: str | None
    app_url: str | None
    started: bool


@dataclass(frozen=True, slots=True)
class DeployResult:
    """Outcome of a deploy run: the reconciliation plus its deployment."""

    sync: SyncResult
    deployment: DeploymentResult | None
