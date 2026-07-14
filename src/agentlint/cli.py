"""Command-line interface for AgentLint."""

from __future__ import annotations

import platform
import sys
from pathlib import Path
from typing import Annotated

import typer

from agentlint.adapters.openai_agents import import_openai_agents_file
from agentlint.adapters.openai_snapshot import OpenAISnapshotError
from agentlint.adapters.opentelemetry import OpenTelemetryImportError, import_opentelemetry_file
from agentlint.checking import check_trace_file
from agentlint.diagnostics import Severity, explain_diagnostic_code, format_diagnostics
from agentlint.integrations.pytest_runs import check_run
from agentlint.ir.v1 import (
    TraceFileError,
    TraceJsonError,
    TraceLoadError,
    TraceSchemaError,
    format_validation_error,
    load_native_trace,
)
from agentlint.passes import evaluate_policy, validate_structure
from agentlint.policy import (
    Policy,
    PolicyFileError,
    PolicyLoadError,
    PolicySchemaError,
    PolicyYamlError,
    compile_policy,
    format_policy_validation_error,
    load_policy,
)
from agentlint.reports import (
    FailOn,
    ReportFormat,
    build_report,
    render_json_report,
    render_text_report,
    report_should_fail,
)
from agentlint.version import __version__

app = typer.Typer(
    name="agentlint",
    help="A CI linter for AI agent execution traces.",
    no_args_is_help=True,
    add_completion=False,
)
policy_app = typer.Typer(
    name="policy",
    help="Validate AgentLint policy files.",
    no_args_is_help=True,
    add_completion=False,
)
import_app = typer.Typer(
    name="import",
    help="Import external trace formats into native AgentLint IR.",
    no_args_is_help=True,
    add_completion=False,
)

app.add_typer(policy_app, name="policy")
app.add_typer(import_app, name="import")


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
def check(
    trace_paths: Annotated[
        list[Path],
        typer.Argument(help="One or more native AgentLint trace JSON files."),
    ],
    policy_path: Annotated[
        Path | None,
        typer.Option("--policy", help="AgentLint YAML policy file to evaluate."),
    ] = None,
    report_format: Annotated[
        ReportFormat,
        typer.Option("--format", help="Report output format."),
    ] = ReportFormat.TEXT,
    fail_on: Annotated[
        FailOn,
        typer.Option("--fail-on", help="Diagnostic severity threshold for exit code."),
    ] = FailOn.ERROR,
) -> None:
    """Check native AgentLint trace files and emit a report."""
    policy = _load_policy_for_cli(policy_path) if policy_path is not None else None
    results = [check_trace_file(trace_path, policy=policy) for trace_path in trace_paths]
    report = build_report(results, fail_on=fail_on)

    if report_format == ReportFormat.JSON:
        typer.echo(render_json_report(report))
    else:
        typer.echo(render_text_report(report))

    if report_should_fail(report):
        raise typer.Exit(1)


@app.command("check-run")
def check_pytest_run(
    run_path: Annotated[
        Path,
        typer.Argument(help="Captured pytest run directory, manifest, or latest pointer."),
    ],
    report_format: Annotated[
        ReportFormat,
        typer.Option("--format", help="Report output format."),
    ] = ReportFormat.TEXT,
    fail_on: Annotated[
        FailOn,
        typer.Option("--fail-on", help="Diagnostic severity threshold for exit code."),
    ] = FailOn.ERROR,
) -> None:
    """Recheck a captured pytest run with its recorded policy assignments."""
    try:
        report = check_run(run_path, fail_on=fail_on)
    except Exception as exc:
        typer.echo(f"error: could not check pytest run: {exc}", err=True)
        raise typer.Exit(1) from exc

    if report_format == ReportFormat.JSON:
        typer.echo(render_json_report(report))
    else:
        typer.echo(render_text_report(report))
    if report_should_fail(report):
        raise typer.Exit(1)


@app.command()
def validate(
    trace_path: Annotated[Path, typer.Argument(help="Native AgentLint trace JSON file.")],
    policy_path: Annotated[
        Path | None,
        typer.Option("--policy", help="AgentLint YAML policy file to evaluate."),
    ] = None,
) -> None:
    """Validate a native AgentLint trace file."""
    policy: Policy | None = None
    if policy_path is not None:
        policy = _load_policy_for_cli(policy_path)
        typer.echo(f"valid policy: {policy.policy_id}")

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

    if policy is not None:
        policy_diagnostics = evaluate_policy(trace, policy)
        diagnostics.extend(policy_diagnostics)

        if policy_diagnostics:
            typer.echo(format_diagnostics(policy_diagnostics), err=True)
        if any(diagnostic.severity == Severity.ERROR for diagnostic in policy_diagnostics):
            raise typer.Exit(1)

    typer.echo(f"valid trace: {trace.trace_id}")
    typer.echo(f"events: {len(trace.events)}")
    typer.echo(f"edges: {len(trace.edges)}")
    typer.echo(f"diagnostics: {len(diagnostics)}")


