"""Report renderers for AgentLint check results."""

from __future__ import annotations

from agentlint.checking import TraceCheckResult
from agentlint.diagnostics import format_diagnostic
from agentlint.reports.models import AgentLintReport


def render_text_report(report: AgentLintReport) -> str:
    """Render a human-readable AgentLint report."""
    lines = [
        "AgentLint Report",
        (
            f"traces: {report.summary.passed} passed, {report.summary.failed} failed, "
            f"{report.summary.invalid} invalid"
        ),
        (
            "diagnostics: "
            f"{report.summary.diagnostics.error} error, "
            f"{report.summary.diagnostics.warning} warning, "
            f"{report.summary.diagnostics.info} info"
        ),
        f"fail-on: {report.summary.fail_on.value}",
        (
            "redaction: "
            f"{report.redaction.mode}, raw values included: "
            f"{str(report.redaction.raw_values_included).lower()}"
        ),
    ]

    for result in report.runs:
        lines.extend(["", *_render_trace_result(result)])

    return "\n".join(lines)


def render_json_report(report: AgentLintReport) -> str:
    """Render a machine-readable AgentLint report."""
    return report.model_dump_json(indent=2)


def _render_trace_result(result: TraceCheckResult) -> list[str]:
    lines = [
        f"trace: {result.trace_path}",
        f"status: {result.status.value}",
    ]

    if result.trace_id is not None:
        lines.append(f"trace id: {result.trace_id}")
    if result.policy_id is not None:
        lines.append(f"policy id: {result.policy_id}")

    lines.extend(
        [
            f"events: {result.events}",
            f"edges: {result.edges}",
        ]
    )

    if result.input_error is not None:
        lines.append(f"input error[{result.input_error.kind.value}]: {result.input_error.message}")
        for detail in result.input_error.details:
            lines.append(f"  - {detail}")

    if result.diagnostics:
        lines.append("")
        lines.append("\n".join(format_diagnostic(diagnostic) for diagnostic in result.diagnostics))

    return lines
