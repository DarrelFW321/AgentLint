"""Normalize OpenAI Agents SDK snapshots into AgentLint IR."""

from __future__ import annotations

import json
from enum import StrEnum
from pathlib import Path
from typing import Any

from agentlint.adapters.common import AdapterResult, AdapterWarning
from agentlint.adapters.openai_snapshot import (
    OpenAISpanSnapshot,
    OpenAITraceSnapshot,
    load_openai_snapshot,
)
from agentlint.capture import (
    CapabilityCoverage,
    CaptureCapabilities,
    CaptureCompleteness,
    CaptureStatus,
)
from agentlint.ir.v1 import SCHEMA_VERSION, Edge, SourceRef, Trace


class OpenAIAgentsWarningCode(StrEnum):
    """Stable warnings emitted by the OpenAI Agents adapter."""

    UNSUPPORTED_SPAN = "OPENAI_AGENTS_UNSUPPORTED_SPAN"
    INVALID_FUNCTION_INPUT = "OPENAI_AGENTS_INVALID_FUNCTION_INPUT"
    MISSING_PARENT = "OPENAI_AGENTS_MISSING_PARENT"
    INCOMPLETE_SPAN = "OPENAI_AGENTS_INCOMPLETE_SPAN"


def import_openai_agents_file(path: str | Path) -> AdapterResult:
    """Import a recorded OpenAI Agents snapshot file."""
    return import_openai_agents_snapshot(load_openai_snapshot(path))


def import_openai_agents_snapshot(snapshot: OpenAITraceSnapshot) -> AdapterResult:
    """Normalize one strict OpenAI Agents snapshot."""
    warnings: list[AdapterWarning] = []
    events: list[dict[str, Any]] = []
    primary_events: dict[str, str] = {}
    span_event_ids: dict[str, list[str]] = {}
    ordered_spans = _ordered_spans(snapshot.spans)

    sequence = 0
    for span in ordered_spans:
        mapped = _map_span(span, sequence, warnings)
        if not mapped:
            continue
        events.extend(mapped)
        event_ids = [event["id"] for event in mapped]
        span_event_ids[span.span_id] = event_ids
        primary_events[span.span_id] = event_ids[0]
        sequence += len(mapped)

    _resolve_semantic_references(events, snapshot.spans, primary_events, warnings)
    edges = _parent_edges(ordered_spans, primary_events, span_event_ids, warnings)
    edges.extend(_semantic_data_flow_edges(snapshot.spans, events, primary_events, warnings))
    capture = _capture_profile(snapshot, warnings)
    trace = Trace.model_validate(
        {
            "schema_version": SCHEMA_VERSION,
            "trace_id": snapshot.trace_id,
            "metadata": {
                "adapter": "openai_agents",
                "workflow_name": snapshot.workflow_name,
                **({"group_id": snapshot.group_id} if snapshot.group_id else {}),
            },
            "capture": capture.model_dump(mode="json"),
            "events": events,
            "edges": [edge.model_dump(mode="json") for edge in edges],
        }
    )
    return AdapterResult(trace=trace, capture=capture, warnings=warnings)


def _ordered_spans(spans: list[OpenAISpanSnapshot]) -> list[OpenAISpanSnapshot]:
    by_id = {span.span_id: span for span in spans}
    approvals = [span for span in spans if span.span_type == "agentlint_approval"]
    finals = [span for span in spans if span.span_type == "agentlint_final_answer"]
    sinks = [span for span in spans if span.span_type == "agentlint_sink"]
    ordinary = [
        span for span in spans if span not in approvals and span not in finals and span not in sinks
    ]
    ordered: list[OpenAISpanSnapshot] = []
    visited: set[str] = set()

    def visit(span: OpenAISpanSnapshot) -> None:
        if span.span_id in visited:
            return
        if span.parent_id and span.parent_id in by_id:
            visit(by_id[span.parent_id])
        visited.add(span.span_id)
        ordered.append(span)

    for span in sorted(ordinary, key=lambda item: (item.started_at or "", item.span_id)):
        visit(span)

    for approval in sorted(approvals, key=lambda item: item.span_id):
        subject = _string(approval.span_data.get("subject_event")) or ""
        subject_span_id = subject.removesuffix(":call")
        insertion = next(
            (index for index, span in enumerate(ordered) if span.span_id == subject_span_id),
            len(ordered),
        )
        ordered.insert(insertion, approval)

    ordered.extend(sorted(finals, key=lambda item: item.span_id))
    ordered.extend(sorted(sinks, key=lambda item: item.span_id))
    return ordered


