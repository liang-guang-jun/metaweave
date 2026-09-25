"""Metaweave command-line entry point."""

from __future__ import annotations

import typer

from .db import app as db_app
from .server import serve

app = typer.Typer(help="Metaweave command-line tools.", no_args_is_help=True)
app.add_typer(db_app, name="db")
app.command(name="server")(serve)
