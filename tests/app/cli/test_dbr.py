from __future__ import annotations

import hashlib
import io
import json
import os
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from threading import Lock
from types import SimpleNamespace
from typing import BinaryIO

import pytest
from databricks.sdk.errors import (
    PermissionDenied,
    ResourceDoesNotExist,
    TooManyRequests,
)
from databricks.sdk.service.apps import (
    App,
    AppDeployment,
    AppDeploymentMode,
    AppDeploymentState,
    AppDeploymentStatus,
    ComputeState,
    ComputeStatus,
)
from typer.testing import CliRunner

from server.app.cli.databricks import (
    HASH_CHUNK_SIZE,
    MANIFEST_NAME,
    MANIFEST_VERSION,
    FileDigest,
    Manifest,
    normalize_workspace_path,
    sha256_file,
)
from server.app.cli.databricks import cli as dbr
from server.app.cli.databricks import workspace as dbr_workspace
from server.app.cli.main import app

runner = CliRunner()

_HOST = "https://adb-1234567890.12.azuredatabricks.net"
_REMOTE = "/Workspace/Users/me/metaweave"
_MANIFEST = f"{_REMOTE}/{MANIFEST_NAME}"
#: How long a fake transfer is held so parallel workers can overlap.
_TRANSFER_DELAY = 0.05


def _flat(output: str) -> str:
    """Collapse layout whitespace so summary rows can be asserted plainly."""
    return " ".join(output.split())


class _FakeWorkspace:
    """In-memory workspace folder that tracks uploads, deletions and contents."""

    def __init__(self) -> None:
        self.directories: list[str] = []
        self.uploads: list[str] = []
        self.deleted: list[str] = []
        self.files: dict[str, bytes] = {}

    def mkdirs(self, path: str) -> None:
        self.directories.append(path)

    def upload(self, path: str, content: bytes | BinaryIO, **_: object) -> None:
        self.uploads.append(path)
        self.files[path] = content if isinstance(content, bytes) else content.read()

    def download(self, path: str) -> BinaryIO:
        if path not in self.files:
            raise ResourceDoesNotExist(f"{path} does not exist")
        return io.BytesIO(self.files[path])

    def delete(self, path: str) -> None:
        self.deleted.append(path)
        self.files.pop(path, None)


class _FakeApps:
    def __init__(self, info: App) -> None:
        self.info = info
        self.deployments: list[tuple[str, AppDeployment]] = []
        self.started: list[str] = []

    def get(self, *, name: str) -> App:
        return self.info

    def deploy_and_wait(
        self, *, app_name: str, app_deployment: AppDeployment
    ) -> AppDeployment:
        self.deployments.append((app_name, app_deployment))
        return AppDeployment(
            deployment_id="deployment-1",
            status=AppDeploymentStatus(state=AppDeploymentState.SUCCEEDED),
        )

    def start_and_wait(self, *, name: str) -> App:
        self.started.append(name)
        return self.info


class _FakeCurrentUser:
    def me(self) -> SimpleNamespace:
        return SimpleNamespace(user_name="service-principal-id")


class _FakeClient:
    def __init__(self, info: App) -> None:
        self.workspace = _FakeWorkspace()
        self.apps = _FakeApps(info)
        self.current_user = _FakeCurrentUser()


def _app_info(*, source_code_path: str | None = _REMOTE) -> App:
    return App(
        name="metaweave",
        source_code_path=source_code_path,
        compute_status=ComputeStatus(state=ComputeState.ACTIVE),
        url="https://metaweave.example.com",
    )


def _manifest(client: _FakeClient) -> dict[str, object]:
    """Decode the deployment manifest the last sync wrote."""
    payload = json.loads(client.workspace.files[_MANIFEST].decode("utf-8"))
    assert isinstance(payload, dict)
    return payload


def _manifest_files(client: _FakeClient) -> dict[str, object]:
    """Return the per-path entries of the deployment manifest."""
    files = _manifest(client)["files"]
    assert isinstance(files, dict)
    return files


def _manifest_paths(client: _FakeClient) -> set[str]:
    """Return the source paths the deployment manifest manages."""
    return set(_manifest_files(client))


def _source_uploads(client: _FakeClient) -> list[str]:
    """Return the uploaded source paths, leaving out the deployment snapshot."""
    return [path for path in client.workspace.uploads if path != _MANIFEST]


@pytest.fixture
def fake_client(monkeypatch: pytest.MonkeyPatch) -> _FakeClient:
    client = _FakeClient(_app_info())
    monkeypatch.setattr(dbr, "_workspace_client", lambda **_: client)
    return client


