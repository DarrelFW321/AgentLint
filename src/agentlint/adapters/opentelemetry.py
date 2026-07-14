"""OpenTelemetry trace adapter."""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from agentlint.adapters.common import AdapterResult, AdapterWarning
from agentlint.capture import (
    CapabilityCoverage,
    CaptureCapabilities,
    CaptureCompleteness,
    CaptureStatus,
)
from agentlint.ir.v1 import SCHEMA_VERSION, Edge, JsonValue, SourceRef, Trace


class OpenTelemetryImportError(Exception):
    """Raised when an OpenTelemetry trace cannot be imported."""


class OpenTelemetryWarningCode(StrEnum):
    """OpenTelemetry adapter warning codes."""

    SPAN_SKIPPED_MISSING_EVENT_TYPE = "OTEL_SPAN_SKIPPED_MISSING_EVENT_TYPE"
    SPAN_SKIPPED_UNSUPPORTED_EVENT_TYPE = "OTEL_SPAN_SKIPPED_UNSUPPORTED_EVENT_TYPE"
    SPAN_SKIPPED_INVALID_JSON_ATTRIBUTE = "OTEL_SPAN_SKIPPED_INVALID_JSON_ATTRIBUTE"
    SPAN_SKIPPED_MISSING_REQUIRED_FIELD = "OTEL_SPAN_SKIPPED_MISSING_REQUIRED_FIELD"
    EDGE_TARGET_NOT_FOUND = "OTEL_EDGE_TARGET_NOT_FOUND"
    PARTIAL_SEMANTICS = "OTEL_PARTIAL_SEMANTICS"


SUPPORTED_EVENT_TYPES = {
    "user_message",
    "developer_instruction",
    "model_call",
    "tool_call",
    "tool_result",
    "approval",
    "final_answer",
}


@dataclass(frozen=True)
class OTelSpan:
    trace_id: str
    span_id: str
    parent_span_id: str | None
    name: str
    start_time_unix_nano: int | None
    end_time_unix_nano: int | None
    attributes: dict[str, JsonValue]

    @property
    def source_ref(self) -> SourceRef:
        return SourceRef(source="opentelemetry", raw_id=self.span_id)


def import_opentelemetry_file(path: str | Path) -> AdapterResult:
    """Import an OTLP-style JSON trace file into AgentLint IR."""
    input_path = Path(path)
    try:
        raw_text = input_path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise OpenTelemetryImportError(f"OpenTelemetry trace file not found: {input_path}") from exc
    except IsADirectoryError as exc:
        raise OpenTelemetryImportError(
            f"OpenTelemetry trace path is a directory, not a file: {input_path}"
        ) from exc
    except OSError as exc:
        raise OpenTelemetryImportError(
            f"could not read OpenTelemetry trace file {input_path}: {exc}"
        ) from exc

    try:
        raw_data = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        message = (
            f"malformed OpenTelemetry JSON at line {exc.lineno}, column {exc.colno}: {exc.msg}"
        )
        raise OpenTelemetryImportError(message) from exc

    return import_opentelemetry_data(raw_data)


def import_opentelemetry_data(raw_data: Any) -> AdapterResult:
    """Import an OTLP-style JSON object into AgentLint IR."""
    spans = _extract_spans(raw_data)
    if not spans:
        raise OpenTelemetryImportError("OpenTelemetry trace contains no spans")

    warnings: list[AdapterWarning] = []
    ordered_spans = _order_spans(spans)
    span_to_event: dict[str, str] = {}
    imported_spans: list[OTelSpan] = []
    events: list[dict[str, Any]] = []

    for sequence, span in enumerate(ordered_spans):
        event_data = _span_to_event(span, sequence, warnings)
        if event_data is None:
            continue
        span_to_event[span.span_id] = event_data["id"]
        imported_spans.append(span)
        events.append(event_data)

    if not events:
        raise OpenTelemetryImportError(
            "OpenTelemetry trace produced no importable AgentLint events"
        )

    edges = _build_edges(ordered_spans, span_to_event, warnings)
    trace_id = _trace_id(imported_spans[0])
    capture = _capture_completeness(warnings)
    trace_data = {
        "schema_version": SCHEMA_VERSION,
        "trace_id": trace_id,
        "metadata": {
            "adapter": "opentelemetry",
            "source_trace_id": imported_spans[0].trace_id,
        },
        "capture": capture.model_dump(mode="json"),
        "events": events,
        "edges": [edge.model_dump(mode="json") for edge in edges],
    }

    try:
        trace = Trace.model_validate(trace_data)
    except ValidationError as exc:
        raise OpenTelemetryImportError(
            "imported OpenTelemetry trace is not valid AgentLint IR"
        ) from exc

    return AdapterResult(trace=trace, capture=capture, warnings=warnings)


