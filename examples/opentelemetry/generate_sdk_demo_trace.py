"""Generate an OpenTelemetry SDK trace for AgentLint.

This script uses the real OpenTelemetry SDK to create spans, then exports those
finished spans into the small OTLP-style JSON subset supported by AgentLint.
It makes no network calls and does not require an OpenTelemetry Collector.
"""

from __future__ import annotations

import json
import sys
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Any

try:
    from opentelemetry import trace
    from opentelemetry.sdk.trace import ReadableSpan, TracerProvider
    from opentelemetry.sdk.trace.export import (
        SimpleSpanProcessor,
        SpanExporter,
        SpanExportResult,
    )
except ModuleNotFoundError:  # pragma: no cover - exercised by users without the optional extra.
    print(
        "error: opentelemetry-sdk is required for this demo. "
        "Install it with `pip install opentelemetry-sdk` or "
        "`pip install -e .[otel-demo]`.",
        file=sys.stderr,
    )
    raise SystemExit(1) from None


ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "examples" / "external" / "opentelemetry" / "sdk_demo_missing_approval.json"


class CapturingSpanExporter(SpanExporter):
    """In-memory exporter for deterministic local demo output."""

    def __init__(self) -> None:
        self.spans: list[ReadableSpan] = []

    def export(self, spans: Sequence[ReadableSpan]) -> SpanExportResult:
        self.spans.extend(spans)
        return SpanExportResult.SUCCESS

    def shutdown(self) -> None:
        return None

    def force_flush(self, timeout_millis: int = 30000) -> bool:
        return True


def main() -> None:
    exporter = CapturingSpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    trace.set_tracer_provider(provider)
    tracer = trace.get_tracer("agentlint.demo.opentelemetry")

    with tracer.start_as_current_span("user.message request") as user_span:
        user_span.set_attribute("agentlint.trace.id", "otel_sdk_demo_missing_approval")
        user_span.set_attribute("agentlint.event.type", "user_message")
        user_span.set_attribute("agentlint.event.id", "evt_user_request")
        user_span.set_attribute("agentlint.sequence", 0)
        user_span.set_attribute("agentlint.content", "Please email the customer an update.")

        with tracer.start_as_current_span("tool.call send_email") as tool_span:
            tool_span.set_attribute("agentlint.trace.id", "otel_sdk_demo_missing_approval")
            tool_span.set_attribute("agentlint.event.type", "tool_call")
            tool_span.set_attribute("agentlint.event.id", "evt_send_email")
            tool_span.set_attribute("agentlint.sequence", 1)
            tool_span.set_attribute("agentlint.tool.name", "send_email")
            tool_span.set_attribute(
                "agentlint.tool.arguments_json",
                json.dumps(
                    {
                        "recipient": "customer@example.com",
                        "body": "Your case has been updated.",
                    },
                    separators=(",", ":"),
                ),
            )

    provider.shutdown()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(to_otlp_json(exporter.spans), indent=2), encoding="utf-8")
    print(OUTPUT)


def to_otlp_json(spans: Iterable[ReadableSpan]) -> dict[str, Any]:
    return {
        "resourceSpans": [
            {
                "resource": {"attributes": []},
                "scopeSpans": [
                    {
                        "scope": {"name": "agentlint.demo.opentelemetry"},
                        "spans": [span_to_otlp(span) for span in spans],
                    }
                ],
            }
        ]
    }


def span_to_otlp(span: ReadableSpan) -> dict[str, Any]:
    context = span.get_span_context()
    raw_span: dict[str, Any] = {
        "traceId": f"{context.trace_id:032x}",
        "spanId": f"{context.span_id:016x}",
        "name": span.name,
        "startTimeUnixNano": str(span.start_time),
        "endTimeUnixNano": str(span.end_time),
        "attributes": [
            {"key": key, "value": any_value(value)}
            for key, value in sorted((span.attributes or {}).items())
        ],
    }

    if span.parent is not None and span.parent.span_id:
        raw_span["parentSpanId"] = f"{span.parent.span_id:016x}"

    return raw_span


def any_value(value: Any) -> dict[str, Any]:
    if isinstance(value, bool):
        return {"boolValue": value}
    if isinstance(value, int):
        return {"intValue": str(value)}
    if isinstance(value, float):
        return {"doubleValue": value}
    if isinstance(value, str):
        return {"stringValue": value}
    if isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
        return {"arrayValue": {"values": [any_value(item) for item in value]}}
    return {"stringValue": str(value)}


if __name__ == "__main__":
    main()
