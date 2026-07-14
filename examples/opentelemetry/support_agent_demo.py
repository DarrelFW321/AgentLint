"""Run a local support-agent workflow with OpenTelemetry SDK spans.

The workflow is intentionally small and deterministic:

1. A user asks for an account update.
2. The agent looks up a private customer profile.
3. The agent sends private profile details to public web search.
4. The agent sends an email without approval.
5. The agent produces a final answer influenced by the private profile.

The script exports finished SDK spans into the OTLP-style JSON subset supported
by AgentLint's OpenTelemetry importer. It makes no network calls.
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
OUTPUT = ROOT / "examples" / "external" / "opentelemetry" / "support_agent_demo.json"


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
    tracer = trace.get_tracer("agentlint.demo.support_agent")

    run_support_workflow(tracer)
    provider.shutdown()

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(to_otlp_json(exporter.spans), indent=2), encoding="utf-8")

    generated = "examples/generated/support_agent_demo.agentlint.json"
    print(OUTPUT)
    print()
    print("Next:")
    print(
        "  agentlint import opentelemetry "
        f"{OUTPUT.relative_to(ROOT).as_posix()} --output {generated}"
    )
    print(f"  agentlint check {generated} --policy examples/policies/policy_checks.yaml")


def run_support_workflow(tracer) -> None:
    with tracer.start_as_current_span("support_agent.run") as run_span:
        set_event(
            run_span,
            event_type="user_message",
            event_id="evt_user_request",
            sequence=0,
            content="Please check account acct_123 and email the customer an update.",
        )

        with tracer.start_as_current_span("tool.call lookup_account") as lookup_call:
            set_event(
                lookup_call,
                event_type="tool_call",
                event_id="evt_lookup_account",
                sequence=1,
                tool_name="lookup_account",
                arguments={"account_id": "acct_123"},
            )

            with tracer.start_as_current_span("tool.result lookup_account") as lookup_result:
                set_event(
                    lookup_result,
                    event_type="tool_result",
                    event_id="evt_lookup_result",
                    sequence=2,
                    tool_name="lookup_account",
                    call_id="evt_lookup_account",
                    result={
                        "account_id": "acct_123",
                        "email": "customer@example.com",
                        "status": "active",
                        "private_note": "Customer profile details.",
                    },
                    sources=["customer_profile"],
                    data_flow_to=[
                        "evt_web_search",
                        "evt_send_email",
                        "evt_final",
                    ],
                    provenance_to=["evt_final"],
                )

        with tracer.start_as_current_span("tool.call web_search") as web_search:
            set_event(
                web_search,
                event_type="tool_call",
                event_id="evt_web_search",
                sequence=3,
                tool_name="web_search",
                arguments={"query": "customer profile details"},
                sinks=["web_search.query"],
            )

        with tracer.start_as_current_span("tool.call send_email") as send_email:
            set_event(
                send_email,
                event_type="tool_call",
                event_id="evt_send_email",
                sequence=4,
                tool_name="send_email",
                arguments={
                    "recipient": "customer@example.com",
                    "body": "Your account is active.",
                },
            )

        with tracer.start_as_current_span("final_answer") as final_answer:
            set_event(
                final_answer,
                event_type="final_answer",
                event_id="evt_final",
                sequence=5,
                content="I checked the account and sent the customer an update.",
                claims=[
                    {
                        "id": "claim_account_checked",
                        "text": "The account is active.",
                        "evidence": ["evt_lookup_result"],
                    }
                ],
            )


def set_event(
    span,
    *,
    event_type: str,
    event_id: str,
    sequence: int,
    content: str | None = None,
    tool_name: str | None = None,
    call_id: str | None = None,
    arguments: dict[str, Any] | None = None,
    result: Any = None,
    claims: list[dict[str, Any]] | None = None,
    sources: list[str] | None = None,
    sinks: list[str] | None = None,
    data_flow_to: list[str] | None = None,
    provenance_to: list[str] | None = None,
) -> None:
    span.set_attribute("agentlint.trace.id", "otel_support_agent_demo")
    span.set_attribute("agentlint.event.type", event_type)
    span.set_attribute("agentlint.event.id", event_id)
    span.set_attribute("agentlint.sequence", sequence)

    if content is not None:
        span.set_attribute("agentlint.content", content)
    if tool_name is not None:
        span.set_attribute("agentlint.tool.name", tool_name)
    if call_id is not None:
        span.set_attribute("agentlint.tool.call_id", call_id)
    if arguments is not None:
        span.set_attribute("agentlint.tool.arguments_json", json_compact(arguments))
    if result is not None:
        span.set_attribute("agentlint.tool.result_json", json_compact(result))
    if claims is not None:
        span.set_attribute("agentlint.claims_json", json_compact(claims))
    if sources:
        span.set_attribute("agentlint.sources", sources)
    if sinks:
        span.set_attribute("agentlint.sinks", sinks)
    if data_flow_to:
        span.set_attribute("agentlint.data_flow.to", data_flow_to)
    if provenance_to:
        span.set_attribute("agentlint.provenance.to", provenance_to)


def json_compact(value: Any) -> str:
    return json.dumps(value, separators=(",", ":"))


def to_otlp_json(spans: Iterable[ReadableSpan]) -> dict[str, Any]:
    return {
        "resourceSpans": [
            {
                "resource": {"attributes": []},
                "scopeSpans": [
                    {
                        "scope": {"name": "agentlint.demo.support_agent"},
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
