"""Databricks Apps operations: source path resolution and deployments."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .models import DeploymentResult
from .progress import NullProgressReporter, ProgressReporter
from .workspace import normalize_workspace_path

if TYPE_CHECKING:  # pragma: no cover
    from databricks.sdk import WorkspaceClient


class AppSourcePathMissingError(RuntimeError):
    """Raised when an app has no source code path to deploy into."""

    def __init__(self, app_name: str) -> None:
        """Record which app has no usable source folder."""
        self.app_name = app_name
        super().__init__(f"app '{app_name}' has no source code path")


class DatabricksAppDeployer:
    """Resolve an app's source folder and trigger its snapshot deployments."""

    def __init__(
        self, client: WorkspaceClient, progress: ProgressReporter | None = None
    ) -> None:
        """Store the client and the reporter used for indeterminate steps."""
        self.client = client
        self._progress = progress or NullProgressReporter()

    def resolve_source_code_path(self, app_name: str, override: str | None) -> str:
        """Return the workspace folder that holds the app's source code."""
        if override:
            return normalize_workspace_path(override)
        app_info = self.client.apps.get(name=app_name)
        remote_root = app_info.source_code_path or app_info.default_source_code_path
        if not remote_root:
            raise AppSourcePathMissingError(app_name)
        return normalize_workspace_path(remote_root)

    def deploy(self, app_name: str, source_code_path: str) -> DeploymentResult:
        """Deploy the app from its source folder and make sure compute runs.

        Neither step reports a reliable percentage, so they are surfaced as
        indeterminate status instead of a fabricated progress bar.
        """
        from databricks.sdk.service.apps import (
            AppDeployment,
            AppDeploymentMode,
            ComputeState,
        )

        with self._progress.deploying("Deploying Databricks App..."):
            deployment = self.client.apps.deploy_and_wait(
                app_name=app_name,
                app_deployment=AppDeployment(
                    source_code_path=source_code_path,
                    mode=AppDeploymentMode.SNAPSHOT,
                ),
            )
        state = deployment.status.state if deployment.status else None

        app_info = self.client.apps.get(name=app_name)
        compute_state = (
            app_info.compute_status.state if app_info.compute_status else None
        )
        started = compute_state in (None, ComputeState.STOPPED)
        if started:
            with self._progress.deploying("Starting Databricks App..."):
                self.client.apps.start_and_wait(name=app_name)
        return DeploymentResult(
            deployment_id=str(deployment.deployment_id),
            state=str(getattr(state, "value", state)) if state is not None else None,
            app_url=app_info.url,
            started=started,
        )
