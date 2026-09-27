"""Interactive instance-administrator bootstrap commands."""

from __future__ import annotations

import asyncio
from typing import NoReturn

import typer

from ...iam.application.messages import BootstrapSystemAdmin
from ...iam.domain.errors import IamDomainError
from ..bootstrap import create_container, load_config

app = typer.Typer(help="Manage instance administrators.", no_args_is_help=True)


def _abort(message: str) -> NoReturn:
    typer.secho(message, fg=typer.colors.RED, err=True)
    raise typer.Exit(code=1)


async def create_system_admin(email: str, password: str) -> str:
    """Run the atomic user and system-ACL bootstrap use case."""
    container = create_container(load_config())
    try:
        user_id = await container.message_bus().send(
            BootstrapSystemAdmin(email=email, password=password)
        )
        return str(user_id.value)
    finally:
        await container.engine().dispose()


@app.command("create")
def create() -> None:
    """Interactively create the first verified user and system ACL grant."""
    email = typer.prompt("Email").strip()
    if not email:
        _abort("Email cannot be empty.")

    password = typer.prompt("Password", hide_input=True, confirmation_prompt=False)
    confirmation = typer.prompt(
        "Confirm password", hide_input=True, confirmation_prompt=False
    )
    if password != confirmation:
        _abort("Passwords do not match.")

    try:
        user_id = asyncio.run(create_system_admin(email, password))
    except IamDomainError as error:
        _abort(str(error))
    except Exception as error:
        _abort(f"Unable to create system administrator: {error}")

    typer.secho(
        f"Created verified user {user_id} and granted system.super_admin.",
        fg=typer.colors.GREEN,
    )