def _capture_completeness(warnings: list[AdapterWarning]) -> CaptureCompleteness:
    reasons = {
        "agent_runs": "Generic spans do not guarantee an agent-run boundary.",
        "model_calls": "Only explicitly typed AgentLint model spans are recognized.",
        "tool_calls": "Only explicitly typed AgentLint tool spans are recognized.",
        "tool_arguments": "Arguments require a valid explicit JSON attribute.",
        "tool_results": "Results require explicitly typed AgentLint result spans.",
        "approvals": "Approvals require explicit AgentLint approval attributes.",
        "data_flow": "Only explicit AgentLint data-flow edges are preserved.",
        "provenance": "Only explicit claims and provenance edges are preserved.",
        "final_answers": "Only explicitly typed final-answer spans are recognized.",
    }
    capabilities = CaptureCapabilities.model_validate(
        {
            name: CapabilityCoverage(status=CaptureStatus.PARTIAL, reason=reason)
            for name, reason in reasons.items()
        }
    )
    notes = sorted({f"Import incident recorded: {warning.code}." for warning in warnings})
    return CaptureCompleteness(
        adapter="opentelemetry",
        framework="opentelemetry",
        capabilities=capabilities,
        notes=notes,
    )


def _extract_spans(raw_data: Any) -> list[OTelSpan]:
    if not isinstance(raw_data, dict):
        raise OpenTelemetryImportError("OpenTelemetry trace must be a JSON object")

    spans: list[OTelSpan] = []
    resource_spans = raw_data.get("resourceSpans", [])
    if not isinstance(resource_spans, list):
        raise OpenTelemetryImportError("resourceSpans must be a list")

    for resource_span in resource_spans:
        if not isinstance(resource_span, dict):
            continue
        scope_spans = resource_span.get("scopeSpans", [])
        if not isinstance(scope_spans, list):
            continue
        for scope_span in scope_spans:
            if not isinstance(scope_span, dict):
                continue
            raw_spans = scope_span.get("spans", [])
            if not isinstance(raw_spans, list):
                continue
            for raw_span in raw_spans:
                if isinstance(raw_span, dict):
                    spans.append(_parse_span(raw_span))

    return spans


def _parse_span(raw_span: dict[str, Any]) -> OTelSpan:
    span_id = _required_string(raw_span, "spanId")
    return OTelSpan(
        trace_id=_required_string(raw_span, "traceId"),
        span_id=span_id,
        parent_span_id=_optional_string(raw_span.get("parentSpanId")),
        name=_optional_string(raw_span.get("name")) or span_id,
        start_time_unix_nano=_optional_int(raw_span.get("startTimeUnixNano")),
        end_time_unix_nano=_optional_int(raw_span.get("endTimeUnixNano")),
        attributes=_decode_attributes(raw_span.get("attributes", [])),
    )


def _required_string(raw_span: dict[str, Any], key: str) -> str:
    value = raw_span.get(key)
    if not isinstance(value, str) or not value:
        raise OpenTelemetryImportError(f"span is missing required string field {key}")
    return value


def _optional_string(value: Any) -> str | None:
    return value if isinstance(value, str) and value else None


def _optional_int(value: Any) -> int | None:
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.isdigit():
        return int(value)
    return None


def _decode_attributes(raw_attributes: Any) -> dict[str, JsonValue]:
    if not isinstance(raw_attributes, list):
        return {}

    decoded: dict[str, JsonValue] = {}
    for item in raw_attributes:
        if not isinstance(item, dict):
            continue
        key = item.get("key")
        if not isinstance(key, str) or not key:
            continue
        decoded[key] = _decode_any_value(item.get("value"))
    return decoded


def _decode_any_value(value: Any) -> JsonValue:
    if not isinstance(value, dict):
        return None
    if "stringValue" in value:
        return value["stringValue"]
    if "intValue" in value:
        raw_int = value["intValue"]
        return int(raw_int) if isinstance(raw_int, str | int) else None
    if "doubleValue" in value:
        raw_float = value["doubleValue"]
        return float(raw_float) if isinstance(raw_float, str | int | float) else None
    if "boolValue" in value:
        raw_bool = value["boolValue"]
        return raw_bool if isinstance(raw_bool, bool) else None
    if "arrayValue" in value:
        values = value["arrayValue"].get("values", [])
        return [_decode_any_value(item) for item in values] if isinstance(values, list) else []
    if "kvlistValue" in value:
        values = value["kvlistValue"].get("values", [])
        result: dict[str, JsonValue] = {}
        if isinstance(values, list):
            for item in values:
                if isinstance(item, dict) and isinstance(item.get("key"), str):
                    result[item["key"]] = _decode_any_value(item.get("value"))
        return result
    return None


