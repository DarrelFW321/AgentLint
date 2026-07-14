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
            f"{report.summary.not_verifiable} not verifiable, "
            f"{report.summary.invalid} invalid"
        ),
        (
            "diagnostics: "
            f"{report.summary.diagnostics.error} error, "
            f"{report.summary.diagnostics.warning} warning, "
            f"{report.summary.diagnostics.info} info"
        ),
        (
            "capture: "
            f"{report.summary.capture.captured} captured, "
            f"{report.summary.capture.partial} partial, "
            f"{report.summary.capture.unavailable} unavailable, "
            f"{report.summary.capture.unknown} unknown"
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
            f"capture: {result.capture.overall_status.value} ({result.capture.adapter})",
        ]
    )

    for capability, coverage in result.capture.capabilities.entries():
        label = capability.value.replace("_", " ")
        reason = f" - {coverage.reason}" if coverage.reason is not None else ""
        lines.append(f"  {label}: {coverage.status.value}{reason}")

    if result.evidence.unmet:
        lines.append("unmet evidence requirements:")
        for requirement in result.evidence.unmet:
            label = requirement.capability.value.replace("_", " ")
            lines.append(
                f"  {label}: requires {requirement.required.value}, "
                f"observed {requirement.observed.value} ({requirement.origin.value})"
            )

    if result.input_error is not None:
        lines.append(f"input error[{result.input_error.kind.value}]: {result.input_error.message}")
        for detail in result.input_error.details:
            lines.append(f"  - {detail}")

    if result.diagnostics:
        lines.append("")
        lines.append("\n".join(format_diagnostic(diagnostic) for diagnostic in result.diagnostics))

    if result.status.value == "passed" and result.capture.overall_status.value != "captured":
        lines.extend(
            [
                "",
                (
                    "Policy checks passed for the behavior represented in the trace; "
                    "incomplete capture limited verification."
                ),
            ]
        )

    return lines
