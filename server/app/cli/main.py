"""Metaweave command-line entry point."""

from __future__ import annotations

import typer

from .admin import app as admin_app
from .databricks.cli import app as dbr_app
from .db import app as db_app
from .server import serve

app = typer.Typer(help="Metaweave command-line tools.", no_args_is_help=True)
app.add_typer(admin_app, name="admin")
app.add_typer(db_app, name="db")
app.add_typer(dbr_app, name="dbr")
app.command(name="server")(serve)