def _order_spans(spans: list[OTelSpan]) -> list[OTelSpan]:
    return sorted(
        spans,
        key=lambda span: (
            _attr_int(span, "agentlint.sequence", fallback=10**18),
            span.start_time_unix_nano if span.start_time_unix_nano is not None else 10**18,
            span.span_id,
        ),
    )


def _span_to_event(
    span: OTelSpan,
    fallback_sequence: int,
    warnings: list[AdapterWarning],
) -> dict[str, Any] | None:
    event_type = _attr_string(span, "agentlint.event.type")
    if event_type is None:
        warnings.append(
            _warning(
                OpenTelemetryWarningCode.SPAN_SKIPPED_MISSING_EVENT_TYPE,
                f'span "{span.span_id}" is missing agentlint.event.type',
                span,
            )
        )
        return None
    if event_type not in SUPPORTED_EVENT_TYPES:
        warnings.append(
            _warning(
                OpenTelemetryWarningCode.SPAN_SKIPPED_UNSUPPORTED_EVENT_TYPE,
                f'span "{span.span_id}" has unsupported AgentLint event type "{event_type}"',
                span,
            )
        )
        return None

    event_id = _attr_string(span, "agentlint.event.id") or f"otel_{span.span_id}"
    event: dict[str, Any] = {
        "id": event_id,
        "type": event_type,
        "sequence": _attr_int(span, "agentlint.sequence", fallback=fallback_sequence),
        "metadata": _event_metadata(span),
        "source_ref": span.source_ref.model_dump(mode="json"),
    }

    if span.start_time_unix_nano is not None:
        event["timestamp"] = str(span.start_time_unix_nano)

    if not _populate_event_payload(event, span, warnings):
        return None
    return event


def _populate_event_payload(
    event: dict[str, Any],
    span: OTelSpan,
    warnings: list[AdapterWarning],
) -> bool:
    match event["type"]:
        case "user_message" | "developer_instruction":
            content = _attr_string(span, "agentlint.content")
            if content is None:
                return _missing_required(span, "agentlint.content", warnings)
            event["content"] = content
        case "model_call":
            event["input"] = _json_attr(span, "agentlint.model.input_json", warnings)
            event["output"] = _json_attr(span, "agentlint.model.output_json", warnings)
            model = _attr_string(span, "gen_ai.request.model") or _attr_string(
                span, "agentlint.model.name"
            )
            if model is not None:
                event["model"] = model
        case "tool_call":
            tool_name = _attr_string(span, "agentlint.tool.name")
            if tool_name is None:
                return _missing_required(span, "agentlint.tool.name", warnings)
            event["tool_name"] = tool_name
            arguments = _json_attr(span, "agentlint.tool.arguments_json", warnings)
            if isinstance(arguments, dict):
                event["arguments"] = arguments
        case "tool_result":
            tool_name = _attr_string(span, "agentlint.tool.name")
            if tool_name is None:
                return _missing_required(span, "agentlint.tool.name", warnings)
            event["tool_name"] = tool_name
            call_id = _attr_string(span, "agentlint.tool.call_id")
            if call_id is not None:
                event["call_id"] = call_id
            event["result"] = _json_attr(span, "agentlint.tool.result_json", warnings)
        case "approval":
            decision = _attr_string(span, "agentlint.approval.decision")
            if decision not in {"approved", "denied"}:
                return _missing_required(span, "agentlint.approval.decision", warnings)
            event["decision"] = decision
            subject_event = _attr_string(span, "agentlint.approval.subject_event")
            if subject_event is not None:
                event["subject_event"] = subject_event
            approved_by = _attr_string(span, "agentlint.approval.approved_by")
            if approved_by is not None:
                event["approved_by"] = approved_by
            reason = _attr_string(span, "agentlint.approval.reason")
            if reason is not None:
                event["reason"] = reason
        case "final_answer":
            content = _attr_string(span, "agentlint.content")
            if content is None:
                return _missing_required(span, "agentlint.content", warnings)
            event["content"] = content
            claims = _json_attr(span, "agentlint.claims_json", warnings, default=[])
            event["claims"] = claims if isinstance(claims, list) else []

    return True


