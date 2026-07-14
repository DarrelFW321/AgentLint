# Milestone 7 Build Report

Status: implemented.

Milestone 7 implemented the first external adapter: OpenTelemetry OTLP-style JSON import with explicit AgentLint semantic attributes. The adapter normalizes supported OTel spans into native AgentLint IR v1 so existing validation, policy checks, and reports run unchanged.

## Implemented

1. Added shared adapter result and warning models.
2. Added `agentlint.adapters.opentelemetry`.
3. Parsed the supported OTLP-style JSON trace subset.
4. Decoded OpenTelemetry attribute arrays and scalar/list values.
5. Mapped OTel spans to all current AgentLint event types.
6. Mapped parent span IDs to `parent` edges.
7. Mapped explicit `agentlint.data_flow.to`, `agentlint.approval_for.to`, and `agentlint.provenance.to` attributes to semantic edges.
8. Added adapter warnings for missing event types, unsupported event types, invalid JSON attributes, missing required fields, and missing edge targets.
9. Added `agentlint import opentelemetry INPUT.json --output OUTPUT.json`.
10. Added offline OpenTelemetry fixtures for passing tool flow, missing approval, private-to-public data flow, unsupported claim, and unsupported metadata.
11. Added generated native IR outputs for representative CLI import flows.
12. Added an offline demo generator with no API calls and no OpenTelemetry SDK dependency.
13. Added an optional OpenTelemetry SDK-backed demo generator that uses real SDK spans and exports them to the supported OTLP-style JSON subset.
14. Added a fuller local support-agent OpenTelemetry SDK demo that simulates private data flow, an unapproved email action, and final-answer exposure.
15. Added a deterministic local-agent demo with an agent-shaped planner, local Python tools, tool results, and final answer.
16. Added adapter and CLI tests.
17. Updated README, architecture, roadmap, and research note.

## OpenTelemetry Attribute Contract

The adapter uses explicit `agentlint.*` attributes because generic OTel spans do not carry enough agent semantics.

Important attributes:

1. `agentlint.trace.id`
2. `agentlint.event.type`
3. `agentlint.event.id`
4. `agentlint.sequence`
5. `agentlint.content`
6. `agentlint.tool.name`
7. `agentlint.tool.call_id`
8. `agentlint.tool.arguments_json`
9. `agentlint.tool.result_json`
10. `agentlint.approval.decision`
11. `agentlint.approval.subject_event`
12. `agentlint.sources`
13. `agentlint.sinks`
14. `agentlint.data_flow.to`
15. `agentlint.approval_for.to`
16. `agentlint.provenance.to`
17. `agentlint.claims_json`
18. `agentlint.trust`

## Verification

Commands run during implementation:

```text
py -3.12 -m pytest tests\test_opentelemetry_adapter.py
py -3.12 -m pytest
py -3.12 -m ruff check .
py -3.12 -m ruff format --check .
git diff --check
git diff --cached --check
```

Results:

```text
tests\test_opentelemetry_adapter.py: 7 passed
full pytest suite: 216 passed
ruff check: passed
ruff format --check: passed
git diff --check: passed
git diff --cached --check: passed
```

## Budget

Routine M7 development and tests cost zero dollars. All fixtures and the demo generator are offline. The OpenAI Agents SDK live demo remains deferred and should be opt-in under a separate budget guard.

The optional OpenTelemetry SDK demo also costs zero dollars. It requires installing the `otel-demo` optional dependency group, but it makes no network calls and does not require an OpenTelemetry Collector.

The support-agent SDK demo produced the expected policy findings during manual verification:

```text
MISSING_APPROVAL
PRIVATE_TO_PUBLIC_SINK
SENSITIVE_FINAL_ANSWER
```

The local-agent demo exercises a deterministic prompt/planner/tool/final-answer loop without using an LLM or API. It is intended as the zero-cost bridge between handwritten trace fixtures and a future OpenAI-backed live agent demo.

## Deferred

1. OpenAI Agents SDK adapter.
2. Live OpenAI Agents demo.
3. OpenTelemetry Collector integration.
4. Binary Protobuf OTLP parsing.
5. Vendor-specific OTel formats.
6. GenAI semantic convention auto-mapping beyond explicit `agentlint.*` attributes.
7. Full value graph modeling.
8. Adapter-level benchmark suite.
