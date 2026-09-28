"""``mw dbr`` commands: transfer local sources and deploy a Databricks App.

Typer only routes commands, parses options and decides exit codes; Rich renders
everything through :class:`RichPresenter`, and the deployment services in this
package keep the business logic. That split keeps the Jenkins log clean while a
terminal gets live progress.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Annotated, Any, Never

import typer
from rich.console import Console

from ...bootstrap.config import repository_root
from . import (
    DEFAULT_JOBS,
    AppSourcePathMissingError,
    DatabricksAppDeployer,
    DatabricksAuthConfig,
    DatabricksAuthError,
    DatabricksClientFactory,
    DatabricksDeploymentService,
    ManifestError,
    SourceScanOptions,
    SourceSyncService,
    SyncRequest,
    UploadRequest,
    WorkspaceError,
)
from .rich_reporter import RichPresenter

if TYPE_CHECKING:  # pragma: no cover
    from databricks.sdk import WorkspaceClient

app = typer.Typer(
    help="Sync sources to a Databricks App and deploy it.", no_args_is_help=True
)

console = Console(soft_wrap=True)

HostOption = Annotated[
    str | None,
    typer.Option(
        "--host",
        help=(
            "Workspace URL, e.g. https://adb-1234567890.12.azuredatabricks.net. "
            "Falls back to DATABRICKS_HOST."
        ),
    ),
]
ProfileOption = Annotated[
    str | None,
    typer.Option(
        "--profile",
        help=(
            "Databricks configuration profile, for example DEFAULT. "
            "Falls back to DATABRICKS_CONFIG_PROFILE."
        ),
    ),
]
ClientIdOption = Annotated[
    str | None,
    typer.Option(
        "--client-id",
        help=(
            "Service principal client id for OAuth machine-to-machine auth. "
            "Falls back to DATABRICKS_CLIENT_ID."
        ),
    ),
]
ClientSecretOption = Annotated[
    str | None,
    typer.Option(
        "--client-secret",
        help=(
            "Service principal client secret for OAuth machine-to-machine auth. "
            "Falls back to DATABRICKS_CLIENT_SECRET."
        ),
    ),
]
AzureClientIdOption = Annotated[
    str | None,
    typer.Option(
        "--azure-client-id",
        help=(
            "Azure AD application (client) id for Azure client-secret auth. "
            "Falls back to AZURE_CLIENT_ID."
        ),
    ),
]
AzureClientSecretOption = Annotated[
    str | None,
    typer.Option(
        "--azure-client-secret",
        help=(
            "Azure AD client secret for Azure client-secret auth. "
            "Falls back to AZURE_CLIENT_SECRET."
        ),
    ),
]
AzureTenantIdOption = Annotated[
    str | None,
    typer.Option(
        "--azure-tenant-id",
        help=(
            "Azure AD tenant id for Azure client-secret auth. Falls back to "
            "AZURE_TENANT_ID, and is discovered from the login page when omitted."
        ),
    ),
]
AppOption = Annotated[str, typer.Option("--app", help="Name of the target app.")]
SourceOption = Annotated[
    str | None,
    typer.Option(
        "--source",
        help=(
            "Local directory to sync, or a single file to upload under its own "
            "name; defaults to the repository root."
        ),
    ),
]
IncludeOption = Annotated[
    list[str] | None,
    typer.Option(
        "--include",
        help="Gitignore-style pattern to force-include despite .gitignore; repeatable.",
    ),
]
ExcludeOption = Annotated[
    list[str] | None,
    typer.Option(
        "--exclude",
        help=(
            "Gitignore-style pattern to skip; wins over .gitignore and --include. "
            "Repeatable."
        ),
    ),
]
SourceCodePathOption = Annotated[
    str | None,
    typer.Option(
        "--source-code-path",
        help=(
            "Workspace folder to upload into; defaults to the app's configured "
            "path, which its service principal must be able to write to."
        ),
    ),
]
DryRunOption = Annotated[
    bool,
    typer.Option(
        "--dry-run",
        help="Report the changes that would be synced without touching the workspace.",
    ),
]
JobsOption = Annotated[
    int,
    typer.Option(
        "--jobs",
        min=1,
        help=(
            "Number of files to upload or delete at the same time. Use 1 to "
            "transfer sequentially."
        ),
    ),
]
RecursiveOption = Annotated[
    bool,
    typer.Option(
        "--recursive/--no-recursive",
        help="Upload the whole tree, or only the files directly in --source.",
    ),
]
ForceDeployOption = Annotated[
    bool,
    typer.Option(
        "--force-deploy",
        help="Deploy even when no source file changed since the last deployment.",
    ),
]
ForceUploadOption = Annotated[
    bool,
    typer.Option(
        "--force",
        help=(
            "Ignore .gitignore rules, upload every file under --source, for "
            "example build output the repository ignores, and refresh the remote "
            "deployment snapshot with the uploaded files."
        ),
    ),
]


def _workspace_client(**kwargs: Any) -> WorkspaceClient:
    """Build a Databricks client, importing the SDK only when it is needed."""
    from databricks.sdk import WorkspaceClient

    return WorkspaceClient(**kwargs)


def _load_project_env() -> None:
    """Load the repository-root .env so it can back the CLI options.

    ``override=True`` makes the project file authoritative: a variable defined
    in ``.env`` replaces one exported by the ambient environment (for example a
    stale ``AZURE_*`` value from the shell).
    """
    from dotenv import load_dotenv

    load_dotenv(dotenv_path=repository_root() / ".env", override=True)


@app.callback()
def _configure() -> None:
    """Load local environment variables before Typer parses each command.

    Click runs this group callback before it builds the sub-command context, so
    variables from ``.env`` are resolved into the authentication options.
    """
    _load_project_env()


def _create_client(
    host: str | None,
    profile: str | None,
    client_id: str | None,
    client_secret: str | None,
    azure_client_id: str | None,
    azure_client_secret: str | None,
    azure_tenant_id: str | None,
) -> WorkspaceClient:
    """Authenticate and return the workspace client for this command."""
    factory = DatabricksClientFactory(create_client=_workspace_client)
    config = DatabricksAuthConfig(
        host=host,
        profile=profile,
        client_id=client_id,
        client_secret=client_secret,
        azure_client_id=azure_client_id,
        azure_client_secret=azure_client_secret,
        azure_tenant_id=azure_tenant_id,
    )
    try:
        return factory.create(config)
    except DatabricksAuthError as error:
        raise typer.BadParameter(str(error)) from error


def _service(
    client: WorkspaceClient, presenter: RichPresenter, jobs: int = DEFAULT_JOBS
) -> DatabricksDeploymentService:
    """Compose the deployment subsystem, sharing one progress presenter."""
    return DatabricksDeploymentService(
        client,
        app_deployer=DatabricksAppDeployer(client, presenter),
        sync_service=SourceSyncService(presenter),
        progress=presenter,
        jobs=jobs,
    )


def _remote_root(
    client: WorkspaceClient, app_name: str, source_code_path: str | None
) -> str:
    """Resolve the app source folder, reporting a missing one as a usage error."""
    try:
        return DatabricksAppDeployer(client).resolve_source_code_path(
            app_name, source_code_path
        )
    except AppSourcePathMissingError as error:
        raise typer.BadParameter(f"{error}; pass --source-code-path") from error


def _local_root(source: str | None) -> Path:
    """Resolve the local directory, or single file, whose contents are uploaded."""
    root = Path(source).expanduser().resolve() if source else repository_root()
    if not root.is_dir() and not root.is_file():
        raise typer.BadParameter(f"source path does not exist: {root}")
    return root


def _scan_options(
    include: list[str] | None,
    exclude: list[str] | None,
    *,
    recursive: bool = True,
    force: bool = False,
) -> SourceScanOptions:
    """Translate the CLI filter options into source scan options."""
    return SourceScanOptions(
        include=tuple(include or ()),
        exclude=tuple(exclude or ()),
        recursive=recursive,
        force=force,
    )


def _identity(client: WorkspaceClient) -> str | None:
    """Return the authenticated identity, when the workspace reports it."""
    try:
        return client.current_user.me().user_name
    except Exception:
        return None


def _abort(
    client: WorkspaceClient, presenter: RichPresenter, error: WorkspaceError
) -> Never:
    """Report a remote failure and stop with a non-zero exit code."""
    presenter.render_error(error, identity=_identity(client))
    raise typer.Exit(code=1)


@app.command()
def sync(
    app_name: AppOption,
    host: HostOption = None,
    profile: ProfileOption = None,
    client_id: ClientIdOption = None,
    client_secret: ClientSecretOption = None,
    azure_client_id: AzureClientIdOption = None,
    azure_client_secret: AzureClientSecretOption = None,
    azure_tenant_id: AzureTenantIdOption = None,
    source: SourceOption = None,
    include: IncludeOption = None,
    exclude: ExcludeOption = None,
    source_code_path: SourceCodePathOption = None,
    recursive: RecursiveOption = True,
    force: ForceUploadOption = False,
    jobs: JobsOption = DEFAULT_JOBS,
    dry_run: DryRunOption = False,
) -> None:
    """Upload a local directory into the app's workspace folder without deploying.

    This is the low-level transfer: it copies the selected files and compares
    nothing, so it never deletes remote files. Files are transferred ``--jobs``
    at a time. ``--force`` additionally uploads files that .gitignore hides and
    refreshes the remote deployment snapshot (``.deploy-manifest.json``) with
    what it uploaded, so the next deploy does not see those files as new again.
    ``--source`` may name a single file, which is uploaded under its own name
    without consulting any .gitignore.
    """
    presenter = RichPresenter(console)
    client = _create_client(
        host,
        profile,
        client_id,
        client_secret,
        azure_client_id,
        azure_client_secret,
        azure_tenant_id,
    )
    remote_root = _remote_root(client, app_name, source_code_path)
    presenter.announce(remote_root)
    try:
        result = _service(client, presenter, jobs).upload(
            UploadRequest(
                local_root=_local_root(source),
                remote_root=remote_root,
                scan=_scan_options(include, exclude, recursive=recursive, force=force),
                dry_run=dry_run,
                force=force,
            )
        )
    except ManifestError as error:
        presenter.render_error(error)
        raise typer.Exit(code=1) from error
    except WorkspaceError as error:
        _abort(client, presenter, error)
    presenter.render_upload(result, remote_root)


@app.command()
def deploy(
    app_name: AppOption,
    host: HostOption = None,
    profile: ProfileOption = None,
    client_id: ClientIdOption = None,
    client_secret: ClientSecretOption = None,
    azure_client_id: AzureClientIdOption = None,
    azure_client_secret: AzureClientSecretOption = None,
    azure_tenant_id: AzureTenantIdOption = None,
    source: SourceOption = None,
    include: IncludeOption = None,
    exclude: ExcludeOption = None,
    source_code_path: SourceCodePathOption = None,
    dry_run: DryRunOption = False,
    force_deploy: ForceDeployOption = False,
    jobs: JobsOption = DEFAULT_JOBS,
) -> None:
    """Sync local sources and trigger a snapshot deployment of the app.

    Only files whose SHA-256 changed since the last successful deployment are
    uploaded, and only files that deployment owned are ever deleted; both run
    ``--jobs`` at a time. A run without changes deploys nothing unless
    ``--force-deploy`` asks for it. ``--source`` may name a single file, which
    then only ever touches that file: its deployment is kept, and nothing else
    is deleted or dropped from the manifest.
    """
    presenter = RichPresenter(console)
    client = _create_client(
        host,
        profile,
        client_id,
        client_secret,
        azure_client_id,
        azure_client_secret,
        azure_tenant_id,
    )
    remote_root = _remote_root(client, app_name, source_code_path)
    presenter.announce(remote_root)
    request = SyncRequest(
        local_root=_local_root(source),
        remote_root=remote_root,
        scan=_scan_options(include, exclude),
        dry_run=dry_run,
    )
    service = _service(client, presenter, jobs)
    try:
        sync_result = service.reconcile(request)
        presenter.render_sync(sync_result, dry_run=dry_run)
        if dry_run:
            presenter.render_dry_run_deploy()
            return
        if not sync_result.diff.has_changes and not force_deploy:
            presenter.render_skipped_deploy()
            return
        deployment = service.deploy_app(app_name, remote_root)
    except ManifestError as error:
        presenter.render_error(error)
        raise typer.Exit(code=1) from error
    except WorkspaceError as error:
        _abort(client, presenter, error)
    presenter.render_deployment(deployment)