def _event_metadata(span: OTelSpan) -> dict[str, JsonValue]:
    metadata: dict[str, JsonValue] = {
        "otel_span_name": span.name,
        "otel_span_id": span.span_id,
    }
    sources = _attr_string_list(span, "agentlint.sources")
    sinks = _attr_string_list(span, "agentlint.sinks")
    if sources:
        metadata["sources"] = sources
        if len(sources) == 1:
            metadata["source"] = sources[0]
    if sinks:
        metadata["sinks"] = sinks
        if len(sinks) == 1:
            metadata["sink"] = sinks[0]
    trust = _attr_string(span, "agentlint.trust")
    if trust is not None:
        metadata["trust"] = trust
    return metadata


def _build_edges(
    spans: list[OTelSpan],
    span_to_event: dict[str, str],
    warnings: list[AdapterWarning],
) -> list[Edge]:
    edges: list[Edge] = []
    edge_ids: set[str] = set()
    event_ids = set(span_to_event.values())

    for span in spans:
        from_event = span_to_event.get(span.span_id)
        if from_event is None:
            continue

        if span.parent_span_id:
            to_event = span_to_event.get(span.parent_span_id)
            if to_event is not None:
                edges.append(_edge("parent", to_event, from_event, span, edge_ids))

        for edge_type, attribute in (
            ("data_flow", "agentlint.data_flow.to"),
            ("approval_for", "agentlint.approval_for.to"),
            ("provenance", "agentlint.provenance.to"),
        ):
            for to_event in _attr_string_list(span, attribute):
                if to_event not in event_ids:
                    warnings.append(
                        _warning(
                            OpenTelemetryWarningCode.EDGE_TARGET_NOT_FOUND,
                            (
                                f'span "{span.span_id}" references missing AgentLint '
                                f'edge target "{to_event}" via {attribute}'
                            ),
                            span,
                        )
                    )
                edges.append(_edge(edge_type, from_event, to_event, span, edge_ids))

    return edges


def _edge(
    edge_type: str,
    from_event: str,
    to_event: str,
    span: OTelSpan,
    edge_ids: set[str],
) -> Edge:
    base_id = f"otel_{edge_type}_{from_event}_{to_event}"
    edge_id = base_id
    suffix = 2
    while edge_id in edge_ids:
        edge_id = f"{base_id}_{suffix}"
        suffix += 1
    edge_ids.add(edge_id)
    return Edge(
        id=edge_id,
        type=edge_type,  # type: ignore[arg-type]
        from_event=from_event,
        to_event=to_event,
        source_ref=span.source_ref,
    )


def _trace_id(span: OTelSpan) -> str:
    configured = _attr_string(span, "agentlint.trace.id")
    return configured or f"otel_{span.trace_id}"


def _attr_string(span: OTelSpan, key: str) -> str | None:
    value = span.attributes.get(key)
    return value if isinstance(value, str) and value else None


def _attr_int(span: OTelSpan, key: str, fallback: int) -> int:
    value = span.attributes.get(key)
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.isdigit():
        return int(value)
    return fallback


def _attr_string_list(span: OTelSpan, key: str) -> list[str]:
    value = span.attributes.get(key)
    if isinstance(value, str) and value:
        return [item.strip() for item in value.split(",") if item.strip()]
    if isinstance(value, list):
        return [item for item in value if isinstance(item, str) and item]
    return []


def _json_attr(
    span: OTelSpan,
    key: str,
    warnings: list[AdapterWarning],
    default: JsonValue = None,
) -> JsonValue:
    value = span.attributes.get(key)
    if value is None:
        return default
    if not isinstance(value, str):
        return value
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        warnings.append(
            _warning(
                OpenTelemetryWarningCode.SPAN_SKIPPED_INVALID_JSON_ATTRIBUTE,
                f'span "{span.span_id}" has invalid JSON in {key}',
                span,
            )
        )
        return default


def _missing_required(
    span: OTelSpan,
    field: str,
    warnings: list[AdapterWarning],
) -> bool:
    warnings.append(
        _warning(
            OpenTelemetryWarningCode.SPAN_SKIPPED_MISSING_REQUIRED_FIELD,
            f'span "{span.span_id}" is missing required field {field}',
            span,
        )
    )
    return False


def _warning(
    code: OpenTelemetryWarningCode,
    message: str,
    span: OTelSpan,
) -> AdapterWarning:
    return AdapterWarning(code=code.value, message=message, source_ref=span.source_ref)
