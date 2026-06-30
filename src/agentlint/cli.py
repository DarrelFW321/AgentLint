"""Command-line interface for AgentLint."""

from __future__ import annotations

import platform
import sys
from pathlib import Path

import typer

from agentlint.version import __version__

app = typer.Typer(
    name="agentlint",
    help="A CI linter for AI agent execution traces.",
    no_args_is_help=True,
    add_completion=False,
)


@app.command()
def version() -> None:
    """Print the AgentLint version."""
    typer.echo(__version__)


@app.command()
def doctor() -> None:
    """Print basic runtime diagnostics."""
    supported_python = sys.version_info >= (3, 12)

    typer.echo(f"AgentLint: {__version__}")
    typer.echo(f"Python: {platform.python_version()}")
    typer.echo(f"Python >=3.12: {'yes' if supported_python else 'no'}")
    typer.echo(f"Working directory: {Path.cwd()}")


def main() -> None:
    """Run the AgentLint CLI."""
    app()


if __name__ == "__main__":
    main()
