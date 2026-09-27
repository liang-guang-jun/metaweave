"""Presentation tests: Rich progress in a terminal, plain output everywhere else."""

from __future__ import annotations

import ast
import io
from pathlib import Path

from rich.console import Console

from server.app.cli.databricks import rich_reporter
from server.app.cli.databricks.manifest import Manifest
from server.app.cli.databricks.models import (
    DeploymentResult,
    FileDigest,
    SyncResult,
    UploadResult,
)
from server.app.cli.databricks.rich_reporter import RichPresenter
from server.app.cli.databricks.workspace import WorkspaceUploadError

# Modules that must stay free of presentation concerns.
_CORE_MODULES = (
    "apps",
    "auth",
    "deployment",
    "manifest",
    "models",
    "progress",
    "source",
    "sync",
    "workspace",
)


def _console(*, terminal: bool) -> tuple[Console, io.StringIO]:
    """Return a console writing to a buffer, optionally pretending to be a TTY."""
    buffer = io.StringIO()
    console = Console(file=buffer, force_terminal=terminal, width=100, soft_wrap=True)
    return console, buffer


def _manifest(**files: str) -> Manifest:
    """Build a manifest whose digests follow the given file contents."""
    return Manifest(
        files={
            path: FileDigest(f"hash-{content}", len(content))
            for path, content in files.items()
        }
    )


def _sync_result(local: Manifest, deployed: Manifest) -> SyncResult:
    """Summarize the difference between two manifests."""
    return SyncResult.from_diff(local.diff(deployed))


def test_progress_stages_render_live_bars_on_a_terminal() -> None:
    console, buffer = _console(terminal=True)
    presenter = RichPresenter(console)

    with presenter.hashing(3) as task:
        task.advance()
        task.advance()
        task.advance()
    with presenter.uploading(2) as task:
        task.advance(2)

    rendered = buffer.getvalue()
    assert "Hashing" in rendered
    assert "3/3" in rendered
    assert "Uploading" in rendered
    assert "2/2" in rendered


def test_progress_stages_degrade_to_plain_lines_without_a_terminal() -> None:
    console, buffer = _console(terminal=False)
    presenter = RichPresenter(console)

    with presenter.deleting(2) as task:
        task.advance(2)

    rendered = buffer.getvalue()
    assert "Deleting 2 files..." in rendered
    assert "Deleted 2 files." in rendered
    assert "\x1b[" not in rendered
    assert "\r" not in rendered


def test_deploying_uses_status_without_faking_a_percentage() -> None:
    console, buffer = _console(terminal=True)
    presenter = RichPresenter(console)

    with presenter.deploying("Deploying Databricks App..."):
        pass

    rendered = buffer.getvalue()
    assert "Deploying Databricks App..." in rendered
    assert "100%" not in rendered


def test_deploying_logs_a_plain_line_without_a_terminal() -> None:
    console, buffer = _console(terminal=False)
    presenter = RichPresenter(console)

    with presenter.deploying("Deploying Databricks App..."):
        pass

    assert buffer.getvalue().strip() == "Deploying Databricks App..."


def test_empty_stages_render_nothing() -> None:
    for terminal in (True, False):
        console, buffer = _console(terminal=terminal)
        presenter = RichPresenter(console)

        with presenter.uploading(0) as task:
            task.advance()

        assert buffer.getvalue() == ""


def test_diff_rendering_marks_added_modified_and_deleted() -> None:
    console, buffer = _console(terminal=False)
    presenter = RichPresenter(console)
    result = _sync_result(
        _manifest(**{"app.py": "v2", "new.py": "n"}),
        _manifest(**{"app.py": "v1", "old.py": "o"}),
    )

    presenter.render_sync(result, dry_run=False)

    rendered = buffer.getvalue()
    assert "+ new.py" in rendered
    assert "M app.py" in rendered
    assert "- old.py" in rendered


def test_summary_rows_are_rendered_with_counts() -> None:
    console, buffer = _console(terminal=False)
    presenter = RichPresenter(console)

    presenter.render_sync(
        _sync_result(_manifest(**{"added.py": "a"}), _manifest(**{"deleted.py": "d"})),
        dry_run=True,
    )
    presenter.render_upload(
        UploadResult(files=("a.py", "b.py"), uploaded=0, dry_run=True), "/remote"
    )

    rendered = " ".join(buffer.getvalue().split())
    assert "Would upload 1" in rendered
    assert "Would delete 1" in rendered
    assert "Would upload 2" in rendered
    assert "Dry run: no files were uploaded." in rendered


def test_no_change_summary_stays_concise() -> None:
    console, buffer = _console(terminal=False)
    presenter = RichPresenter(console)

    presenter.render_sync(
        _sync_result(_manifest(**{"app.py": "a"}), _manifest(**{"app.py": "a"})),
        dry_run=False,
    )

    rendered = " ".join(buffer.getvalue().split())
    assert rendered.startswith("No source changes detected.")
    assert "Unchanged 1" in rendered
    assert "Changes:" not in rendered


def test_deployment_result_renders_state_start_and_url() -> None:
    console, buffer = _console(terminal=True)
    presenter = RichPresenter(console)

    presenter.render_deployment(
        DeploymentResult(
            deployment_id="abc123",
            state="SUCCEEDED",
            app_url="https://example.com",
            started=True,
        )
    )

    rendered = buffer.getvalue()
    assert "Deployment abc123 completed with state SUCCEEDED" in rendered
    assert "App compute started" in rendered
    assert "https://example.com" in rendered


def test_started_compute_is_not_reported_when_the_app_was_running() -> None:
    console, buffer = _console(terminal=False)
    presenter = RichPresenter(console)

    presenter.render_deployment(
        DeploymentResult(
            deployment_id="abc123", state="SUCCEEDED", app_url=None, started=False
        )
    )

    assert "compute" not in buffer.getvalue()


def test_errors_are_reported_on_stderr_with_a_remedy() -> None:
    console, buffer = _console(terminal=False)
    error_console, error_buffer = _console(terminal=False)
    presenter = RichPresenter(console, error_console)

    presenter.render_error(
        WorkspaceUploadError("/remote/app.py", RuntimeError("denied")),
        identity="service-principal-id",
    )

    rendered = error_buffer.getvalue()
    assert "Error:" in rendered
    assert "--source-code-path" in rendered
    assert "service-principal-id" in rendered
    assert buffer.getvalue() == ""


def test_plain_error_output_keeps_the_message_on_one_line() -> None:
    console, _ = _console(terminal=False)
    error_console, error_buffer = _console(terminal=False)
    presenter = RichPresenter(console, error_console)
    message = "x" * 200

    presenter.render_error(RuntimeError(message))

    assert message in error_buffer.getvalue()


def test_core_modules_do_not_import_presentation_libraries() -> None:
    package = Path(rich_reporter.__file__).parent
    for name in _CORE_MODULES:
        tree = ast.parse((package / f"{name}.py").read_text(encoding="utf-8"))
        imported = {
            alias.name.split(".")[0]
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for alias in node.names
        }
        imported |= {
            (node.module or "").split(".")[0]
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom)
        }
        assert not {"rich", "typer"} & imported, f"{name}.py imports presentation code"