def _map_span(
    span: OpenAISpanSnapshot,
    sequence: int,
    warnings: list[AdapterWarning],
) -> list[dict[str, Any]]:
    data = span.span_data
    common = {
        "sequence": sequence,
        "timestamp": span.started_at,
        "metadata": {"has_error": span.has_error} if span.has_error else {},
        "source_ref": _source_ref(span).model_dump(mode="json"),
    }
    match span.span_type:
        case "agent":
            name = _string(data.get("name")) or "unknown_agent"
            return [{"id": span.span_id, "type": "agent_run", "agent_name": name, **common}]
        case "generation":
            return [
                {
                    "id": span.span_id,
                    "type": "model_call",
                    "input": data.get("input"),
                    "output": data.get("output"),
                    "model": _string(data.get("model")),
                    **common,
                }
            ]
        case "response":
            response_id = _string(data.get("response_id"))
            metadata = dict(common["metadata"])
            if response_id is not None:
                metadata["openai_response_id"] = response_id
            return [
                {
                    "id": span.span_id,
                    "type": "model_call",
                    "input": None,
                    "output": None,
                    **{**common, "metadata": metadata},
                }
            ]
        case "function":
            return _map_function(span, common, warnings)
        case "handoff":
            return [
                {
                    "id": span.span_id,
                    "type": "handoff",
                    "from_agent": _string(data.get("from_agent")),
                    "to_agent": _string(data.get("to_agent")),
                    **common,
                }
            ]
        case "guardrail":
            return [
                {
                    "id": span.span_id,
                    "type": "guardrail",
                    "guardrail_name": _string(data.get("name")) or "unknown_guardrail",
                    "triggered": data.get("triggered") is True,
                    **common,
                }
            ]
        case "agentlint_final_answer":
            content = _string(data.get("content"))
            if content is None:
                return []
            return [
                {
                    "id": span.span_id,
                    "type": "final_answer",
                    "content": content,
                    "claims": [],
                    **common,
                }
            ]
        case "agentlint_approval":
            decision = _string(data.get("decision"))
            if decision not in {"approved", "denied"}:
                return []
            subject = _string(data.get("subject_event"))
            return [
                {
                    "id": span.span_id,
                    "type": "approval",
                    "decision": decision,
                    "subject_event": subject,
                    **common,
                }
            ]
        case "agentlint_source":
            name = _string(data.get("name"))
            if name is None:
                warnings.append(
                    _warning(
                        OpenAIAgentsWarningCode.INCOMPLETE_SPAN,
                        "semantic source record did not contain a name",
                        span,
                    )
                )
                return []
            metadata: dict[str, Any] = {"source": name}
            for key in ("sensitivity", "trust"):
                value = _string(data.get(key))
                if value is not None:
                    metadata[f"declared_{key}"] = value
            return [
                {
                    "id": span.span_id,
                    "type": "user_message",
                    "content": "[AgentLint semantic source]",
                    **{**common, "metadata": metadata},
                }
            ]
        case "agentlint_sink":
            return []
        case "custom" if _is_transparent_container(span):
            return []
        case _:
            warnings.append(
                _warning(
                    OpenAIAgentsWarningCode.UNSUPPORTED_SPAN,
                    f'unsupported OpenAI Agents span type "{span.span_type}"',
                    span,
                )
            )
            return []


