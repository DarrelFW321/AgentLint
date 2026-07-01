"""Structural validation pass for AgentLint IR traces."""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable

from agentlint.diagnostics import Diagnostic, DiagnosticCode
from agentlint.ir.v1 import (
    ApprovalEvent,
    Edge,
    FinalAnswerEvent,
    ToolCallEvent,
    ToolResultEvent,
    Trace,
)


def validate_structure(trace: Trace) -> list[Diagnostic]:
    """Validate structural relationships in a parsed trace."""
    diagnostics: list[Diagnostic] = []
    event_counts = Counter(event.id for event in trace.events)
    unique_events = {event.id: event for event in trace.events if event_counts[event.id] == 1}

    diagnostics.extend(
        _duplicate_event_diagnostics(_duplicates_in_order(event.id for event in trace.events))
    )
    diagnostics.extend(
        _duplicate_edge_diagnostics(_duplicates_in_order(edge.id for edge in trace.edges))
    )
    diagnostics.extend(_missing_reference_diagnostics(trace, event_counts))
    diagnostics.extend(_missing_tool_arguments_diagnostics(trace))

    matched_tool_results = _matched_tool_results(trace, event_counts, unique_events)
    diagnostics.extend(matched_tool_results.diagnostics)
    diagnostics.extend(
        _invalid_order_diagnostics(trace, unique_events, matched_tool_results.matches)
    )
    diagnostics.extend(_invalid_evidence_reference_diagnostics(trace, event_counts))

    return diagnostics


def _duplicates_in_order(values: Iterable[str]) -> list[str]:
    values_list = list(values)
    counts = Counter(values_list)
    seen: set[str] = set()
    duplicates: list[str] = []

    for value in values_list:
        if counts[value] > 1 and value not in seen:
            duplicates.append(value)
            seen.add(value)

    return duplicates


def _duplicate_event_diagnostics(duplicate_ids: list[str]) -> list[Diagnostic]:
    return [
        Diagnostic(
            code=DiagnosticCode.DUPLICATE_EVENT_ID,
            message=f'duplicate event id "{event_id}"',
            related_events=[event_id],
            remediation="Ensure every event id is unique within the trace.",
        )
        for event_id in duplicate_ids
    ]


def _duplicate_edge_diagnostics(duplicate_ids: list[str]) -> list[Diagnostic]:
    return [
        Diagnostic(
            code=DiagnosticCode.DUPLICATE_EDGE_ID,
            message=f'duplicate edge id "{edge_id}"',
            related_edges=[edge_id],
            remediation="Ensure every edge id is unique within the trace.",
        )
        for edge_id in duplicate_ids
    ]


def _missing_reference_diagnostics(trace: Trace, event_counts: Counter[str]) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []

    for edge in trace.edges:
        diagnostics.extend(_missing_edge_endpoint_diagnostics(edge, event_counts))

    for event in trace.events:
        if isinstance(event, ApprovalEvent) and event.subject_event is not None:
            if event_counts[event.subject_event] == 0:
                diagnostics.append(
                    Diagnostic(
                        code=DiagnosticCode.MISSING_EVENT_REFERENCE,
                        message=(
                            f'approval event "{event.id}" references missing subject event '
                            f'"{event.subject_event}"'
                        ),
                        related_events=[event.id, event.subject_event],
                        remediation=(
                            "Reference an existing event id from the approval subject_event."
                        ),
                    )
                )

    return diagnostics


def _missing_edge_endpoint_diagnostics(edge: Edge, event_counts: Counter[str]) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []

    for field_name, event_id in (
        ("from_event", edge.from_event),
        ("to_event", edge.to_event),
    ):
        if event_counts[event_id] == 0:
            diagnostics.append(
                Diagnostic(
                    code=DiagnosticCode.MISSING_EVENT_REFERENCE,
                    message=(
                        f'edge "{edge.id}" references missing event "{event_id}" in {field_name}'
                    ),
                    related_events=[event_id],
                    related_edges=[edge.id],
                    remediation="Reference only event ids that exist in the trace.",
                )
            )

    return diagnostics


def _missing_tool_arguments_diagnostics(trace: Trace) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []

    for event in trace.events:
        if isinstance(event, ToolCallEvent) and event.arguments is None:
            diagnostics.append(
                Diagnostic(
                    code=DiagnosticCode.TOOL_CALL_MISSING_ARGUMENTS,
                    message=f'tool call "{event.id}" is missing arguments',
                    related_events=[event.id],
                    remediation="Add an arguments object to the tool call event.",
                )
            )

    return diagnostics