@pytest.fixture(autouse=True)
def isolated_environment(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> Iterator[None]:
    """Hide the developer's real .env and Databricks variables from the tests."""
    saved = dict(os.environ)
    for name in (
        "DATABRICKS_HOST",
        "DATABRICKS_CONFIG_PROFILE",
        "DATABRICKS_CLIENT_ID",
        "DATABRICKS_CLIENT_SECRET",
        "AZURE_CLIENT_ID",
        "AZURE_CLIENT_SECRET",
        "AZURE_TENANT_ID",
    ):
        monkeypatch.delenv(name, raising=False)
    repository = tmp_path / "repository"
    repository.mkdir()
    monkeypatch.setattr(dbr, "repository_root", lambda: repository)
    try:
        yield
    finally:
        os.environ.clear()
        os.environ.update(saved)


def _write_tree(root: Path) -> None:
    (root / ".gitignore").write_text("dist/\n*.db\n", encoding="utf-8")
    (root / "server").mkdir()
    (root / "server" / "app.py").write_text("print('hi')", encoding="utf-8")
    (root / "metaweave.db").write_text("", encoding="utf-8")
    (root / "dist" / "client").mkdir(parents=True)
    (root / "dist" / "client" / "index.html").write_text("<html>", encoding="utf-8")
    (root / ".git").mkdir()
    (root / ".git" / "HEAD").write_text("ref: refs/heads/main", encoding="utf-8")


def _sync_arguments(source: Path, *extra: str) -> list[str]:
    return [
        "sync",
        "--app",
        "metaweave",
        "--host",
        _HOST,
        "--profile",
        "DEFAULT",
        "--source",
        str(source),
        *extra,
    ]


def test_dbr_help_is_exposed_through_main_cli() -> None:
    result = runner.invoke(app, ["dbr", "--help"])

    assert result.exit_code == 0
    assert "sync" in result.output
    assert "deploy" in result.output


def test_sync_uploads_tracked_files_and_respects_gitignore(
    fake_client: _FakeClient, tmp_path: Path
) -> None:
    _write_tree(tmp_path)

    result = runner.invoke(dbr.app, _sync_arguments(tmp_path))

    assert result.exit_code == 0, result.output
    assert sorted(fake_client.workspace.uploads) == [
        f"{_REMOTE}/.gitignore",
        f"{_REMOTE}/server/app.py",
    ]
    # The low-level uploader never records a deployment manifest.
    assert _MANIFEST not in fake_client.workspace.files
    assert f"{_REMOTE}/server" in fake_client.workspace.directories


def test_include_forces_gitignored_paths(
    fake_client: _FakeClient, tmp_path: Path
) -> None:
    _write_tree(tmp_path)

    result = runner.invoke(dbr.app, _sync_arguments(tmp_path, "--include", "dist/"))

    assert result.exit_code == 0, result.output
    assert f"{_REMOTE}/dist/client/index.html" in fake_client.workspace.uploads


def test_sync_honors_nested_gitignore(fake_client: _FakeClient, tmp_path: Path) -> None:
    (tmp_path / ".gitignore").write_text("", encoding="utf-8")
    package = tmp_path / "client"
    package.mkdir()
    (package / ".gitignore").write_text("node_modules\n", encoding="utf-8")
    (package / "node_modules").mkdir()
    (package / "node_modules" / "dep.js").write_text("", encoding="utf-8")
    (package / "index.html").write_text("", encoding="utf-8")

    result = runner.invoke(dbr.app, _sync_arguments(tmp_path))

    assert result.exit_code == 0, result.output
    assert sorted(fake_client.workspace.uploads) == [
        f"{_REMOTE}/.gitignore",
        f"{_REMOTE}/client/.gitignore",
        f"{_REMOTE}/client/index.html",
    ]


def test_source_code_path_override_wins(
    fake_client: _FakeClient, tmp_path: Path
) -> None:
    (tmp_path / "app.py").write_text("", encoding="utf-8")

    result = runner.invoke(
        dbr.app,
        _sync_arguments(tmp_path, "--source-code-path", "/Workspace/override/"),
    )

    assert result.exit_code == 0, result.output
    assert fake_client.workspace.uploads == ["/Workspace/override/app.py"]


def test_normalize_workspace_path_converts_legacy_aliases() -> None:
    assert normalize_workspace_path("/Workspace/Shared/app") == "/Workspace/Shared/app"
    assert normalize_workspace_path("/Shared/app") == "/Workspace/Shared/app"
    assert normalize_workspace_path("/Users/me/app/") == "/Workspace/Users/me/app"
    assert normalize_workspace_path("/Repos/team/app") == "/Workspace/Repos/team/app"


def test_legacy_shared_source_code_path_is_normalized(
    fake_client: _FakeClient, tmp_path: Path
) -> None:
    (tmp_path / "app.py").write_text("", encoding="utf-8")

    result = runner.invoke(
        dbr.app,
        _sync_arguments(
            tmp_path, "--source-code-path", "/Shared/databricks-apps/metaweave"
        ),
    )

    assert result.exit_code == 0, result.output
    assert fake_client.workspace.uploads == [
        "/Workspace/Shared/databricks-apps/metaweave/app.py"
    ]


def test_deploy_normalizes_legacy_source_code_path(
    fake_client: _FakeClient, tmp_path: Path
) -> None:
    (tmp_path / "app.py").write_text("", encoding="utf-8")

    result = runner.invoke(
        dbr.app,
        [
            "deploy",
            "--app",
            "metaweave",
            "--host",
            _HOST,
            "--profile",
            "DEFAULT",
            "--source",
            str(tmp_path),
            "--source-code-path",
            "/Shared/apps/metaweave",
        ],
    )

    assert result.exit_code == 0, result.output
    _, deployment = fake_client.apps.deployments[0]
    assert deployment.source_code_path == "/Workspace/Shared/apps/metaweave"
    assert fake_client.workspace.uploads == [
        "/Workspace/Shared/apps/metaweave/app.py",
        "/Workspace/Shared/apps/metaweave/.deploy-manifest.json",
    ]


def test_sync_falls_back_to_default_source_code_path(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    info = App(
        name="metaweave",
        default_source_code_path="/Workspace/Users/me/default",
        compute_status=ComputeStatus(state=ComputeState.ACTIVE),
    )
    client = _FakeClient(info)
    monkeypatch.setattr(dbr, "_workspace_client", lambda **_: client)
    (tmp_path / "app.py").write_text("", encoding="utf-8")

    result = runner.invoke(dbr.app, _sync_arguments(tmp_path))

    assert result.exit_code == 0, result.output
    assert client.workspace.uploads == ["/Workspace/Users/me/default/app.py"]


def test_deploy_syncs_then_triggers_snapshot_deployment(
    fake_client: _FakeClient, tmp_path: Path
) -> None:
    _write_tree(tmp_path)

    result = runner.invoke(
        dbr.app,
        [
            "deploy",
            "--app",
            "metaweave",
            "--host",
            _HOST,
            "--profile",
            "DEFAULT",
            "--source",
            str(tmp_path),
        ],
    )

    assert result.exit_code == 0, result.output
    assert fake_client.workspace.uploads
    assert len(fake_client.apps.deployments) == 1
    app_name, deployment = fake_client.apps.deployments[0]
    assert app_name == "metaweave"
    assert deployment.mode == AppDeploymentMode.SNAPSHOT
    assert deployment.source_code_path == _REMOTE
    assert fake_client.apps.started == []


def test_upload_failure_names_the_deployment_identity(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    class _RejectingWorkspace(_FakeWorkspace):
        def upload(self, path: str, content: bytes | BinaryIO, **_: object) -> None:
            raise ResourceDoesNotExist(
                "The parent folder (/Workspace/Users/me/app) does not exist."
            )

    client = _FakeClient(_app_info())
    client.workspace = _RejectingWorkspace()
    monkeypatch.setattr(dbr, "_workspace_client", lambda **_: client)
    (tmp_path / "app.py").write_text("", encoding="utf-8")

    result = runner.invoke(dbr.app, _sync_arguments(tmp_path))

    assert result.exit_code == 1
    assert "--source-code-path" in result.output
    assert "service-principal-id" in result.output


def test_deploy_starts_stopped_app_compute(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    info = App(
        name="metaweave",
        source_code_path=_REMOTE,
        compute_status=ComputeStatus(state=ComputeState.STOPPED),
    )
    client = _FakeClient(info)
    monkeypatch.setattr(dbr, "_workspace_client", lambda **_: client)
    (tmp_path / "app.py").write_text("", encoding="utf-8")

    result = runner.invoke(
        dbr.app,
        [
            "deploy",
            "--app",
            "metaweave",
            "--host",
            _HOST,
            "--profile",
            "DEFAULT",
            "--source",
            str(tmp_path),
        ],
    )

    assert result.exit_code == 0, result.output
    assert client.apps.started == ["metaweave"]


def test_sync_requires_source_code_path_when_app_has_none(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    client = _FakeClient(App(name="metaweave"))
    monkeypatch.setattr(dbr, "_workspace_client", lambda **_: client)

    result = runner.invoke(dbr.app, _sync_arguments(tmp_path))

    assert result.exit_code != 0
    assert "source code path" in result.output


def _source_with_app(tmp_path: Path) -> Path:
    source = tmp_path / "src"
    source.mkdir()
    (source / "app.py").write_text("", encoding="utf-8")
    return source


def test_dbr_loads_project_env_before_option_parsing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    (tmp_path / ".env").write_text(
        f"DATABRICKS_HOST={_HOST}\nDATABRICKS_CONFIG_PROFILE=DEFAULT\n",
        encoding="utf-8",
    )
    captured: dict[str, object] = {}
    client = _FakeClient(_app_info())

    def _capture(**kwargs: object) -> _FakeClient:
        captured.update(kwargs)
        return client

    monkeypatch.setattr(dbr, "_workspace_client", _capture)
    monkeypatch.setattr(dbr, "repository_root", lambda: tmp_path)
    source = _source_with_app(tmp_path)

    result = runner.invoke(
        dbr.app, ["sync", "--app", "metaweave", "--source", str(source)]
    )

    assert result.exit_code == 0, result.output
    assert captured == {"host": _HOST, "profile": "DEFAULT"}


def test_project_env_overrides_existing_variables(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("DATABRICKS_HOST", "https://existing.example.com")
    (tmp_path / ".env").write_text(
        "DATABRICKS_HOST=https://from-dotenv.example.com\n", encoding="utf-8"
    )
    captured: dict[str, object] = {}
    client = _FakeClient(_app_info())

    def _capture(**kwargs: object) -> _FakeClient:
        captured.update(kwargs)
        return client

    monkeypatch.setattr(dbr, "_workspace_client", _capture)
    monkeypatch.setattr(dbr, "repository_root", lambda: tmp_path)
    source = _source_with_app(tmp_path)

    result = runner.invoke(
        dbr.app,
        [
            "sync",
            "--app",
            "metaweave",
            "--profile",
            "DEFAULT",
            "--source",
            str(source),
        ],
    )

    assert result.exit_code == 0, result.output
    assert captured["host"] == "https://from-dotenv.example.com"


def test_sync_uses_service_principal_from_project_env(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    (tmp_path / ".env").write_text(
        f"DATABRICKS_HOST={_HOST}\n"
        "DATABRICKS_CLIENT_ID=env-id\n"
        "DATABRICKS_CLIENT_SECRET=env-secret\n",
        encoding="utf-8",
    )
    captured: dict[str, object] = {}
    client = _FakeClient(_app_info())

    def _capture(**kwargs: object) -> _FakeClient:
        captured.update(kwargs)
        return client

    monkeypatch.setattr(dbr, "_workspace_client", _capture)
    monkeypatch.setattr(dbr, "repository_root", lambda: tmp_path)
    source = _source_with_app(tmp_path)

    result = runner.invoke(
        dbr.app, ["sync", "--app", "metaweave", "--source", str(source)]
    )

    assert result.exit_code == 0, result.output
    assert captured == {
        "host": _HOST,
        "client_id": "env-id",
        "client_secret": "env-secret",
        "auth_type": "oauth-m2m",
    }


def test_cli_profile_wins_over_service_principal_in_project_env(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    (tmp_path / ".env").write_text(
        f"DATABRICKS_HOST={_HOST}\n"
        "DATABRICKS_CLIENT_ID=env-id\n"
        "DATABRICKS_CLIENT_SECRET=env-secret\n",
        encoding="utf-8",
    )
    captured: dict[str, object] = {}
    client = _FakeClient(_app_info())

    def _capture(**kwargs: object) -> _FakeClient:
        captured.update(kwargs)
        return client

    monkeypatch.setattr(dbr, "_workspace_client", _capture)
    monkeypatch.setattr(dbr, "repository_root", lambda: tmp_path)
    source = _source_with_app(tmp_path)

    result = runner.invoke(
        dbr.app,
        [
            "sync",
            "--app",
            "metaweave",
            "--profile",
            "DEFAULT",
            "--source",
            str(source),
        ],
    )

    assert result.exit_code == 0, result.output
    assert captured == {"host": _HOST, "profile": "DEFAULT"}


def test_service_principal_credentials_are_passed_to_the_client(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    captured: dict[str, object] = {}
    client = _FakeClient(_app_info())

    def _capture(**kwargs: object) -> _FakeClient:
        captured.update(kwargs)
        return client

    monkeypatch.setattr(dbr, "_workspace_client", _capture)
    (tmp_path / "app.py").write_text("", encoding="utf-8")

    result = runner.invoke(
        dbr.app,
        [
            "sync",
            "--app",
            "metaweave",
            "--host",
            _HOST,
            "--client-id",
            "client-id",
            "--client-secret",
            "client-secret",
            "--source",
            str(tmp_path),
        ],
    )

    assert result.exit_code == 0, result.output
    assert captured == {
        "host": _HOST,
        "client_id": "client-id",
        "client_secret": "client-secret",
        "auth_type": "oauth-m2m",
    }


def test_azure_credentials_are_passed_to_the_client(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    captured: dict[str, object] = {}
    client = _FakeClient(_app_info())

    def _capture(**kwargs: object) -> _FakeClient:
        captured.update(kwargs)
        return client

    monkeypatch.setattr(dbr, "_workspace_client", _capture)
    source = _source_with_app(tmp_path)

    result = runner.invoke(
        dbr.app,
        [
            "sync",
            "--app",
            "metaweave",
            "--host",
            _HOST,
            "--azure-client-id",
            "azure-id",
            "--azure-client-secret",
            "azure-secret",
            "--azure-tenant-id",
            "azure-tenant",
            "--source",
            str(source),
        ],
    )

    assert result.exit_code == 0, result.output
    assert captured == {
        "host": _HOST,
        "azure_client_id": "azure-id",
        "azure_client_secret": "azure-secret",
        "azure_tenant_id": "azure-tenant",
        "auth_type": "azure-client-secret",
    }


def test_azure_credentials_are_read_from_project_env(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    (tmp_path / ".env").write_text(
        f"DATABRICKS_HOST={_HOST}\n"
        "AZURE_CLIENT_ID=env-azure-id\n"
        "AZURE_CLIENT_SECRET=env-azure-secret\n"
        "AZURE_TENANT_ID=env-azure-tenant\n",
        encoding="utf-8",
    )
    captured: dict[str, object] = {}
    client = _FakeClient(_app_info())

    def _capture(**kwargs: object) -> _FakeClient:
        captured.update(kwargs)
        return client

    monkeypatch.setattr(dbr, "_workspace_client", _capture)
    monkeypatch.setattr(dbr, "repository_root", lambda: tmp_path)
    source = _source_with_app(tmp_path)

    result = runner.invoke(
        dbr.app, ["sync", "--app", "metaweave", "--source", str(source)]
    )

    assert result.exit_code == 0, result.output
    assert captured == {
        "host": _HOST,
        "azure_client_id": "env-azure-id",
        "azure_client_secret": "env-azure-secret",
        "azure_tenant_id": "env-azure-tenant",
        "auth_type": "azure-client-secret",
    }


def test_explicit_azure_flags_win_over_project_env_service_principal(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    (tmp_path / ".env").write_text(
        f"DATABRICKS_HOST={_HOST}\n"
        "DATABRICKS_CLIENT_ID=env-id\n"
        "DATABRICKS_CLIENT_SECRET=env-secret\n",
        encoding="utf-8",
    )
    captured: dict[str, object] = {}
    client = _FakeClient(_app_info())

    def _capture(**kwargs: object) -> _FakeClient:
        captured.update(kwargs)
        return client

    monkeypatch.setattr(dbr, "_workspace_client", _capture)
    monkeypatch.setattr(dbr, "repository_root", lambda: tmp_path)
    source = _source_with_app(tmp_path)

    result = runner.invoke(
        dbr.app,
        [
            "sync",
            "--app",
            "metaweave",
            "--azure-client-id",
            "azure-id",
            "--azure-client-secret",
            "azure-secret",
            "--azure-tenant-id",
            "azure-tenant",
            "--source",
            str(source),
        ],
    )

    assert result.exit_code == 0, result.output
    assert captured == {
        "host": _HOST,
        "azure_client_id": "azure-id",
        "azure_client_secret": "azure-secret",
        "azure_tenant_id": "azure-tenant",
        "auth_type": "azure-client-secret",
    }


def test_azure_tenant_id_is_optional(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    captured: dict[str, object] = {}
    client = _FakeClient(_app_info())

    def _capture(**kwargs: object) -> _FakeClient:
        captured.update(kwargs)
        return client

    monkeypatch.setattr(dbr, "_workspace_client", _capture)
    source = _source_with_app(tmp_path)

    result = runner.invoke(
        dbr.app,
        [
            "sync",
            "--app",
            "metaweave",
            "--host",
            _HOST,
            "--azure-client-id",
            "azure-id",
            "--azure-client-secret",
            "azure-secret",
            "--source",
            str(source),
        ],
    )

    assert result.exit_code == 0, result.output
    assert "azure_tenant_id" not in captured
    assert captured["auth_type"] == "azure-client-secret"


def test_azure_requires_client_id_and_secret_together(
    tmp_path: Path,
) -> None:
    result = runner.invoke(
        dbr.app,
        [
            "sync",
            "--app",
            "metaweave",
            "--host",
            _HOST,
            "--azure-client-id",
            "azure-id",
            "--source",
            str(_source_with_app(tmp_path)),
        ],
    )

    assert result.exit_code != 0
    assert "must be provided together" in result.output


def test_profile_credentials_are_passed_to_the_client(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    captured: dict[str, object] = {}
    client = _FakeClient(_app_info())

    def _capture(**kwargs: object) -> _FakeClient:
        captured.update(kwargs)
        return client

    monkeypatch.setattr(dbr, "_workspace_client", _capture)
    (tmp_path / "app.py").write_text("", encoding="utf-8")

    result = runner.invoke(dbr.app, _sync_arguments(tmp_path))

    assert result.exit_code == 0, result.output
    assert captured == {"host": _HOST, "profile": "DEFAULT"}


def test_sync_rejects_profile_combined_with_client_credentials() -> None:
    result = runner.invoke(
        dbr.app,
        [
            "sync",
            "--app",
            "metaweave",
            "--host",
            _HOST,
            "--profile",
            "DEFAULT",
            "--client-id",
            "client-id",
            "--client-secret",
            "client-secret",
        ],
    )

    assert result.exit_code != 0
    assert "only one authentication method" in result.output


def test_conflicting_authorization_methods_reports_a_clean_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    def _reject(**_: object) -> _FakeClient:
        raise ValueError(
            "more than one authorization method configured: azure and oauth"
        )

    monkeypatch.setattr(dbr, "_workspace_client", _reject)
    source = _source_with_app(tmp_path)

    result = runner.invoke(
        dbr.app,
        [
            "sync",
            "--app",
            "metaweave",
            "--host",
            _HOST,
            "--profile",
            "DEFAULT",
            "--source",
            str(source),
        ],
    )

    assert result.exit_code == 2
    assert "more than one authorization method" in result.output
    assert "Traceback" not in result.output


def test_sync_requires_client_id_and_secret_together() -> None:
    result = runner.invoke(
        dbr.app,
        ["sync", "--app", "metaweave", "--host", _HOST, "--client-id", "client-id"],
    )

    assert result.exit_code != 0


# --- manifest based incremental sync ---------------------------------------


class _FailingAfterFirstUpload(_FakeWorkspace):
    """Accept one upload and reject the rest, like a missing write permission."""

    def upload(self, path: str, content: bytes | BinaryIO, **kwargs: object) -> None:
        if self.uploads:
            raise PermissionDenied("no write access")
        super().upload(path, content, **kwargs)


class _RejectingDelete(_FakeWorkspace):
    """Refuse every deletion."""

    def delete(self, path: str) -> None:
        raise PermissionDenied("no delete access")


class _RejectingUpload(_FakeWorkspace):
    """Refuse one target, whatever order the transfers run in."""

    def __init__(self, target: str) -> None:
        super().__init__()
        self.target = target

    def upload(self, path: str, content: bytes | BinaryIO, **kwargs: object) -> None:
        if path == self.target:
            raise PermissionDenied("no write access")
        super().upload(path, content, **kwargs)


class _ConcurrencyProbe(_FakeWorkspace):
    """Fake workspace that records the peak number of transfers in flight.

    Each transfer is held for a moment so overlapping workers are observable
    without depending on scheduling luck.
    """

    def __init__(self) -> None:
        super().__init__()
        self.peak = {"uploads": 0, "deletes": 0}
        self.in_flight = {"uploads": 0, "deletes": 0}
        self._lock = Lock()

    def upload(self, path: str, content: bytes | BinaryIO, **kwargs: object) -> None:
        if isinstance(content, bytes):
            # The deployment manifest is written by the caller, not by the pool.
            super().upload(path, content, **kwargs)
            return
        with self._transfer("uploads"):
            super().upload(path, content, **kwargs)

    def delete(self, path: str) -> None:
        with self._transfer("deletes"):
            super().delete(path)

    @contextmanager
    def _transfer(self, kind: str) -> Iterator[None]:
        """Track one transfer and hold it open so workers can overlap."""
        with self._lock:
            self.in_flight[kind] += 1
            self.peak[kind] = max(self.peak[kind], self.in_flight[kind])
        time.sleep(_TRANSFER_DELAY)
        try:
            yield
        finally:
            with self._lock:
                self.in_flight[kind] -= 1


class _ThrottlingWorkspace(_FakeWorkspace):
    """Answer the first ``free`` transfers of a target with HTTP 429."""

    def __init__(self, free: int = 2, *, target: str | None = None) -> None:
        super().__init__()
        self.free = free
        self.target = target
        self.throttled = 0
        self._lock = Lock()

    def upload(self, path: str, content: bytes | BinaryIO, **kwargs: object) -> None:
        self._throttle(path)
        super().upload(path, content, **kwargs)

    def delete(self, path: str) -> None:
        self._throttle(path)
        super().delete(path)

    def _throttle(self, path: str) -> None:
        """Reject the transfer while this target is still inside its free run."""
        with self._lock:
            if self.target is not None and path != self.target:
                return
            if self.throttled >= self.free:
                return
            self.throttled += 1
        message = "Too many requests. Please wait a moment and try again."
        raise TooManyRequests(message, retry_after_secs=0)


def _write_source(root: Path, files: dict[str, str]) -> Path:
    """Write one source file per mapping entry and return the root directory."""
    for relative, content in files.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    return root


def _deploy_arguments(source: Path, *extra: str) -> list[str]:
    return [
        "deploy",
        "--app",
        "metaweave",
        "--host",
        _HOST,
        "--profile",
        "DEFAULT",
        "--source",
        str(source),
        *extra,
    ]


def test_sha256_file_streams_in_chunks(
    tmp_path: Path,
) -> None:
    payload = b"metaweave" * (HASH_CHUNK_SIZE // 2)
    path = tmp_path / "payload.bin"
    path.write_bytes(payload)

    assert sha256_file(path, chunk_size=1024) == hashlib.sha256(payload).hexdigest()


def test_calculate_sync_diff_classifies_paths_by_sha256() -> None:
    local = {
        "added.py": FileDigest("a", 1),
        "modified.py": FileDigest("new", 2),
        "same.py": FileDigest("same", 3),
    }
    remote = {
        "modified.py": FileDigest("old", 2),
        "same.py": FileDigest("same", 999),
        "deleted.py": FileDigest("d", 4),
    }

    diff = Manifest(files=local).diff(Manifest(files=remote))

    assert diff.added == ["added.py"]
    assert diff.modified == ["modified.py"]
    assert diff.deleted == ["deleted.py"]
    # A different size with an identical hash stays unchanged: the hash wins.
    assert diff.unchanged == ["same.py"]
    assert diff.has_changes is True


def test_first_deploy_uploads_every_file_and_records_the_manifest(
    fake_client: _FakeClient, tmp_path: Path
) -> None:
    source = _write_source(tmp_path, {"app.py": "one", "server/main.py": "two"})

    result = runner.invoke(dbr.app, _deploy_arguments(source))

    assert result.exit_code == 0, result.output
    assert sorted(fake_client.workspace.uploads) == [
        _MANIFEST,
        f"{_REMOTE}/app.py",
        f"{_REMOTE}/server/main.py",
    ]
    assert _manifest(fake_client)["version"] == MANIFEST_VERSION
    assert _manifest_paths(fake_client) == {"app.py", "server/main.py"}
    assert "Uploaded 2" in _flat(result.output)
    assert "Unchanged 0" in _flat(result.output)
    assert "Deploying Databricks App..." in _flat(result.output)
    assert "completed with state" in result.output
    assert fake_client.apps.deployments


def test_first_deploy_never_deletes_unmanaged_remote_files(
    fake_client: _FakeClient, tmp_path: Path
) -> None:
    fake_client.workspace.files[f"{_REMOTE}/notes.txt"] = b"hand written"
    source = _write_source(tmp_path, {"app.py": "one"})

    result = runner.invoke(dbr.app, _deploy_arguments(source))

    assert result.exit_code == 0, result.output
    assert fake_client.workspace.deleted == []
    assert fake_client.workspace.files[f"{_REMOTE}/notes.txt"] == b"hand written"


def test_deploy_without_changes_uploads_nothing_and_skips_the_deployment(
    fake_client: _FakeClient, tmp_path: Path
) -> None:
    source = _write_source(tmp_path, {"app.py": "one"})
    runner.invoke(dbr.app, _deploy_arguments(source))
    fake_client.workspace.uploads.clear()
    deployments = len(fake_client.apps.deployments)

    result = runner.invoke(dbr.app, _deploy_arguments(source))

    assert result.exit_code == 0, result.output
    assert fake_client.workspace.uploads == []
    assert len(fake_client.apps.deployments) == deployments
    assert "No source changes detected." in result.output
    assert "Unchanged 1" in _flat(result.output)
    assert "Deployment skipped" in _flat(result.output)
    assert "--force-deploy" in result.output


def test_force_deploy_deploys_without_changes(
    fake_client: _FakeClient, tmp_path: Path
) -> None:
    source = _write_source(tmp_path, {"app.py": "one"})
    runner.invoke(dbr.app, _deploy_arguments(source))
    deployments = len(fake_client.apps.deployments)

    result = runner.invoke(dbr.app, _deploy_arguments(source, "--force-deploy"))

    assert result.exit_code == 0, result.output
    assert len(fake_client.apps.deployments) == deployments + 1
    assert "completed with state" in result.output
    assert "Deployment skipped" not in _flat(result.output)


def test_include_uploads_build_output_hidden_by_nested_gitignore(
    fake_client: _FakeClient, tmp_path: Path
) -> None:
    # `uv build` writes a `dist/.gitignore` holding `*`, which hides the whole
    # directory; `--include dist` is what lifts it for a deployment.
    source = _write_source(
        tmp_path,
        {
            ".gitignore": "dist/\n",
            "app.py": "one",
            "dist/.gitignore": "*\n",
            "dist/client/index.html": "<html>",
        },
    )

    plain = runner.invoke(dbr.app, _deploy_arguments(source))
    assert plain.exit_code == 0, plain.output
    assert sorted(_source_uploads(fake_client)) == [
        f"{_REMOTE}/.gitignore",
        f"{_REMOTE}/app.py",
    ]
    fake_client.workspace.uploads.clear()

    included = runner.invoke(dbr.app, _deploy_arguments(source, "--include", "dist"))

    assert included.exit_code == 0, included.output
    assert f"{_REMOTE}/dist/client/index.html" in fake_client.workspace.uploads
    assert "  + dist/client/index.html" in included.output


def test_deploy_uploads_only_the_new_file(
    fake_client: _FakeClient, tmp_path: Path
) -> None:
    source = _write_source(tmp_path, {"app.py": "one"})
    runner.invoke(dbr.app, _deploy_arguments(source))
    fake_client.workspace.uploads.clear()
    _write_source(source, {"server/new_service.py": "new"})

    result = runner.invoke(dbr.app, _deploy_arguments(source))

    assert result.exit_code == 0, result.output
    assert fake_client.workspace.uploads == [
        f"{_REMOTE}/server/new_service.py",
        _MANIFEST,
    ]
    assert "  + server/new_service.py" in result.output
    assert "Uploaded 1" in _flat(result.output)
    assert "Unchanged 1" in _flat(result.output)


def test_deploy_detects_a_content_change_of_equal_size(
    fake_client: _FakeClient, tmp_path: Path
) -> None:
    source = _write_source(tmp_path, {"app.py": "abc"})
    runner.invoke(dbr.app, _deploy_arguments(source))
    fake_client.workspace.uploads.clear()
    _write_source(source, {"app.py": "abd"})

    result = runner.invoke(dbr.app, _deploy_arguments(source))

    assert result.exit_code == 0, result.output
    assert fake_client.workspace.uploads == [f"{_REMOTE}/app.py", _MANIFEST]
    assert fake_client.workspace.files[f"{_REMOTE}/app.py"] == b"abd"
    assert "  M app.py" in result.output


def test_deploy_deletes_files_that_disappeared_locally(
    fake_client: _FakeClient, tmp_path: Path
) -> None:
    source = _write_source(tmp_path, {"app.py": "one", "server/old.py": "old"})
    runner.invoke(dbr.app, _deploy_arguments(source))

    (source / "server" / "old.py").unlink()
    result = runner.invoke(dbr.app, _deploy_arguments(source))

    assert result.exit_code == 0, result.output
    assert fake_client.workspace.deleted == [f"{_REMOTE}/server/old.py"]
    assert f"{_REMOTE}/server/old.py" not in fake_client.workspace.files
    assert "  - server/old.py" in result.output
    assert "Deleted 1" in _flat(result.output)
    assert _manifest_paths(fake_client) == {"app.py"}


def test_deploy_deletes_previously_synced_files_that_newly_ignored(
    fake_client: _FakeClient, tmp_path: Path
) -> None:
    source = _write_source(tmp_path, {"app.py": "one", "generated.log": "noise"})
    runner.invoke(dbr.app, _deploy_arguments(source))

    _write_source(source, {".gitignore": "generated.log\n"})
    result = runner.invoke(dbr.app, _deploy_arguments(source))

    assert result.exit_code == 0, result.output
    assert fake_client.workspace.deleted == [f"{_REMOTE}/generated.log"]


def test_deploy_never_deletes_remote_files_outside_the_manifest(
    fake_client: _FakeClient, tmp_path: Path
) -> None:
    source = _write_source(tmp_path, {"app.py": "one"})
    runner.invoke(dbr.app, _deploy_arguments(source))
    fake_client.workspace.files[f"{_REMOTE}/unmanaged.py"] = b"someone else's"

    result = runner.invoke(dbr.app, _deploy_arguments(source))

    assert result.exit_code == 0, result.output
    assert fake_client.workspace.deleted == []
    assert fake_client.workspace.files[f"{_REMOTE}/unmanaged.py"] == b"someone else's"


def test_local_manifest_file_is_never_uploaded_as_source(
    fake_client: _FakeClient, tmp_path: Path
) -> None:
    source = _write_source(
        tmp_path, {"app.py": "one", ".deploy-manifest.json": "not json"}
    )

    result = runner.invoke(dbr.app, _deploy_arguments(source))

    assert result.exit_code == 0, result.output
    assert _manifest_paths(fake_client) == {"app.py"}


def test_include_cannot_force_upload_the_git_directory(
    fake_client: _FakeClient, tmp_path: Path
) -> None:
    source = _write_source(tmp_path, {"app.py": "one", ".git/HEAD": "ref: main"})

    result = runner.invoke(dbr.app, _sync_arguments(source, "--include", ".git/"))

    assert result.exit_code == 0, result.output
    assert f"{_REMOTE}/app.py" in fake_client.workspace.uploads
    assert not any("/.git/" in path for path in fake_client.workspace.uploads)


def test_sync_force_uploads_files_the_gitignore_excludes(
    fake_client: _FakeClient, tmp_path: Path
) -> None:
    # `uv build` drops a `dist/.gitignore` holding `*`, which hides build output
    # from an ordinary scan of that directory.
    source = _write_source(
        tmp_path,
        {
            ".gitignore": "*",
            "client/index.html": "<html>",
            "server-0.1.0.tar.gz": "archive",
        },
    )

    ignored = runner.invoke(dbr.app, _sync_arguments(source, "--dry-run"))
    forced = runner.invoke(dbr.app, _sync_arguments(source, "--force"))

    assert "Would upload 0" in _flat(ignored.output)
    assert sorted(_source_uploads(fake_client)) == [
        f"{_REMOTE}/.gitignore",
        f"{_REMOTE}/client/index.html",
        f"{_REMOTE}/server-0.1.0.tar.gz",
    ]
    assert _MANIFEST in fake_client.workspace.uploads
    assert forced.exit_code == 0, forced.output


def test_sync_force_still_honours_exclude_and_the_manifest_rule(
    fake_client: _FakeClient, tmp_path: Path
) -> None:
    source = _write_source(
        tmp_path,
        {
            ".gitignore": "*",
            "app.py": "one",
            "notes.md": "two",
            ".deploy-manifest.json": "not json",
            ".git/HEAD": "ref: main",
        },
    )

    result = runner.invoke(
        dbr.app,
        _sync_arguments(
            source, "--force", "--exclude", "*.md", "--exclude", ".gitignore"
        ),
    )

    assert result.exit_code == 0, result.output
    assert _source_uploads(fake_client) == [f"{_REMOTE}/app.py"]
    assert _manifest_paths(fake_client) == {"app.py"}


def test_sync_force_refreshes_the_remote_snapshot(
    fake_client: _FakeClient, tmp_path: Path
) -> None:
    fake_client.workspace.files[_MANIFEST] = json.dumps(
        {"version": 1, "files": {"app.py": {"sha256": "old", "size": 3}}}
    ).encode("utf-8")
    source = _write_source(tmp_path, {".gitignore": "*", "bundle.js": "js"})

    result = runner.invoke(dbr.app, _sync_arguments(source, "--force"))

    assert result.exit_code == 0, result.output
    entries = _manifest_files(fake_client)
    assert set(entries) == {".gitignore", "app.py", "bundle.js"}
    assert entries["bundle.js"] == {
        "sha256": hashlib.sha256(b"js").hexdigest(),
        "size": 2,
    }
    # A forced upload keeps the snapshot entries it did not touch, because a
    # plain transfer never deletes the remote files they describe.
    assert entries["app.py"] == {"sha256": "old", "size": 3}
    assert "Remote deployment snapshot refreshed" in _flat(result.output)
    assert MANIFEST_NAME in result.output


def test_sync_without_force_leaves_the_remote_snapshot_untouched(
    fake_client: _FakeClient, tmp_path: Path
) -> None:
    source = _write_source(tmp_path, {"app.py": "one"})

    result = runner.invoke(dbr.app, _sync_arguments(source))

    assert result.exit_code == 0, result.output
    assert fake_client.workspace.uploads == [f"{_REMOTE}/app.py"]
    assert _MANIFEST not in fake_client.workspace.files
    assert "snapshot" not in result.output.lower()


def test_sync_force_reports_a_corrupt_remote_snapshot(
    fake_client: _FakeClient, tmp_path: Path
) -> None:
    fake_client.workspace.files[_MANIFEST] = b"{not json"
    source = _write_source(tmp_path, {"app.py": "one"})

    result = runner.invoke(dbr.app, _sync_arguments(source, "--force"))

    assert result.exit_code == 1
    assert "is not valid JSON" in result.output
    assert "Traceback" not in result.output
    # The snapshot is read before anything is uploaded, so a corrupt one never
    # leaves the workspace folder half updated.
    assert fake_client.workspace.uploads == []


def test_sync_force_dry_run_lists_every_ignored_file(
    fake_client: _FakeClient, tmp_path: Path
) -> None:
    source = _write_source(tmp_path, {".gitignore": "*", "bundle.js": "js"})

    result = runner.invoke(dbr.app, _sync_arguments(source, "--force", "--dry-run"))

    assert result.exit_code == 0, result.output
    assert fake_client.workspace.uploads == []
    assert "bundle.js" in result.output
    assert "Would upload 2" in _flat(result.output)


def test_sync_dry_run_lists_files_without_uploading(
    fake_client: _FakeClient, tmp_path: Path
) -> None:
    source = _write_source(tmp_path, {"app.py": "one"})

    result = runner.invoke(dbr.app, _sync_arguments(source, "--dry-run"))

    assert result.exit_code == 0, result.output
    assert fake_client.workspace.uploads == []
    assert fake_client.workspace.files == {}
    assert "  + app.py" in result.output
    assert "Would upload 1" in _flat(result.output)
    assert "Dry run: no files were uploaded." in result.output
    assert "Uploading" not in result.output
    assert "\r" not in result.output


def test_deploy_dry_run_neither_syncs_nor_deploys(
    fake_client: _FakeClient, tmp_path: Path
) -> None:
    source = _write_source(tmp_path, {"app.py": "one"})

    result = runner.invoke(dbr.app, _deploy_arguments(source, "--dry-run"))

    assert result.exit_code == 0, result.output
    assert fake_client.workspace.uploads == []
    assert fake_client.apps.deployments == []
    assert (
        "Dry run: no files changed and deployment was not triggered." in result.output
    )
    # A dry run hashes and diffs, but never uploads, deletes or deploys.
    flat = _flat(result.output)
    assert "Hashing" in flat
    assert "Uploading" not in flat
    assert "Deploying Databricks App" not in flat


def test_sync_uploads_a_single_file_under_its_own_name(
    fake_client: _FakeClient, tmp_path: Path
) -> None:
    _write_source(
        tmp_path,
        {".gitignore": "app.yaml\n", "app.yaml": "kind: App", "other.py": "one"},
    )

    result = runner.invoke(dbr.app, _sync_arguments(tmp_path / "app.yaml"))

    assert result.exit_code == 0, result.output
    # An explicitly named file is uploaded even though .gitignore matches it.
    assert fake_client.workspace.uploads == [f"{_REMOTE}/app.yaml"]
    assert "Uploaded 1 files" in _flat(result.output)


def test_sync_single_file_still_honours_exclude(
    fake_client: _FakeClient, tmp_path: Path
) -> None:
    _write_source(tmp_path, {"app.yaml": "kind: App"})

    result = runner.invoke(
        dbr.app, _sync_arguments(tmp_path / "app.yaml", "--exclude", "app.yaml")
    )

    assert result.exit_code == 0, result.output
    assert fake_client.workspace.uploads == []
    assert "Uploaded 0 files" in _flat(result.output)


def test_missing_source_path_reports_a_clear_error(
    fake_client: _FakeClient, tmp_path: Path
) -> None:
    result = runner.invoke(dbr.app, _sync_arguments(tmp_path / "missing.yaml"))

    assert result.exit_code == 2
    assert "source path does not exist" in result.output
    assert "Traceback" not in result.output


def test_deploy_of_a_single_file_keeps_the_rest_of_the_deployment(
    fake_client: _FakeClient, tmp_path: Path
) -> None:
    source = _write_source(tmp_path, {"app.py": "one", "server/main.py": "two"})
    runner.invoke(dbr.app, _deploy_arguments(source))
    _write_source(source, {"app.yaml": "kind: App"})
    fake_client.workspace.uploads.clear()

    result = runner.invoke(dbr.app, _deploy_arguments(source / "app.yaml"))

    assert result.exit_code == 0, result.output
    assert _source_uploads(fake_client) == [f"{_REMOTE}/app.yaml"]
    # A single-file source owns nothing else: no remote file is deleted and the
    # manifest keeps the entries of the files it never looked at.
    assert fake_client.workspace.deleted == []
    assert _manifest_paths(fake_client) == {"app.py", "server/main.py", "app.yaml"}
    assert "completed with state" in result.output


def test_deploy_of_a_single_unchanged_file_skips_the_deployment(
    fake_client: _FakeClient, tmp_path: Path
) -> None:
    source = _write_source(tmp_path, {"app.yaml": "kind: App"})
    runner.invoke(dbr.app, _deploy_arguments(source / "app.yaml"))
    deployments = len(fake_client.apps.deployments)

    result = runner.invoke(dbr.app, _deploy_arguments(source / "app.yaml"))

    assert result.exit_code == 0, result.output
    assert len(fake_client.apps.deployments) == deployments
    assert "No source changes detected." in result.output
    assert "Deployment skipped" in _flat(result.output)
    assert "Unchanged 1" in _flat(result.output)


def test_upload_failure_does_not_update_the_manifest(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    client = _FakeClient(_app_info())
    client.workspace = _FailingAfterFirstUpload()
    monkeypatch.setattr(dbr, "_workspace_client", lambda **_: client)
    source = _write_source(tmp_path, {"app.py": "one", "server/two.py": "two"})

    result = runner.invoke(dbr.app, _deploy_arguments(source, "--jobs", "1"))

    assert result.exit_code == 1
    assert _MANIFEST not in client.workspace.files
    assert len(client.workspace.uploads) == 1


def test_parallel_upload_failure_does_not_update_the_manifest(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    client = _FakeClient(_app_info())
    client.workspace = _RejectingUpload(f"{_REMOTE}/server/two.py")
    monkeypatch.setattr(dbr, "_workspace_client", lambda **_: client)
    source = _write_source(tmp_path, {"app.py": "one", "server/two.py": "two"})

    result = runner.invoke(dbr.app, _deploy_arguments(source))

    assert result.exit_code == 1
    assert "/server/two.py'" in result.output
    assert "Traceback" not in result.output
    assert _MANIFEST not in client.workspace.files
    assert not client.apps.deployments


def test_source_uploads_run_in_parallel(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    client = _FakeClient(_app_info())
    client.workspace = _ConcurrencyProbe()
    monkeypatch.setattr(dbr, "_workspace_client", lambda **_: client)
    source = _write_source(tmp_path, {f"file{i}.py": "content" for i in range(4)})

    result = runner.invoke(dbr.app, _sync_arguments(source))

    assert result.exit_code == 0, result.output
    assert len(client.workspace.uploads) == 4
    assert client.workspace.peak["uploads"] > 1


def test_deletions_run_in_parallel(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    client = _FakeClient(_app_info())
    monkeypatch.setattr(dbr, "_workspace_client", lambda **_: client)
    source = _write_source(tmp_path, {f"file{i}.py": "content" for i in range(4)})
    runner.invoke(dbr.app, _deploy_arguments(source))

    probe = _ConcurrencyProbe()
    probe.files = dict(client.workspace.files)
    client.workspace = probe
    for index in range(3):
        (source / f"file{index}.py").unlink()

    result = runner.invoke(dbr.app, _deploy_arguments(source))

    assert result.exit_code == 0, result.output
    assert len(probe.deleted) == 3
    assert probe.peak["deletes"] > 1


def test_jobs_one_transfers_sequentially(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    client = _FakeClient(_app_info())
    client.workspace = _ConcurrencyProbe()
    monkeypatch.setattr(dbr, "_workspace_client", lambda **_: client)
    source = _write_source(tmp_path, {f"file{i}.py": "content" for i in range(4)})

    result = runner.invoke(dbr.app, _sync_arguments(source, "--jobs", "1"))

    assert result.exit_code == 0, result.output
    assert len(client.workspace.uploads) == 4
    assert client.workspace.peak["uploads"] == 1


def test_jobs_must_be_positive(fake_client: _FakeClient, tmp_path: Path) -> None:
    source = _write_source(tmp_path, {"app.py": "one"})

    result = runner.invoke(dbr.app, _sync_arguments(source, "--jobs", "0"))

    assert result.exit_code == 2
    assert "--jobs" in result.output


def test_throttled_uploads_are_retried(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _fast_retries(monkeypatch)
    client = _FakeClient(_app_info())
    probe = _ThrottlingWorkspace(free=2)
    client.workspace = probe
    monkeypatch.setattr(dbr, "_workspace_client", lambda **_: client)
    source = _write_source(tmp_path, {"app.py": "one", "server/two.py": "two"})

    result = runner.invoke(dbr.app, _deploy_arguments(source))

    assert result.exit_code == 0, result.output
    assert probe.throttled == 2
    assert sorted(_source_uploads(client)) == [
        f"{_REMOTE}/app.py",
        f"{_REMOTE}/server/two.py",
    ]
    assert _manifest_paths(client) == {"app.py", "server/two.py"}


def test_throttled_deletions_are_retried(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _fast_retries(monkeypatch)
    client = _FakeClient(_app_info())
    monkeypatch.setattr(dbr, "_workspace_client", lambda **_: client)
    source = _write_source(tmp_path, {"app.py": "one"})
    runner.invoke(dbr.app, _deploy_arguments(source))

    probe = _ThrottlingWorkspace(free=1)
    probe.files = dict(client.workspace.files)
    client.workspace = probe
    (source / "app.py").unlink()

    result = runner.invoke(dbr.app, _deploy_arguments(source))

    assert result.exit_code == 0, result.output
    assert probe.throttled == 1
    assert probe.deleted == [f"{_REMOTE}/app.py"]


def test_an_endless_throttle_fails_with_a_jobs_remedy(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _fast_retries(monkeypatch)
    client = _FakeClient(_app_info())
    probe = _ThrottlingWorkspace(free=100)
    client.workspace = probe
    monkeypatch.setattr(dbr, "_workspace_client", lambda **_: client)
    source = _write_source(tmp_path, {"app.py": "one"})

    result = runner.invoke(dbr.app, _deploy_arguments(source))

    assert result.exit_code == 1
    assert "Too many requests" in result.output
    assert "--jobs 2" in result.output
    assert "Traceback" not in result.output
    assert "service principal" not in result.output
    # One file, one attempt each: the policy gives up instead of looping.
    assert probe.throttled == dbr_workspace.DEFAULT_ATTEMPTS
    assert _MANIFEST not in client.workspace.files


def _fast_retries(monkeypatch: pytest.MonkeyPatch) -> None:
    """Shrink the retry backoff so the tests do not sleep for real."""
    monkeypatch.setattr(dbr_workspace, "_RETRY_INITIAL_SECONDS", 0.001)
    monkeypatch.setattr(dbr_workspace, "_RETRY_MAX_SECONDS", 0.002)


def test_delete_failure_keeps_the_previous_manifest(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    client = _FakeClient(_app_info())
    monkeypatch.setattr(dbr, "_workspace_client", lambda **_: client)
    source = _write_source(tmp_path, {"app.py": "one", "server/old.py": "old"})
    runner.invoke(dbr.app, _deploy_arguments(source))
    previous = client.workspace.files[_MANIFEST]

    rejecting = _RejectingDelete()
    rejecting.files = dict(client.workspace.files)
    client.workspace = rejecting
    (source / "server" / "old.py").unlink()

    result = runner.invoke(dbr.app, _deploy_arguments(source))

    assert result.exit_code == 1
    assert rejecting.files[_MANIFEST] == previous
    assert "was not updated" in result.output


def test_corrupt_remote_manifest_reports_a_clear_error(
    fake_client: _FakeClient, tmp_path: Path
) -> None:
    fake_client.workspace.files[_MANIFEST] = b"{not json"
    source = _write_source(tmp_path, {"app.py": "one"})

    result = runner.invoke(dbr.app, _deploy_arguments(source))

    assert result.exit_code == 1
    assert "is not valid JSON" in result.output
    assert "Traceback" not in result.output
    assert fake_client.workspace.uploads == []


def test_unsupported_manifest_version_reports_a_clear_error(
    fake_client: _FakeClient, tmp_path: Path
) -> None:
    fake_client.workspace.files[_MANIFEST] = json.dumps(
        {"version": 99, "files": {}}
    ).encode("utf-8")
    source = _write_source(tmp_path, {"app.py": "one"})

    result = runner.invoke(dbr.app, _deploy_arguments(source))

    assert result.exit_code == 1
    assert "unsupported manifest version 99" in result.output
    assert fake_client.workspace.uploads == []


def test_manifest_without_files_mapping_reports_a_clear_error(
    fake_client: _FakeClient, tmp_path: Path
) -> None:
    fake_client.workspace.files[_MANIFEST] = b'{"version": 1}'
    source = _write_source(tmp_path, {"app.py": "one"})

    result = runner.invoke(dbr.app, _deploy_arguments(source))

    assert result.exit_code == 1
    assert "has no 'files' mapping" in result.output


def test_manifest_entry_without_digest_reports_a_clear_error(
    fake_client: _FakeClient, tmp_path: Path
) -> None:
    fake_client.workspace.files[_MANIFEST] = json.dumps(
        {"version": 1, "files": {"app.py": {"size": 3}}}
    ).encode("utf-8")
    source = _write_source(tmp_path, {"app.py": "one"})

    result = runner.invoke(dbr.app, _deploy_arguments(source))

    assert result.exit_code == 1
    assert "must provide a 'sha256' and 'size'" in result.output


# --- low-level transfer options --------------------------------------------


def test_sync_no_recursive_skips_nested_directories(
    fake_client: _FakeClient, tmp_path: Path
) -> None:
    source = _write_source(tmp_path, {"app.py": "one", "server/main.py": "two"})

    result = runner.invoke(dbr.app, _sync_arguments(source, "--no-recursive"))

    assert result.exit_code == 0, result.output
    assert fake_client.workspace.uploads == [f"{_REMOTE}/app.py"]


def test_sync_excludes_matching_files(fake_client: _FakeClient, tmp_path: Path) -> None:
    source = _write_source(
        tmp_path, {"app.py": "one", "notes.md": "two", "docs/readme.md": "three"}
    )

    result = runner.invoke(dbr.app, _sync_arguments(source, "--exclude", "*.md"))

    assert result.exit_code == 0, result.output
    assert fake_client.workspace.uploads == [f"{_REMOTE}/app.py"]


def test_exclude_wins_over_include(fake_client: _FakeClient, tmp_path: Path) -> None:
    source = _write_source(
        tmp_path,
        {
            ".gitignore": "dist/\n",
            "dist/client/index.html": "<html>",
            "dist/client/app.js": "js",
        },
    )

    result = runner.invoke(
        dbr.app,
        _sync_arguments(
            source, "--include", "dist/", "--exclude", "dist/client/index.html"
        ),
    )

    assert result.exit_code == 0, result.output
    assert set(fake_client.workspace.uploads) == {
        f"{_REMOTE}/.gitignore",
        f"{_REMOTE}/dist/client/app.js",
    }


def test_deploy_excludes_matching_files(
    fake_client: _FakeClient, tmp_path: Path
) -> None:
    source = _write_source(tmp_path, {"app.py": "one", "notes.md": "two"})

    result = runner.invoke(dbr.app, _deploy_arguments(source, "--exclude", "*.md"))

    assert result.exit_code == 0, result.output
    assert _manifest_paths(fake_client) == {"app.py"}
    assert f"{_REMOTE}/notes.md" not in fake_client.workspace.files
    assert len(fake_client.apps.deployments) == 1


def test_deploy_deletes_files_excluded_from_a_later_deployment(
    fake_client: _FakeClient, tmp_path: Path
) -> None:
    source = _write_source(tmp_path, {"app.py": "one", "notes.md": "two"})
    runner.invoke(dbr.app, _deploy_arguments(source))

    result = runner.invoke(dbr.app, _deploy_arguments(source, "--exclude", "*.md"))

    assert result.exit_code == 0, result.output
    assert fake_client.workspace.deleted == [f"{_REMOTE}/notes.md"]
    assert "  - notes.md" in result.output
    assert _manifest_paths(fake_client) == {"app.py"}


def test_progress_bars_stay_silent_without_a_terminal(
    fake_client: _FakeClient, tmp_path: Path
) -> None:
    source = _write_source(tmp_path, {"app.py": "one", "server/main.py": "two"})

    result = runner.invoke(dbr.app, _deploy_arguments(source))

    assert result.exit_code == 0, result.output
    assert "\r" not in result.output
