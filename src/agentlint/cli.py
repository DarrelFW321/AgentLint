"""Command-line interface for AgentLint."""

from __future__ import annotations

import platform
import sys
from pathlib import Path
from typing import Annotated

import typer

from agentlint.diagnostics import Severity, format_diagnostics
from agentlint.ir.v1 import (
    TraceFileError,
    TraceJsonError,
    TraceLoadError,
    TraceSchemaError,
    format_validation_error,
    load_native_trace,
)
from agentlint.passes import validate_structure
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


@app.command()
def validate(
    trace_path: Annotated[Path, typer.Argument(help="Native AgentLint trace JSON file.")],
) -> None:
    """Validate a native AgentLint trace file."""
    try:
        trace = load_native_trace(trace_path)
    except TraceSchemaError as exc:
        typer.echo(f"error: {exc}", err=True)
        for formatted_error in format_validation_error(exc.validation_error):
            typer.echo(f"  - {formatted_error}", err=True)
        raise typer.Exit(1) from exc
    except (TraceFileError, TraceJsonError, TraceLoadError) as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(1) from exc

    diagnostics = validate_structure(trace)
    error_diagnostics = [
        diagnostic for diagnostic in diagnostics if diagnostic.severity == Severity.ERROR
    ]

    if diagnostics:
        typer.echo(format_diagnostics(diagnostics), err=True)
    if error_diagnostics:
        raise typer.Exit(1)

    typer.echo(f"valid trace: {trace.trace_id}")
    typer.echo(f"events: {len(trace.events)}")
    typer.echo(f"edges: {len(trace.edges)}")
    typer.echo(f"diagnostics: {len(diagnostics)}")


def main() -> None:
    """Run the AgentLint CLI."""
    app()


if __name__ == "__main__":
    main()
