"""Database migration commands backed by Alembic's Python API."""

from __future__ import annotations

import asyncio
import os
import re
from pathlib import Path
from typing import Annotated

import typer
from alembic import command
from alembic.config import Config
from sqlalchemy import URL
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import AsyncEngine

from ...kernel.infrastructure.persistence.sqlalchemy import create_database_backend
from ..bootstrap import create_container
from ..bootstrap.config import repository_root
from ..bootstrap.loader import load_config

app = typer.Typer(help="Manage database schema migrations.", no_args_is_help=True)

_MIGRATIONS = Path(__file__).resolve().parents[2] / "migrations"
# Anchored to the repository root so migrations touch one canonical database
# regardless of the working directory the command runs from.
_DEFAULT_DATABASE_URL = f"sqlite+aiosqlite:///{repository_root() / 'metaweave.db'}"
_REVISION_PATTERN = re.compile(r"^(?P<number>\d{4})(?:_|$)")

DatabaseUrl = Annotated[
    str | None,
    typer.Option(
        "--url",
        envvar="MW_DATABASE_URL",
        help="SQLAlchemy URL; defaults to MW_DATABASE_URL or a local SQLite database.",
    ),
]


def alembic_config(database_url: str | None = None) -> Config:
    """Create a cwd-independent Alembic configuration for the kernel schema."""
    config = Config()
    config.set_main_option("script_location", str(_MIGRATIONS))
    if database_url or os.getenv("MW_DATABASE_URL"):
        resolved_url = database_url or os.environ["MW_DATABASE_URL"]
    else:
        database = load_config().database
        if database.provider == "databricks_lakebase":
            # Online commands inject a connection with its dynamic token; this
            # URL only selects the PostgreSQL dialect and is safe for --sql.
            resolved_url = str(URL.create("postgresql+asyncpg"))
        else:
            resolved_url = str(create_database_backend(database).url())
        if resolved_url.startswith("sqlite+") and ":memory:" not in resolved_url:
            from sqlalchemy.engine import make_url
            parsed = make_url(resolved_url)
            if parsed.database and not Path(parsed.database).is_absolute():
                resolved_url = str(parsed.set(database=str(repository_root() / parsed.database)))
    config.set_main_option("sqlalchemy.url", resolved_url)
    return config


def _uses_managed_engine(url: str | None) -> bool:
    """Return whether a command must reuse a config-managed password source."""
    return not url and not os.getenv("MW_DATABASE_URL") and (
        load_config().database.provider in {"postgresql", "databricks_lakebase"}
    )


def _run_with_managed_engine(
    operation: object, url: str | None, *args: object, **kwargs: object
) -> None:
    """Run an Alembic operation through a password-owning application engine."""
    if not _uses_managed_engine(url):
        operation(alembic_config(url), *args, **kwargs)  # type: ignore[operator]
        return
    engine = create_container(load_config()).engine()

    async def run() -> None:
        async with engine.connect() as connection:
            await connection.run_sync(_run_alembic_operation, operation, args, kwargs)
        await engine.dispose()

    asyncio.run(run())


def _run_alembic_operation(
    connection: Connection,
    operation: object,
    args: tuple[object, ...],
    kwargs: dict[str, object],
) -> None:
    """Execute an Alembic command with its connection injected."""
    config = alembic_config()
    config.attributes["connection"] = connection
    operation(config, *args, **kwargs)  # type: ignore[operator]


def apply_migrations(
    engine: AsyncEngine, revision: str = "head", *, dispose_after: bool = False
) -> None:
    """Apply migrations through an engine the caller already owns.

    Alembic otherwise opens its own connection, which never works for an
    in-memory SQLite database: it only exists for the process and pool that
    created it. Injecting the engine keeps the schema and the runtime traffic on
    one database. Synchronous callers such as the CLI use this helper.
    """

    async def run() -> None:
        async with engine.connect() as connection:
            await connection.run_sync(_upgrade_on_connection, revision)
        if dispose_after:
            await engine.dispose()

    asyncio.run(run())


def _upgrade_on_connection(connection: Connection, revision: str) -> None:
    """Run an upgrade on a synchronous connection facade."""
    config = alembic_config()
    config.attributes["connection"] = connection
    command.upgrade(config, revision)


