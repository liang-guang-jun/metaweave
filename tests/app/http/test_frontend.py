from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from server.app.bootstrap import AppConfig
from server.app.http.frontend import mount_frontend


def _write_frontend(directory: Path) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "index.html").write_text("<html>app</html>", encoding="utf-8")
    (directory / "app.js").write_text("console.log('app')", encoding="utf-8")


def _config(directory: Path, frontend_type: str) -> AppConfig:
    return AppConfig.model_validate(
        {"app": {"frontend": {"type": frontend_type, "path": str(directory)}}}
    )


def test_mount_frontend_serves_assets_and_spa_fallback(tmp_path: Path) -> None:
    _write_frontend(tmp_path)
    app = FastAPI()
    mount_frontend(app, _config(tmp_path, "static"))

    with TestClient(app) as client:
        root = client.get("/")
        asset = client.get("/app.js")
        navigation = client.get("/login", headers={"accept": "text/html"})
        api_probe = client.get("/login", headers={"accept": "application/json"})

    assert root.status_code == 200
    assert root.text == "<html>app</html>"
    assert asset.text == "console.log('app')"
    assert navigation.status_code == 200
    assert navigation.text == "<html>app</html>"
    assert api_probe.status_code == 404


def test_mount_frontend_is_skipped_when_not_configured(tmp_path: Path) -> None:
    _write_frontend(tmp_path)
    app = FastAPI()
    mount_frontend(app, AppConfig.model_validate({"app": {"name": "test"}}))

    with TestClient(app) as client:
        response = client.get("/")

    assert response.status_code == 404


def test_mount_frontend_is_skipped_when_disabled(tmp_path: Path) -> None:
    _write_frontend(tmp_path)
    app = FastAPI()
    mount_frontend(app, _config(tmp_path, "disabled"))

    with TestClient(app) as client:
        response = client.get("/")

    assert response.status_code == 404


def test_mount_frontend_is_skipped_when_assets_are_missing(tmp_path: Path) -> None:
    app = FastAPI()
    mount_frontend(app, _config(tmp_path / "missing", "static"))

    with TestClient(app) as client:
        response = client.get("/")

    assert response.status_code == 404