def _map_function(
    span: OpenAISpanSnapshot,
    common: dict[str, Any],
    warnings: list[AdapterWarning],
) -> list[dict[str, Any]]:
    name = _string(span.span_data.get("name")) or "unknown_function"
    arguments: dict[str, Any] = {}
    raw_input = span.span_data.get("input")
    if isinstance(raw_input, dict):
        arguments = raw_input
    elif isinstance(raw_input, str) and raw_input:
        try:
            decoded = json.loads(raw_input)
            if isinstance(decoded, dict):
                arguments = decoded
            else:
                raise ValueError
        except (json.JSONDecodeError, ValueError):
            warnings.append(
                _warning(
                    OpenAIAgentsWarningCode.INVALID_FUNCTION_INPUT,
                    "function span input was not a JSON object",
                    span,
                )
            )

    call_id = f"{span.span_id}:call"
    call = {
        "id": call_id,
        "type": "tool_call",
        "tool_name": name,
        "arguments": arguments,
        **common,
    }
    output = span.span_data.get("output")
    if output is None:
        warnings.append(
            _warning(
                OpenAIAgentsWarningCode.INCOMPLETE_SPAN,
                "function span did not contain an output",
                span,
            )
        )
        return [call]

    result = {
        "id": f"{span.span_id}:result",
        "type": "tool_result",
        "tool_name": name,
        "call_id": call_id,
        "result": output,
        **{**common, "sequence": common["sequence"] + 1, "timestamp": span.ended_at},
    }
    return [call, result]


def _parent_edges(
    spans: list[OpenAISpanSnapshot],
    primary_events: dict[str, str],
    span_event_ids: dict[str, list[str]],
    warnings: list[AdapterWarning],
) -> list[Edge]:
    edges: list[Edge] = []
    spans_by_id = {span.span_id: span for span in spans}
    for span in spans:
        event_ids = span_event_ids.get(span.span_id)
        if not event_ids:
            continue
        if span.parent_id:
            parent_event = _nearest_supported_parent(
                span.parent_id,
                spans_by_id,
                primary_events,
            )
            if parent_event is None:
                direct_parent = spans_by_id.get(span.parent_id)
                if direct_parent is None or not _is_transparent_container(direct_parent):
                    warnings.append(
                        _warning(
                            OpenAIAgentsWarningCode.MISSING_PARENT,
                            "span parent was not captured as a supported event",
                            span,
                        )
                    )
            else:
                edges.append(_edge(parent_event, event_ids[0], span, "parent"))
        if len(event_ids) == 2:
            edges.append(_edge(event_ids[0], event_ids[1], span, "parent"))
    return edges


def _resolve_semantic_references(
    events: list[dict[str, Any]],
    spans: list[OpenAISpanSnapshot],
    primary_events: dict[str, str],
    warnings: list[AdapterWarning],
) -> None:
    functions = {span.span_id for span in spans if span.span_type == "function"}
    event_ids = {event["id"] for event in events}
    for event in events:
        if event["type"] != "approval":
            continue
        subject = event.get("subject_event")
        if subject in functions:
            event["subject_event"] = f"{subject}:call"
        elif subject in primary_events:
            event["subject_event"] = primary_events[subject]
        if event.get("subject_event") not in event_ids:
            span = next((item for item in spans if item.span_id == event["id"]), None)
            if span is not None:
                warnings.append(
                    _warning(
                        OpenAIAgentsWarningCode.INCOMPLETE_SPAN,
                        "approval record did not reference a captured event",
                        span,
                    )
                )


def _semantic_data_flow_edges(
    spans: list[OpenAISpanSnapshot],
    events: list[dict[str, Any]],
    primary_events: dict[str, str],
    warnings: list[AdapterWarning],
) -> list[Edge]:
    events_by_id = {event["id"]: event for event in events}
    edges: list[Edge] = []
    for span in spans:
        if span.span_type != "agentlint_sink":
            continue
        name = _string(span.span_data.get("name"))
        target = _string(span.span_data.get("target_event"))
        raw_sources = span.span_data.get("source_events")
        sources = raw_sources if isinstance(raw_sources, list) else []
        target_id = primary_events.get(target or "", target)
        if target_id in primary_events.values() and target in {
            item.span_id for item in spans if item.span_type == "function"
        }:
            target_id = f"{target}:call"
        if name is None or target_id not in events_by_id or not sources:
            warnings.append(
                _warning(
                    OpenAIAgentsWarningCode.INCOMPLETE_SPAN,
                    "semantic sink record had incomplete event references",
                    span,
                )
            )
            continue
        events_by_id[target_id].setdefault("metadata", {})["sink"] = name
        visibility = _string(span.span_data.get("visibility"))
        if visibility is not None:
            events_by_id[target_id]["metadata"]["declared_visibility"] = visibility
        for index, source in enumerate(sources):
            if not isinstance(source, str) or source not in events_by_id:
                warnings.append(
                    _warning(
                        OpenAIAgentsWarningCode.INCOMPLETE_SPAN,
                        "semantic sink source did not reference a captured event",
                        span,
                    )
                )
                continue
            edges.append(
                Edge(
                    id=f"openai_data_flow_{span.span_id}_{index}",
                    type="data_flow",
                    from_event=source,
                    to_event=target_id,
                    source_ref=_source_ref(span),
                )
            )
    return edges


