"""Local source discovery: gitignore, include, exclude and recursion rules."""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from .manifest import MANIFEST_NAME

if TYPE_CHECKING:  # pragma: no cover
    from pathspec import GitIgnoreSpec

# Directories that never belong to a deployment, even without a .gitignore.
_ALWAYS_IGNORED_DIRECTORIES = frozenset({".git"})


@dataclass(frozen=True, slots=True)
class SourceFile:
    """One file selected for upload."""

    absolute_path: Path
    relative_path: str


@dataclass(frozen=True, slots=True)
class SourceScanOptions:
    """Filters applied while scanning a source directory."""

    include: tuple[str, ...] = ()
    exclude: tuple[str, ...] = ()
    recursive: bool = True
    #: Ignore `.gitignore` rules, for example to upload build output that the
    #: repository ignores. ``exclude``, ``.git`` and the deployment manifest
    #: still apply.
    force: bool = False


def rebase_gitignore_patterns(prefix: str, content: str) -> list[str]:
    """Rebase one .gitignore file's patterns onto the scanned root."""
    rebased: list[str] = []
    for raw in content.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        negation = line.startswith("!")
        pattern = line[1:] if negation else line
        if prefix:
            pattern = pattern[1:] if pattern.startswith("/") else pattern
            pattern = f"{prefix}{pattern}"
        rebased.append(f"{'!' if negation else ''}{pattern}")
    return rebased


def is_manifest_path(relative: str) -> bool:
    """Report whether a source-relative path is a deployment manifest."""
    return relative == MANIFEST_NAME or relative.endswith(f"/{MANIFEST_NAME}")


def build_spec(patterns: Sequence[str]) -> GitIgnoreSpec | None:
    """Return a spec matching the given patterns, or ``None`` when empty."""
    if not patterns:
        return None
    from pathspec import GitIgnoreSpec

    return GitIgnoreSpec.from_lines(patterns)


class SourceScanner:
    """Select the files one deployment must transfer from a local directory.

    ``.git`` and the deployment manifest are always excluded; ``exclude`` wins
    over ``include``, which in turn wins over ``.gitignore`` unless ``force``
    asks to ignore those rules entirely. A ``root`` that is one file selects
    just that file, under its own name: naming a file is an explicit choice, so
    no ``.gitignore`` applies to it, and the scan covers nothing else.
    """

    def __init__(self, root: Path, options: SourceScanOptions | None = None) -> None:
        """Read the ignore rules under ``root`` and prepare the filters."""
        self.root = root
        self.options = options or SourceScanOptions()
        self._single_file = root.is_file()
        self._ignore_spec = None if self._single_file else self._collect_ignore_spec()
        self._include_spec = build_spec(self.options.include)
        self._exclude_spec = build_spec(self.options.exclude)

    def scan(self) -> list[SourceFile]:
        """Return every file to upload as ``absolute``/``relative`` pairs."""
        if self._single_file:
            if self._is_ignored(self.root.name):
                return []
            return [SourceFile(self.root, self.root.name)]
        return [
            SourceFile(absolute_path, relative)
            for absolute_path, relative in self._iter_files()
        ]

    def covers(self, relative_path: str) -> bool:
        """Report whether a deployed path is in the scope of this scan.

        Only a covered path may be deleted, and only covered manifest entries
        are replaced. A directory scan covers the whole deployed tree; a
        single-file scan covers nothing but that one file, so uploading it can
        neither delete nor unmanage the rest of the deployment.
        """
        if self._single_file:
            return relative_path == self.root.name
        return True

    def _collect_ignore_spec(self) -> GitIgnoreSpec:
        """Combine every nested .gitignore into one root-relative ignore spec."""
        from pathspec import GitIgnoreSpec

        patterns: list[str] = []
        pending: list[tuple[Path, str]] = [(self.root, "")]
        while pending:
            directory, relative_directory = pending.pop()
            gitignore = directory / ".gitignore"
            if gitignore.is_file():
                prefix = f"{relative_directory}/" if relative_directory else ""
                patterns.extend(
                    rebase_gitignore_patterns(
                        prefix, gitignore.read_text(encoding="utf-8")
                    )
                )
            spec = GitIgnoreSpec.from_lines(patterns)
            for entry in sorted(directory.iterdir()):
                if not entry.is_dir():
                    continue
                relative = (
                    f"{relative_directory}/{entry.name}"
                    if relative_directory
                    else entry.name
                )
                if entry.name in _ALWAYS_IGNORED_DIRECTORIES or spec.match_file(
                    relative
                ):
                    continue
                pending.append((entry, relative))
        return GitIgnoreSpec.from_lines(patterns)

    def _is_ignored(self, relative: str) -> bool:
        """Report whether a source-relative path must be excluded."""
        if relative.split("/", 1)[0] in _ALWAYS_IGNORED_DIRECTORIES:
            return True
        if is_manifest_path(relative):
            return True
        if self._exclude_spec is not None and self._exclude_spec.match_file(relative):
            return True
        if self.options.force:
            return False
        if self._include_spec is not None and self._include_spec.match_file(relative):
            return False
        return self._ignore_spec is not None and self._ignore_spec.match_file(relative)

    def _iter_files(self) -> Iterator[tuple[Path, str]]:
        """Yield ``(absolute_path, relative_path)`` for the selected files."""
        pending: list[tuple[Path, str]] = [(self.root, "")]
        while pending:
            directory, relative_directory = pending.pop()
            for entry in sorted(directory.iterdir()):
                relative = (
                    f"{relative_directory}/{entry.name}"
                    if relative_directory
                    else entry.name
                )
                if self._is_ignored(relative):
                    continue
                if entry.is_dir():
                    if self.options.recursive:
                        pending.append((entry, relative))
                elif entry.is_file():
                    yield entry, relative
