"""Deployment manifest: the record of the last successful deployment."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

from .models import FileDigest, SyncDiff
from .progress import NullProgressReporter, ProgressReporter

if TYPE_CHECKING:  # pragma: no cover
    from .source import SourceFile

# Name of the manifest inside the app source folder. It is owned by the
# deployment tooling: never uploaded as user source, never deleted as one.
MANIFEST_NAME = ".deploy-manifest.json"
MANIFEST_VERSION = 1
HASH_CHUNK_SIZE = 1 << 20


class ManifestError(RuntimeError):
    """Raised when a remote manifest is corrupt or from a newer tool."""


def sha256_file(path: Path, *, chunk_size: int = HASH_CHUNK_SIZE) -> str:
    """Hash one file in fixed-size chunks so large files stay out of memory."""
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


@dataclass(frozen=True, slots=True)
class Manifest:
    """Hashes of every file a deployment owns, keyed by source-relative path."""

    files: Mapping[str, FileDigest] = field(default_factory=dict)
    version: int = MANIFEST_VERSION

    @classmethod
    def empty(cls) -> Manifest:
        """Return the manifest of a folder that was never deployed."""
        return cls()

    @classmethod
    def from_files(
        cls,
        files: Iterable[SourceFile],
        *,
        progress: ProgressReporter | None = None,
    ) -> Manifest:
        """Hash the selected source files into a manifest."""
        scanned = list(files)
        entries: dict[str, FileDigest] = {}
        reporter = progress or NullProgressReporter()
        with reporter.hashing(len(scanned)) as task:
            for source in scanned:
                entries[source.relative_path] = FileDigest(
                    sha256_file(source.absolute_path),
                    source.absolute_path.stat().st_size,
                )
                task.advance()
        return cls(files=entries)

    def diff(self, deployed: Manifest) -> SyncDiff:
        """Compare this local manifest with the deployed one, on SHA-256."""
        local_paths, remote_paths = set(self.files), set(deployed.files)
        shared = local_paths & remote_paths

        def is_unchanged(path: str) -> bool:
            return self.files[path].sha256 == deployed.files[path].sha256

        return SyncDiff(
            added=sorted(local_paths - remote_paths),
            modified=sorted(path for path in shared if not is_unchanged(path)),
            deleted=sorted(remote_paths - local_paths),
            unchanged=sorted(path for path in shared if is_unchanged(path)),
        )


class ManifestCodec:
    """Encode and validate the manifest document stored in the workspace."""

    def dumps(self, manifest: Manifest) -> bytes:
        """Encode a manifest as the JSON document uploaded to the workspace."""
        payload = {
            "version": manifest.version,
            "generated_at": datetime.now(UTC).isoformat(),
            "files": {
                path: {"sha256": digest.sha256, "size": digest.size}
                for path, digest in sorted(manifest.files.items())
            },
        }
        return json.dumps(payload, indent=2).encode("utf-8")

    def loads(self, data: bytes, *, source: str) -> Manifest:
        """Decode a manifest document, reporting unusable input clearly."""
        try:
            payload = json.loads(data.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ManifestError(f"{source} is not valid JSON: {error}") from error
        return self._from_payload(payload, source)

    def _from_payload(self, payload: object, source: str) -> Manifest:
        """Validate one decoded manifest document."""
        if not isinstance(payload, dict):
            raise ManifestError(f"{source} does not contain a JSON object")
        version = payload.get("version")
        if version != MANIFEST_VERSION:
            raise ManifestError(
                f"{source} has unsupported manifest version {version!r}; "
                f"expected {MANIFEST_VERSION}"
            )
        files = payload.get("files")
        if not isinstance(files, dict):
            raise ManifestError(f"{source} has no 'files' mapping")
        return Manifest(files=self._digests(files, source), version=version)

    def _digests(
        self, files: dict[object, object], source: str
    ) -> dict[str, FileDigest]:
        """Validate the per-file digest entries of a manifest document."""
        digests: dict[str, FileDigest] = {}
        for relative, entry in files.items():
            if not isinstance(relative, str) or not isinstance(entry, dict):
                raise ManifestError(f"{source} has an invalid file entry {relative!r}")
            sha256 = entry.get("sha256")
            size = entry.get("size")
            if not isinstance(sha256, str) or not isinstance(size, int):
                raise ManifestError(
                    f"{source} entry {relative!r} must provide a 'sha256' and 'size'"
                )
            digests[relative] = FileDigest(sha256, size)
        return digests
