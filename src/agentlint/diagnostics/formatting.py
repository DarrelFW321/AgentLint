"""Human-readable formatting for AgentLint diagnostics."""

from __future__ import annotations

from agentlint.diagnostics.models import Diagnostic


def format_diagnostic(diagnostic: Diagnostic) -> str:
    """Format one diagnostic for terminal output."""
    lines = [f"{diagnostic.severity.value}[{diagnostic.code.value}]: {diagnostic.message}"]

    if diagnostic.related_events:
        lines.append(f"  related events: {', '.join(diagnostic.related_events)}")
    if diagnostic.related_edges:
        lines.append(f"  related edges: {', '.join(diagnostic.related_edges)}")
    if diagnostic.path is not None:
        rendered = diagnostic.path.nodes[0].label
        for edge, node in zip(diagnostic.path.edges, diagnostic.path.nodes[1:], strict=True):
            rendered += f" --{edge.edge_type}--> {node.label}"
        lines.append(f"  path: {rendered}")
    if diagnostic.policy_reference is not None:
        lines.append(f"  policy reference: {diagnostic.policy_reference}")
    if diagnostic.remediation is not None:
        lines.append(f"  remediation: {diagnostic.remediation}")

    return "\n".join(lines)


def format_diagnostics(diagnostics: list[Diagnostic]) -> str:
    """Format multiple diagnostics for terminal output."""
    return "\n".join(format_diagnostic(diagnostic) for diagnostic in diagnostics)
