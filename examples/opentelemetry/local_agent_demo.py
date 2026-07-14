"""Run a deterministic local agent with OpenTelemetry SDK spans.

This demo has an agent-shaped control loop but no model/API calls:

1. The agent receives a user prompt.
2. A deterministic planner chooses tool actions.
3. Local Python tools execute.
4. The agent emits a final answer.

Each agent step emits real OpenTelemetry SDK spans with `agentlint.*`
attributes. The exported JSON can be imported by AgentLint.
"""

from __future__ import annotations

import json
import sys
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
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
OUTPUT = ROOT / "examples" / "external" / "opentelemetry" / "local_agent_demo.json"


@dataclass(frozen=True)
class ToolAction:
    id: str
    name: str
    arguments: dict[str, Any]


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


class LocalAgent:
    """Small deterministic agent loop for instrumentation demos."""

    def __init__(self, tracer, tools: dict[str, Callable[..., Any]]) -> None:
        self.tracer = tracer
        self.tools = tools

    def run(self, prompt: str) -> str:
        with self.tracer.start_as_current_span("agent.run support_update") as run_span:
            set_user_message(run_span, prompt)
            actions = self.plan(prompt)
            results: dict[str, Any] = {}

            for action_index, action in enumerate(actions, start=1):
                call_sequence = action_index * 2 - 1
                result_sequence = action_index * 2
                with self.tracer.start_as_current_span(f"tool.call {action.name}") as call_span:
                    set_tool_call(call_span, action, call_sequence)
                    results[action.id] = self.tools[action.name](**action.arguments)

                with self.tracer.start_as_current_span(f"tool.result {action.name}") as result_span:
                    set_tool_result(result_span, action, results[action.id], result_sequence)

            final_answer = "I checked the account and sent the customer an update."
            with self.tracer.start_as_current_span("agent.final_answer") as final_span:
                set_final_answer(final_span, final_answer)
            return final_answer

    def plan(self, prompt: str) -> list[ToolAction]:
        if "email" not in prompt.lower():
            return []
        return [
            ToolAction(
                id="evt_lookup_account",
                name="lookup_account",
                arguments={"account_id": "acct_123"},
            ),
            ToolAction(
                id="evt_web_search",
                name="web_search",
                arguments={"query": "customer profile details"},
            ),
            ToolAction(
                id="evt_send_email",
                name="send_email",
                arguments={
                    "recipient": "customer@example.com",
                    "body": "Your account is active.",
                },
            ),
        ]


def lookup_account(account_id: str) -> dict[str, str]:
    return {
        "account_id": account_id,
        "email": "customer@example.com",
        "status": "active",
        "private_note": "Customer profile details.",
    }


def web_search(query: str) -> dict[str, str]:
    return {"query": query, "result": "Public search completed."}


def send_email(recipient: str, body: str) -> dict[str, str]:
    return {"recipient": recipient, "status": "sent", "body": body}


def main() -> None:
    exporter = CapturingSpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    trace.set_tracer_provider(provider)
    tracer = trace.get_tracer("agentlint.demo.local_agent")

    agent = LocalAgent(
        tracer,
        tools={
            "lookup_account": lookup_account,
            "web_search": web_search,
            "send_email": send_email,
        },
    )
    final_answer = agent.run("Please check account acct_123 and email the customer an update.")
    provider.shutdown()

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(to_otlp_json(exporter.spans), indent=2), encoding="utf-8")

    generated = "examples/generated/local_agent_demo.agentlint.json"
    print(f"final answer: {final_answer}")
    print(OUTPUT)
    print()
    print("Next:")
    print(
        "  agentlint import opentelemetry "
        f"{OUTPUT.relative_to(ROOT).as_posix()} --output {generated}"
    )
    print(f"  agentlint check {generated} --policy examples/policies/policy_checks.yaml")


def set_user_message(span, prompt: str) -> None:
    span.set_attribute("agentlint.trace.id", "otel_local_agent_demo")
    span.set_attribute("agentlint.event.type", "user_message")
    span.set_attribute("agentlint.event.id", "evt_user_request")
    span.set_attribute("agentlint.sequence", 0)
    span.set_attribute("agentlint.content", prompt)


def set_tool_call(span, action: ToolAction, sequence: int) -> None:
    span.set_attribute("agentlint.trace.id", "otel_local_agent_demo")
    span.set_attribute("agentlint.event.type", "tool_call")
    span.set_attribute("agentlint.event.id", action.id)
    span.set_attribute("agentlint.sequence", sequence)
    span.set_attribute("agentlint.tool.name", action.name)
    span.set_attribute("agentlint.tool.arguments_json", json_compact(action.arguments))

    if action.name == "web_search":
        span.set_attribute("agentlint.sinks", ["web_search.query"])


def set_tool_result(span, action: ToolAction, result: Any, sequence: int) -> None:
    event_id = action.id.replace("evt_", "evt_result_", 1)
    span.set_attribute("agentlint.trace.id", "otel_local_agent_demo")
    span.set_attribute("agentlint.event.type", "tool_result")
    span.set_attribute("agentlint.event.id", event_id)
    span.set_attribute("agentlint.sequence", sequence)
    span.set_attribute("agentlint.tool.name", action.name)
    span.set_attribute("agentlint.tool.call_id", action.id)
    span.set_attribute("agentlint.tool.result_json", json_compact(result))

    if action.name == "lookup_account":
        span.set_attribute("agentlint.sources", ["customer_profile"])
        span.set_attribute("agentlint.data_flow.to", ["evt_web_search", "evt_final"])
        span.set_attribute("agentlint.provenance.to", ["evt_final"])


def set_final_answer(span, content: str) -> None:
    span.set_attribute("agentlint.trace.id", "otel_local_agent_demo")
    span.set_attribute("agentlint.event.type", "final_answer")
    span.set_attribute("agentlint.event.id", "evt_final")
    span.set_attribute("agentlint.sequence", 20)
    span.set_attribute("agentlint.content", content)
    span.set_attribute(
        "agentlint.claims_json",
        json_compact(
            [
                {
                    "id": "claim_account_active",
                    "text": "The account is active.",
                    "evidence": ["evt_result_lookup_account"],
                }
            ]
        ),
    )


def json_compact(value: Any) -> str:
    return json.dumps(value, separators=(",", ":"))


def to_otlp_json(spans: Iterable[ReadableSpan]) -> dict[str, Any]:
    return {
        "resourceSpans": [
            {
                "resource": {"attributes": []},
                "scopeSpans": [
                    {
                        "scope": {"name": "agentlint.demo.local_agent"},
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