def next_revision_id(versions_dir: Path | None = None) -> str:
    """Return the next zero-padded four-digit revision prefix.

    Alembic revision identifiers remain strings, so ``0002`` is a valid ID and
    a generated file becomes ``0002_<slug>.py`` through the script template.
    """
    directory = versions_dir or _MIGRATIONS / "versions"
    highest = 0
    for path in directory.glob("*.py"):
        match = _REVISION_PATTERN.match(path.stem)
        if match is not None:
            highest = max(highest, int(match.group("number")))
    if highest >= 9999:
        raise RuntimeError("Migration revision prefix limit (9999) reached")
    return f"{highest + 1:04d}"


@app.command()
def revision(
    message: Annotated[str, typer.Argument(help="Human-readable migration message.")],
    url: DatabaseUrl = None,
    empty: Annotated[
        bool,
        typer.Option(
            "--empty", help="Create a manual migration without schema autogeneration."
        ),
    ] = False,
    head: Annotated[
        str, typer.Option(help="Parent revision, normally 'head'.")
    ] = "head",
    splice: Annotated[
        bool, typer.Option(help="Allow a branch from a non-head revision.")
    ] = False,
    branch_label: Annotated[
        str | None, typer.Option(help="Optional Alembic branch label.")
    ] = None,
) -> None:
    """Create a revision; schema autogeneration is enabled by default."""
    revision_id = next_revision_id()
    _run_with_managed_engine(
        command.revision,
        url,
        message=message,
        autogenerate=not empty,
        rev_id=revision_id,
        head=head,
        splice=splice,
        branch_label=branch_label,
    )


@app.command()
def upgrade(
    revision: Annotated[
        str, typer.Argument(help="Target revision, e.g. head or +1")
    ] = "head",
    url: DatabaseUrl = None,
    sql: Annotated[bool, typer.Option(help="Print SQL without applying it.")] = False,
    tag: Annotated[
        str | None, typer.Option(help="Optional Alembic environment tag.")
    ] = None,
) -> None:
    """Upgrade the database to a target revision."""
    if sql:
        command.upgrade(alembic_config(url), revision, sql=True, tag=tag)
    else:
        _run_with_managed_engine(command.upgrade, url, revision, tag=tag)


@app.command()
def downgrade(
    revision: Annotated[str, typer.Argument(help="Target revision, e.g. -1 or base")],
    url: DatabaseUrl = None,
    sql: Annotated[bool, typer.Option(help="Print SQL without applying it.")] = False,
    tag: Annotated[
        str | None, typer.Option(help="Optional Alembic environment tag.")
    ] = None,
) -> None:
    """Downgrade the database to a target revision."""
    if sql:
        command.downgrade(alembic_config(url), revision, sql=True, tag=tag)
    else:
        _run_with_managed_engine(command.downgrade, url, revision, tag=tag)


@app.command()
def current(url: DatabaseUrl = None, verbose: bool = False) -> None:
    """Display the revision currently recorded by the database."""
    _run_with_managed_engine(command.current, url, verbose=verbose)


@app.command()
def history(
    url: DatabaseUrl = None,
    verbose: bool = False,
    indicate_current: bool = False,
) -> None:
    """Display migration history."""
    command.history(
        alembic_config(url), verbose=verbose, indicate_current=indicate_current
    )


@app.command()
def heads(url: DatabaseUrl = None, verbose: bool = False) -> None:
    """Display current migration heads."""
    command.heads(alembic_config(url), verbose=verbose)


@app.command()
def branches(url: DatabaseUrl = None, verbose: bool = False) -> None:
    """Display migration branch points."""
    command.branches(alembic_config(url), verbose=verbose)


@app.command()
def show(revision: str, url: DatabaseUrl = None) -> None:
    """Display the details of one migration revision."""
    command.show(alembic_config(url), revision)


@app.command()
def stamp(
    revision: Annotated[
        str, typer.Argument(help="Revision to record without migration.")
    ],
    url: DatabaseUrl = None,
    purge: Annotated[
        bool, typer.Option(help="Clear existing revision stamps first.")
    ] = False,
) -> None:
    """Record a revision without executing upgrade or downgrade code."""
    _run_with_managed_engine(command.stamp, url, revision, purge=purge)


@app.command()
def check(url: DatabaseUrl = None) -> None:
    """Fail if autogenerate detects model changes absent from migrations."""
    _run_with_managed_engine(command.check, url)


@app.command()
def merge(
    revisions: Annotated[list[str], typer.Argument(help="Heads to merge.")],
    message: Annotated[str, typer.Option("--message", "-m", help="Merge message")],
    url: DatabaseUrl = None,
) -> None:
    """Create a merge revision with the next four-digit prefix."""
    _run_with_managed_engine(
        command.merge,
        url,
        revisions=revisions,
        message=message,
        rev_id=next_revision_id(),
    )