def _nearest_supported_parent(
    parent_id: str,
    spans_by_id: dict[str, OpenAISpanSnapshot],
    primary_events: dict[str, str],
) -> str | None:
    visited: set[str] = set()
    current_id: str | None = parent_id
    while current_id is not None and current_id not in visited:
        visited.add(current_id)
        event_id = primary_events.get(current_id)
        if event_id is not None:
            return event_id
        span = spans_by_id.get(current_id)
        if span is None or not _is_transparent_container(span):
            return None
        current_id = span.parent_id
    return None


def _edge(from_event: str, to_event: str, span: OpenAISpanSnapshot, edge_type: str) -> Edge:
    return Edge(
        id=f"openai_{edge_type}_{from_event}_{to_event}",
        type=edge_type,  # type: ignore[arg-type]
        from_event=from_event,
        to_event=to_event,
        source_ref=_source_ref(span),
    )


def _capture_profile(
    snapshot: OpenAITraceSnapshot, warnings: list[AdapterWarning]
) -> CaptureCompleteness:
    status = CaptureStatus
    span_types = {span.span_type for span in snapshot.spans}
    values = {
        "agent_runs": CapabilityCoverage(status=status.CAPTURED),
        "model_calls": CapabilityCoverage(status=status.CAPTURED),
        "tool_calls": CapabilityCoverage(
            status=status.PARTIAL,
            reason="Function tools are captured; other tool families may not be represented.",
        ),
        "tool_arguments": CapabilityCoverage(
            status=status.PARTIAL,
            reason="Arguments depend on SDK sensitive-data capture and valid JSON input.",
        ),
        "tool_results": CapabilityCoverage(
            status=status.PARTIAL,
            reason="Results depend on supported completed function spans.",
        ),
        "approvals": CapabilityCoverage(
            status=(status.PARTIAL if "agentlint_approval" in span_types else status.UNAVAILABLE),
            reason=(
                "Explicitly recorded approval decisions were captured."
                if "agentlint_approval" in span_types
                else "General approval decisions are not exposed by tracing spans."
            ),
        ),
        "data_flow": CapabilityCoverage(
            status=(status.PARTIAL if "agentlint_sink" in span_types else status.UNAVAILABLE),
            reason=(
                "Explicitly declared source-to-sink relationships were captured."
                if "agentlint_sink" in span_types
                else "Span parentage is not value-level data flow."
            ),
        ),
        "provenance": CapabilityCoverage(
            status=status.UNAVAILABLE,
            reason="SDK tracing does not provide claim-evidence semantics.",
        ),
        "final_answers": CapabilityCoverage(
            status=(
                status.PARTIAL if "agentlint_final_answer" in span_types else status.UNAVAILABLE
            ),
            reason=(
                "An explicit run result was recorded for this trace."
                if "agentlint_final_answer" in span_types
                else "Tracing spans do not expose authoritative RunResult final output."
            ),
        ),
    }
    notes = sorted(
        {f"Capture incident recorded: {code}." for code in snapshot.capture_incidents}
        | {f"Import incident recorded: {warning.code}." for warning in warnings}
    )
    return CaptureCompleteness(
        adapter="openai_agents",
        framework="openai_agents",
        framework_version=snapshot.sdk_version,
        capabilities=CaptureCapabilities.model_validate(values),
        notes=notes[:20],
    )


def _source_ref(span: OpenAISpanSnapshot) -> SourceRef:
    return SourceRef(source="openai_agents", raw_id=span.span_id)


def _warning(
    code: OpenAIAgentsWarningCode, message: str, span: OpenAISpanSnapshot
) -> AdapterWarning:
    return AdapterWarning(code=code.value, message=message, source_ref=_source_ref(span))


def _string(value: Any) -> str | None:
    return value if isinstance(value, str) and value else None


def _is_transparent_container(span: OpenAISpanSnapshot) -> bool:
    return span.span_type == "custom" and _string(span.span_data.get("name")) in {
        "task",
        "turn",
    }
