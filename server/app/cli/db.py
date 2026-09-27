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
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import AsyncEngine

from ..bootstrap.config import repository_root

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
    resolved_url = database_url or os.getenv("MW_DATABASE_URL") or _DEFAULT_DATABASE_URL
    config.set_main_option("sqlalchemy.url", resolved_url)
    return config


def apply_migrations(engine: AsyncEngine, revision: str = "head") -> None:
    """Apply migrations through an engine the caller already owns.

    Alembic otherwise opens its own connection, which never works for an
    in-memory SQLite database: it only exists for the process and pool that
    created it. Injecting the engine keeps the schema and the runtime traffic on
    one database. Synchronous callers such as the CLI use this helper.
    """

    async def run() -> None:
        async with engine.connect() as connection:
            await connection.run_sync(_upgrade_on_connection, revision)

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
    command.revision(
        alembic_config(url),
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
    command.upgrade(alembic_config(url), revision, sql=sql, tag=tag)


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
    command.downgrade(alembic_config(url), revision, sql=sql, tag=tag)


@app.command()
def current(url: DatabaseUrl = None, verbose: bool = False) -> None:
    """Display the revision currently recorded by the database."""
    command.current(alembic_config(url), verbose=verbose)


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
    command.stamp(alembic_config(url), revision, purge=purge)


@app.command()
def check(url: DatabaseUrl = None) -> None:
    """Fail if autogenerate detects model changes absent from migrations."""
    command.check(alembic_config(url))


@app.command()
def merge(
    revisions: Annotated[list[str], typer.Argument(help="Heads to merge.")],
    message: Annotated[str, typer.Option("--message", "-m", help="Merge message")],
    url: DatabaseUrl = None,
) -> None:
    """Create a merge revision with the next four-digit prefix."""
    command.merge(
        alembic_config(url),
        revisions=revisions,
        message=message,
        rev_id=next_revision_id(),
    )