@app.command()
def explain(
    code: Annotated[str, typer.Argument(help="AgentLint diagnostic code to explain.")],
) -> None:
    """Explain an AgentLint diagnostic code."""
    explanation = explain_diagnostic_code(code)
    if explanation is None:
        typer.echo(f"error: unknown diagnostic code: {code}", err=True)
        raise typer.Exit(1)

    typer.echo(f"code: {explanation.code.value}")
    typer.echo(f"category: {explanation.category}")
    typer.echo(f"type: {explanation.kind}")
    typer.echo(f"meaning: {explanation.meaning}")
    typer.echo(f"remediation: {explanation.remediation}")


@policy_app.command("validate")
def validate_policy(
    policy_path: Annotated[Path, typer.Argument(help="AgentLint YAML policy file.")],
) -> None:
    """Validate an AgentLint YAML policy file."""
    policy = _load_policy_for_cli(policy_path)
    _echo_policy_summary(policy)


@import_app.command("opentelemetry")
def import_opentelemetry(
    input_path: Annotated[Path, typer.Argument(help="OpenTelemetry OTLP-style JSON trace file.")],
    output_path: Annotated[
        Path,
        typer.Option("--output", help="Output native AgentLint trace JSON file."),
    ],
) -> None:
    """Import an OpenTelemetry trace into native AgentLint IR."""
    try:
        result = import_opentelemetry_file(input_path)
    except OpenTelemetryImportError as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(1) from exc

    for warning in result.warnings:
        typer.echo(f"warning[{warning.code}]: {warning.message}", err=True)

    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            result.trace.model_dump_json(indent=2),
            encoding="utf-8",
        )
    except OSError as exc:
        typer.echo(f"error: could not write output trace {output_path}: {exc}", err=True)
        raise typer.Exit(1) from exc

    typer.echo(f"imported trace: {result.trace.trace_id}")
    typer.echo(f"events: {len(result.trace.events)}")
    typer.echo(f"edges: {len(result.trace.edges)}")
    typer.echo(f"warnings: {len(result.warnings)}")
    typer.echo(f"capture: {result.capture.overall_status.value}")


@import_app.command("openai-agents")
def import_openai_agents(
    input_path: Annotated[Path, typer.Argument(help="OpenAI Agents snapshot JSON file.")],
    output_path: Annotated[
        Path,
        typer.Option("--output", help="Output native AgentLint trace JSON file."),
    ],
) -> None:
    """Import an OpenAI Agents SDK snapshot into native AgentLint IR."""
    try:
        result = import_openai_agents_file(input_path)
    except OpenAISnapshotError as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(1) from exc

    for warning in result.warnings:
        typer.echo(f"warning[{warning.code}]: {warning.message}", err=True)
    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            result.trace.model_dump_json(indent=2),
            encoding="utf-8",
        )
    except OSError as exc:
        typer.echo(f"error: could not write output trace {output_path}: {exc}", err=True)
        raise typer.Exit(1) from exc

    typer.echo(f"imported trace: {result.trace.trace_id}")
    typer.echo(f"events: {len(result.trace.events)}")
    typer.echo(f"edges: {len(result.trace.edges)}")
    typer.echo(f"warnings: {len(result.warnings)}")
    typer.echo(f"capture: {result.capture.overall_status.value}")


def _load_policy_for_cli(policy_path: Path) -> Policy:
    try:
        return load_policy(policy_path)
    except PolicySchemaError as exc:
        typer.echo(f"error: {exc}", err=True)
        for formatted_error in format_policy_validation_error(exc.validation_error):
            typer.echo(f"  - {formatted_error}", err=True)
        raise typer.Exit(1) from exc
    except (PolicyFileError, PolicyYamlError, PolicyLoadError) as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(1) from exc


def _echo_policy_summary(policy: Policy) -> None:
    plan = compile_policy(policy)
    inferred_evidence = plan.inferred_evidence()
    result_boundaries = sum(tool.result is not None for tool in policy.tools.values())
    argument_boundaries = sum(
        argument.sink is not None
        for tool in policy.tools.values()
        for argument in tool.arguments.values()
    )
    typer.echo(f"valid policy: {policy.policy_id}")
    typer.echo(f"version: {policy.version}")
    typer.echo(f"tools: {len(policy.tools)}")
    typer.echo(f"sources: {len(policy.effective_sources())}")
    typer.echo(f"sinks: {len(policy.effective_sinks())}")
    typer.echo(
        f"declared boundaries: {result_boundaries} result source, "
        f"{argument_boundaries} argument sink"
    )
    typer.echo(f"rules: {len(policy.rules)}")
    active_rules = ", ".join(rule.value for rule in plan.rules) or "none"
    typer.echo(f"active checks: {active_rules}")
    evidence = (
        ", ".join(
            f"{capability.value}>={level.value}" for capability, level in inferred_evidence.items()
        )
        or "none"
    )
    typer.echo(f"inferred evidence: {evidence}")
    typer.echo(f"exceptions: {len(policy.exceptions)}")


def main() -> None:
    """Run the AgentLint CLI."""
    app()


if __name__ == "__main__":
    main()
