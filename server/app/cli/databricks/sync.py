"""Reconcile local sources with the deployment recorded in the workspace."""

from __future__ import annotations

from dataclasses import replace

from .manifest import Manifest
from .models import SyncDiff, SyncResult, UploadResult
from .progress import ProgressReporter
from .source import SourceFile, SourceScanner
from .workspace import WorkspaceSourceRepository


def _scoped(diff: SyncDiff, scanner: SourceScanner) -> SyncDiff:
    """Drop the deletions a scan is not in a position to decide."""
    deleted = [path for path in diff.deleted if scanner.covers(path)]
    if deleted == diff.deleted:
        return diff
    return replace(diff, deleted=deleted)


def _scoped_manifest(
    local: Manifest, deployed: Manifest, scanner: SourceScanner
) -> Manifest:
    """Keep the deployed entries this scan does not cover."""
    kept = {
        path: digest
        for path, digest in deployed.files.items()
        if not scanner.covers(path)
    }
    return Manifest(files={**kept, **local.files})


class SourceSyncService:
    """Upload what changed since the last deployment and delete what it dropped.

    The manifest of the last successful deployment is the only authority: files
    it never recorded are never touched, so unrelated content in the app source
    folder survives. A run without changes writes nothing at all.
    """

    def __init__(self, progress: ProgressReporter | None = None) -> None:
        """Store the reporter that observes the hashing stage."""
        self._progress = progress

    def upload(
        self,
        scanner: SourceScanner,
        repository: WorkspaceSourceRepository,
        *,
        force: bool = False,
        dry_run: bool = False,
    ) -> UploadResult:
        """Copy the scanned files into the workspace folder without comparing.

        ``force`` also refreshes the remote deployment snapshot with the files
        this run wrote, so a later deploy recognises them instead of uploading
        them again. Entries of the previous snapshot are kept, because a plain
        transfer never deletes the remote files they describe.
        """
        files = scanner.scan()
        selected = tuple(source.relative_path for source in files)
        if dry_run:
            return UploadResult(files=selected, uploaded=0, dry_run=True)
        snapshot = self._refreshed_snapshot(repository, files) if force else None
        uploaded = repository.upload_all(files)
        if snapshot is None:
            return UploadResult(files=selected, uploaded=uploaded, dry_run=False)
        repository.save_manifest(snapshot)
        return UploadResult(
            files=selected,
            uploaded=uploaded,
            dry_run=False,
            snapshot_refreshed=True,
        )

    def _refreshed_snapshot(
        self, repository: WorkspaceSourceRepository, files: list[SourceFile]
    ) -> Manifest:
        """Merge the uploaded files into the snapshot of the last deployment."""
        uploaded = Manifest.from_files(files, progress=self._progress)
        return Manifest(files={**repository.load_manifest().files, **uploaded.files})

    def sync(
        self,
        scanner: SourceScanner,
        repository: WorkspaceSourceRepository,
        *,
        dry_run: bool = False,
    ) -> SyncResult:
        """Apply the difference between the scanned sources and the manifest."""
        files = scanner.scan()
        local = Manifest.from_files(files, progress=self._progress)
        deployed = repository.load_manifest()
        diff = _scoped(local.diff(deployed), scanner)
        result = SyncResult.from_diff(diff)
        if dry_run or not diff.has_changes:
            return result

        selected = {source.relative_path: source for source in files}
        repository.upload_all(
            [selected[path] for path in (*diff.added, *diff.modified)]
        )
        repository.delete_all(diff.deleted)
        repository.save_manifest(_scoped_manifest(local, deployed, scanner))
        return result
