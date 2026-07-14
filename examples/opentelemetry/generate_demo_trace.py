"""Generate a deterministic OpenTelemetry demo trace for AgentLint.

This script makes no network calls and does not require the OpenTelemetry SDK.
It writes the small OTLP-style JSON subset supported by AgentLint's M7 adapter.
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "examples" / "external" / "opentelemetry" / "demo_missing_approval.json"


def attr(key: str, value: str | int) -> dict:
    if isinstance(value, int):
        return {"key": key, "value": {"intValue": str(value)}}
    return {"key": key, "value": {"stringValue": value}}


def main() -> None:
    trace = {
        "resourceSpans": [
            {
                "scopeSpans": [
                    {
                        "spans": [
                            {
                                "traceId": "77777777777777777777777777777777",
                                "spanId": "0000000000000001",
                                "name": "tool.call send_email",
                                "startTimeUnixNano": "100",
                                "endTimeUnixNano": "200",
                                "attributes": [
                                    attr("agentlint.trace.id", "otel_demo_missing_approval"),
                                    attr("agentlint.event.type", "tool_call"),
                                    attr("agentlint.event.id", "evt_send_email"),
                                    attr("agentlint.sequence", 0),
                                    attr("agentlint.tool.name", "send_email"),
                                    attr(
                                        "agentlint.tool.arguments_json",
                                        json.dumps(
                                            {
                                                "recipient": "customer@example.com",
                                                "body": "Your case has been updated.",
                                            },
                                            separators=(",", ":"),
                                        ),
                                    ),
                                ],
                            }
                        ]
                    }
                ]
            }
        ]
    }

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(trace, indent=2), encoding="utf-8")
    print(OUTPUT)


if __name__ == "__main__":
    main()