class _MatchedToolResults:
    def __init__(self) -> None:
        self.diagnostics: list[Diagnostic] = []
        self.matches: list[tuple[ToolCallEvent, ToolResultEvent]] = []


def _matched_tool_results(
    trace: Trace,
    event_counts: Counter[str],
    unique_events: dict[str, object],
) -> _MatchedToolResults:
    result = _MatchedToolResults()

    for event in trace.events:
        if not isinstance(event, ToolResultEvent):
            continue

        if event.call_id is None:
            result.diagnostics.append(
                _tool_result_without_call(
                    event,
                    "has no call_id",
                    [event.id],
                )
            )
            continue

        if event_counts[event.call_id] == 0:
            result.diagnostics.append(
                _tool_result_without_call(
                    event,
                    f'references missing tool call "{event.call_id}"',
                    [event.id, event.call_id],
                )
            )
            continue

        if event_counts[event.call_id] > 1:
            continue

        call_event = unique_events[event.call_id]

        if not isinstance(call_event, ToolCallEvent):
            result.diagnostics.append(
                _tool_result_without_call(
                    event,
                    f'references non-tool-call event "{event.call_id}"',
                    [event.id, event.call_id],
                )
            )
            continue

        if event.tool_name != call_event.tool_name:
            result.diagnostics.append(
                _tool_result_without_call(
                    event,
                    (f'tool name "{event.tool_name}" does not match call "{event.call_id}"'),
                    [event.id, event.call_id],
                )
            )
            continue

        result.matches.append((call_event, event))

    return result


def _tool_result_without_call(
    event: ToolResultEvent,
    reason: str,
    related_events: list[str],
) -> Diagnostic:
    return Diagnostic(
        code=DiagnosticCode.TOOL_RESULT_WITHOUT_MATCHING_CALL,
        message=f'tool result "{event.id}" {reason}',
        related_events=related_events,
        remediation="Set call_id to the id of the matching prior tool_call event.",
    )


def _invalid_order_diagnostics(
    trace: Trace,
    unique_events: dict[str, object],
    matched_tool_results: list[tuple[ToolCallEvent, ToolResultEvent]],
) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []

    for edge in trace.edges:
        from_event = unique_events.get(edge.from_event)
        to_event = unique_events.get(edge.to_event)

        if from_event is None or to_event is None:
            continue
        if not hasattr(from_event, "sequence") or not hasattr(to_event, "sequence"):
            continue

        if from_event.sequence > to_event.sequence:
            diagnostics.append(
                Diagnostic(
                    code=DiagnosticCode.INVALID_EVENT_ORDER,
                    message=(
                        f'edge "{edge.id}" points backward from event '
                        f'"{edge.from_event}" to "{edge.to_event}"'
                    ),
                    related_events=[edge.from_event, edge.to_event],
                    related_edges=[edge.id],
                    remediation="Ensure structural edges do not point backward in sequence order.",
                )
            )

    for tool_call, tool_result in matched_tool_results:
        if tool_result.sequence <= tool_call.sequence:
            diagnostics.append(
                Diagnostic(
                    code=DiagnosticCode.INVALID_EVENT_ORDER,
                    message=(
                        f'tool result "{tool_result.id}" occurs before or at the same '
                        f'sequence as tool call "{tool_call.id}"'
                    ),
                    related_events=[tool_call.id, tool_result.id],
                    remediation="Ensure each tool_result occurs after its matching tool_call.",
                )
            )

    return diagnostics


def _invalid_evidence_reference_diagnostics(
    trace: Trace,
    event_counts: Counter[str],
) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []

    for event in trace.events:
        if not isinstance(event, FinalAnswerEvent):
            continue

        for claim in event.claims:
            for evidence_id in claim.evidence:
                if event_counts[evidence_id] == 0:
                    diagnostics.append(
                        Diagnostic(
                            code=DiagnosticCode.INVALID_EVIDENCE_REFERENCE,
                            message=(
                                f'claim "{claim.id}" references missing evidence '
                                f'event "{evidence_id}"'
                            ),
                            related_events=[event.id, evidence_id],
                            remediation="Reference existing event ids in claim evidence.",
                        )
                    )

    return diagnostics
