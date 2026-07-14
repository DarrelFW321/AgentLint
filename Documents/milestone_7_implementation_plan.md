# Milestone 7 Implementation Plan

Status: finalized for implementation.

Milestone 7 introduces the first external trace adapter. The original roadmap recommended OpenAI Agents tracing first and OpenTelemetry second. After reevaluating demo cost, repeatability, and current architecture, Milestone 7 should implement OpenTelemetry first with explicit AgentLint semantic attributes, while keeping OpenAI Agents SDK support as a planned follow-on adapter and optional live demo path.

## Objective

Show that AgentLint can analyze traces from an external tracing ecosystem without changing the existing structural checks, policy checks, reports, or fixture discipline.

Milestone 7 is complete when:

1. OpenTelemetry trace JSON can be imported into native AgentLint IR v1 JSON.
2. Imported traces run through existing `agentlint validate` and `agentlint check` behavior.
3. Adapter fixtures cover passing, missing approval, private-to-public data flow, unsupported claim, and unsupported metadata cases.
4. Adapter tests are offline and deterministic.
5. The adapter emits clear warnings for source spans that lack metadata needed for precise checks.
6. The M6 fixture-corpus discipline is extended to imported traces where appropriate.
7. Documentation explains the OpenTelemetry attribute contract and the budget-safe demo path.
8. OpenAI Agents SDK live demos remain optional and are gated so normal tests cost zero dollars.

## Current Baseline

The current codebase already has the right internal boundary:

```text
raw traces
  -> adapters
  -> schema validation
  -> AgentLint IR
  -> structural checks
  -> policy checks
  -> reports
```

Implemented pieces:

1. Native AgentLint IR v1 JSON models and loader.
2. Structural validation.
3. YAML policy validation and policy checks.
4. Text and JSON reports.
5. `agentlint check` for native trace files.
6. Fixture manifest and golden report discipline.

Current adapter gaps:

1. `src/agentlint/adapters/` is only an architectural placeholder.
2. There is no external import command.
3. There is no adapter warning model.
4. There are no external trace fixtures.
5. There is no OpenTelemetry attribute contract.
6. There is no local demo generator for external traces.

## Research Findings

### OpenTelemetry

OpenTelemetry traces are made of spans. A span includes a name, parent span ID, timestamps, span context, attributes, events, links, and status. This maps well to AgentLint's graph-shaped IR because span IDs can become event IDs and parent span IDs can become `parent` edges.

OTLP/HTTP supports JSON Protobuf encoding for trace payloads. In that JSON mapping, `traceId` and `spanId` are hex strings, enum fields are integer values, field names are lowerCamelCase, and unknown fields are ignored by OTLP receivers. AgentLint should be strict for its supported subset, but tolerant enough to ignore unrelated OTel resource fields.

OpenTelemetry also has generative-AI semantic conventions, but they are moving separately from the main OTel docs and do not fully cover AgentLint's approval, source/sink, and provenance concepts. For Milestone 7, AgentLint should define its own narrow `agentlint.*` semantic attributes and optionally recognize known GenAI attributes later.

### OpenAI Agents SDK

OpenAI Agents SDK tracing is agent-native and records agent runs, LLM generations, function tool calls, handoffs, guardrails, and custom spans. It also supports custom trace processors, which is the right way to capture local trace fixtures without relying on the hosted traces dashboard.

However, live OpenAI Agents runs use OpenAI API billing. Tracing may include sensitive generation inputs/outputs and function inputs/outputs by default, so any future OpenAI adapter must preserve the M5 metadata-only report boundary and keep live tests explicitly opt-in.

### Budget Constraint

The development budget target is less than five dollars. OpenTelemetry can be generated and imported locally with no API calls. OpenAI Agents SDK can likely be demoed for cents if kept tiny, but it should not be required for tests or routine development.

## Finalized Scope

Milestone 7 should implement:

1. OpenTelemetry adapter package under `agentlint.adapters.opentelemetry`.
2. A strict, documented supported subset of OTLP-style JSON trace input.
3. AgentLint-specific OpenTelemetry attributes.
4. Adapter result model that contains an AgentLint `Trace` plus adapter warnings.
5. CLI import command:

```text
agentlint import opentelemetry INPUT.json --output OUTPUT.json
```

6. Offline OpenTelemetry fixtures under `examples/external/opentelemetry/`.
7. Generated AgentLint fixture outputs under `examples/generated/` or checked expected outputs under `examples/expected_imports/`.
8. Adapter tests proving imported traces run through existing checks.
9. Local demo generator that writes OpenTelemetry JSON without API calls.
10. Documentation for the OTel attribute contract and demo workflow.
11. Milestone 7 build report after implementation.

Milestone 7 should not implement:

1. Live OpenAI Agents SDK integration as required functionality.
2. Any always-on API calls.
3. OpenTelemetry Collector integration.
4. Binary Protobuf OTLP parsing.
5. Zipkin, Jaeger, or vendor-specific trace formats.
6. Generic inference from arbitrary spans without `agentlint.*` attributes.
7. New policy checks.
8. Full value graph modeling.
9. Directory traversal for `agentlint check`.
10. SARIF, HTML, GitHub annotations, or report file output.

## Reevaluated Decisions

### D7.1 Adapter Order

Decision:

Implement OpenTelemetry first. Keep OpenAI Agents SDK as the next adapter or optional live demo path.

Reasoning:

OpenTelemetry gives us a real external trace ecosystem with zero-cost local demos. It is broad, stable, and easy to generate locally. OpenAI Agents is more semantically direct for agent workflows, but live demos require API billing and setup.

Implementation consequence:

1. M7 is renamed in practice to "OpenTelemetry Adapter With AgentLint Semantic Attributes".
2. The roadmap should be updated to record this order change.
3. OpenAI Agents research and demo notes can be documented, but not implemented as required M7 code.

### D7.2 Import Then Check

Decision:

Add an import command that converts external traces to native AgentLint IR JSON. Do not make `agentlint check` accept external formats directly in M7.

Proposed command:

```text
agentlint import opentelemetry INPUT.json --output OUTPUT.json
```

Reasoning:

The current checker is intentionally native-IR based. A separate import step preserves a clean compiler-style boundary and makes debugging easier because users can inspect the normalized AgentLint trace.

Implementation consequence:

1. Adapter code produces `Trace` or native IR JSON.
2. Existing `agentlint validate` and `agentlint check` remain unchanged.
3. Tests can assert both normalized IR output and downstream diagnostics.

### D7.3 Supported OpenTelemetry Input Shape

Decision:

Support OTLP-style JSON trace exports in M7.

Supported high-level shape:

```text
resourceSpans[]
  scopeSpans[]
    spans[]
      traceId
      spanId
      parentSpanId
      name
      startTimeUnixNano
      endTimeUnixNano
      attributes[]
      events[]
```

Reasoning:

OTLP JSON is a documented interchange shape. Supporting the subset we need is enough for fixture imports, local generation, and later collector/exporter compatibility.

Implementation consequence:

1. Ignore metrics and logs.
2. Ignore unrelated resource and scope fields in M7.
3. Preserve source span IDs in `source_ref`.
4. Sort spans deterministically by timestamp, then parent relation, then span ID.

### D7.4 AgentLint Semantic Attributes

Decision:

Require explicit `agentlint.*` attributes for AgentLint-specific semantics.

Initial attributes:

```text
agentlint.event.type
agentlint.event.id
agentlint.sequence
agentlint.content
agentlint.tool.name
agentlint.tool.call_id
agentlint.tool.arguments_json
agentlint.tool.result_json
agentlint.approval.decision
agentlint.approval.subject_event
agentlint.sources
agentlint.sinks
agentlint.data_flow.to
agentlint.approval_for.to
agentlint.provenance.to
agentlint.claims_json
agentlint.trust
```

Reasoning:

OpenTelemetry spans are generic operations. AgentLint should not pretend it can infer approvals, source sensitivity, sinks, or claim evidence from arbitrary span names. Explicit attributes keep the analysis honest and make unsupported metadata visible.

Implementation consequence:

1. Spans without `agentlint.event.type` become adapter warnings and are skipped by default.
2. The adapter may use span name as fallback content only for non-sensitive metadata fields.
3. JSON-valued attributes are parsed strictly with clear warnings on invalid JSON.
4. Source/sink labels are copied into event metadata for existing policy checks.

### D7.5 Event Mapping

Decision:

Map OTel spans with `agentlint.event.type` directly to AgentLint event types.

Mapping:

```text
agentlint.event.type=user_message -> UserMessageEvent
agentlint.event.type=developer_instruction -> DeveloperInstructionEvent
agentlint.event.type=model_call -> ModelCallEvent
agentlint.event.type=tool_call -> ToolCallEvent
agentlint.event.type=tool_result -> ToolResultEvent
agentlint.event.type=approval -> ApprovalEvent
agentlint.event.type=final_answer -> FinalAnswerEvent
```

Reasoning:

Direct mapping keeps adapter behavior predictable and ensures existing structural validation owns relationship errors after import.

Implementation consequence:

1. Unknown event types produce adapter warnings.
2. Missing required fields produce adapter warnings and skip the span when no valid IR event can be constructed.
3. Event IDs use `agentlint.event.id` when present, otherwise a stable `otel_{spanId}` form.
4. Sequence uses `agentlint.sequence` when present, otherwise deterministic timestamp order.

### D7.6 Edge Mapping

Decision:

Map parent span IDs to `parent` edges and explicit edge attributes to semantic edges.

Edges:

1. `parentSpanId` -> `parent`
2. `agentlint.data_flow.to` -> `data_flow`
3. `agentlint.approval_for.to` -> `approval_for`
4. `agentlint.provenance.to` -> `provenance`

Reasoning:

OpenTelemetry naturally represents operation nesting with parent span IDs. AgentLint-specific data-flow, approval, and provenance relationships need explicit annotations.

Implementation consequence:

1. Missing edge targets should still be represented when possible so structural validation can emit `MISSING_EVENT_REFERENCE`.
2. Edge IDs should be deterministic, for example `otel_parent_{from}_{to}`.
3. Duplicate generated edge IDs should be avoided by stable suffixing.

### D7.7 Adapter Warnings

Decision:

Introduce adapter warnings separate from AgentLint diagnostics.

Proposed model:

```text
AdapterWarning:
  code: str
  message: str
  source_ref: SourceRef | None
```

Initial warning codes:

```text
OTEL_SPAN_SKIPPED_UNSUPPORTED_EVENT_TYPE
OTEL_SPAN_SKIPPED_MISSING_EVENT_TYPE
OTEL_SPAN_SKIPPED_INVALID_JSON_ATTRIBUTE
OTEL_SPAN_SKIPPED_MISSING_REQUIRED_FIELD
OTEL_EDGE_TARGET_NOT_FOUND
OTEL_PARTIAL_SEMANTICS
```

Reasoning:

Milestone 7 exit criteria require actionable warnings when source traces lack metadata. These are adapter import warnings, not policy diagnostics, because they describe import fidelity rather than trace behavior.

Implementation consequence:

1. Import command prints warnings to stderr.
2. Import can still succeed if at least one valid event is produced.
3. Import exits non-zero if no valid AgentLint trace can be produced.
4. Adapter warnings are tested directly.

### D7.8 Output File Requirement

Decision:

Require `--output` for import commands in M7.

Reasoning:

`agentlint check` deliberately deferred report file output, but import is a transformation command. Writing normalized IR to a file is the main purpose of the command, and requiring output avoids mixing JSON payloads with warnings.

Implementation consequence:

1. Normalized trace JSON is written to `--output`.
2. Warnings go to stderr.
3. A success summary goes to stdout.
4. Existing report output remains stdout-only.

### D7.9 Offline Demo Generator

Decision:

Add a local OpenTelemetry demo generator that writes fixture JSON without requiring `opentelemetry-sdk`.

Reasoning:

The demo should cost zero dollars and avoid adding dependencies. Hand-generating the small OTLP JSON subset is sufficient for M7 and keeps the repo lightweight.

Implementation consequence:

1. Add `examples/opentelemetry/generate_demo_trace.py`.
2. The script writes a deterministic OTel JSON file.
3. The generated trace demonstrates a policy violation, preferably missing approval or private-to-public sink.
4. Tests should not depend on running the script unless it is cheap and deterministic.

### D7.10 OpenAI Agents Follow-On Plan

Decision:

Document OpenAI Agents SDK as a follow-on adapter, not an M7 requirement.

Reasoning:

It remains the better agent-native demo, but it introduces setup and billing. The user budget allows a small live run if necessary, but the project should not require it.

Implementation consequence:

1. Add docs describing a future optional OpenAI live demo budget guard.
2. No live API test is added in M7.
3. Future OpenAI tests should be fixture-only by default and live only under an explicit marker such as `live_api`.

## Build Track

### B7.1 Add Adapter Package Boundary

Files:

```text
src/agentlint/adapters/__init__.py
src/agentlint/adapters/common.py
src/agentlint/adapters/opentelemetry.py
tests/test_opentelemetry_adapter.py
```

Implement:

1. `AdapterWarning`.
2. `AdapterResult`.
3. Warning code constants or enum.
4. OpenTelemetry import entrypoint.

### B7.2 Parse OTLP-Style JSON Subset

Files:

```text
src/agentlint/adapters/opentelemetry.py
tests/test_opentelemetry_adapter.py
```

Implement:

1. Load JSON input from a path.
2. Walk `resourceSpans[].scopeSpans[].spans[]`.
3. Decode OTel attribute arrays into Python values.
4. Preserve `traceId`, `spanId`, `parentSpanId`, name, timestamps, and attributes.
5. Ignore unrelated OTel fields.

### B7.3 Map Spans To AgentLint Events

Files:

```text
src/agentlint/adapters/opentelemetry.py
tests/test_opentelemetry_adapter.py
```

Implement mapping for:

1. `user_message`
2. `developer_instruction`
3. `model_call`
4. `tool_call`
5. `tool_result`
6. `approval`
7. `final_answer`

### B7.4 Map Edges

Files:

```text
src/agentlint/adapters/opentelemetry.py
tests/test_opentelemetry_adapter.py
```

Implement:

1. Parent edges from `parentSpanId`.
2. Data-flow edges from `agentlint.data_flow.to`.
3. Approval edges from `agentlint.approval_for.to`.
4. Provenance edges from `agentlint.provenance.to`.
5. Deterministic edge IDs.

### B7.5 Add Import CLI

Files:

```text
src/agentlint/cli.py
tests/test_cli.py
```

Implement:

```text
agentlint import opentelemetry INPUT.json --output OUTPUT.json
```

Behavior:

1. Write native AgentLint IR JSON to output.
2. Print import summary to stdout.
3. Print adapter warnings to stderr.
4. Exit `0` on successful import.
5. Exit `1` on malformed input or no importable events.

### B7.6 Add External Fixtures

Files:

```text
examples/external/opentelemetry/*.json
examples/expected_imports/opentelemetry/*.json
```

Add fixtures for:

1. Passing tool flow.
2. Missing approval.
3. Private-to-public data flow.
4. Unsupported claim.
5. Unsupported metadata or missing event type.

### B7.7 Extend Corpus Discipline

Files:

```text
examples/fixtures/manifest.yaml
tests/test_fixture_corpus.py
```

Implement:

1. Add imported native IR outputs to the fixture corpus if checked in.
2. Or add a focused adapter test that imports OTel fixtures then runs `check_trace`.
3. Keep M6 diagnostic coverage guard intact.

Decision:

Prefer focused adapter tests for generated imports in M7. Add checked-in generated native traces to the M6 manifest only for stable demo outputs that should become long-term evaluation fixtures.

### B7.8 Add Offline Demo Generator

Files:

```text
examples/opentelemetry/generate_demo_trace.py
```

Implement:

1. Deterministic OTLP-style JSON generation.
2. No network calls.
3. No dependency on `opentelemetry-sdk`.
4. Example command comments in README.

### B7.9 Update Documentation

Files:

```text
README.md
Documents/architecture.md
Documents/milestones.md
Documents/research_note.md
Documents/milestone_7_build_report.md
```

Update:

1. M7 adapter order change.
2. OpenTelemetry import command.
3. AgentLint OTel semantic attributes.
4. Budget-safe demo instructions.
5. OpenAI Agents SDK follow-on plan.
6. Build report after verification.

## Verification Plan

Required commands:

```text
py -3.12 -m pytest tests\test_opentelemetry_adapter.py
py -3.12 -m pytest
py -3.12 -m ruff check .
py -3.12 -m ruff format --check .
git diff --check
git diff --cached --check
```

Representative manual workflow:

```text
py -3.12 examples\opentelemetry\generate_demo_trace.py
py -3.12 -m agentlint import opentelemetry examples\external\opentelemetry\demo_missing_approval.json --output examples\generated\otel_demo_missing_approval.agentlint.json
py -3.12 -m agentlint validate examples\generated\otel_demo_missing_approval.agentlint.json
py -3.12 -m agentlint check examples\generated\otel_demo_missing_approval.agentlint.json --policy examples\policies\policy_checks.yaml
```

Expected behavior:

1. Import creates valid native AgentLint IR JSON.
2. Existing structural validation runs unchanged.
3. Existing policy checks run unchanged.
4. Missing metadata produces adapter warnings, not silent drops.
5. Tests and demos make no network calls.
6. Routine verification costs zero dollars.

## Budget Plan

Milestone 7 routine development:

```text
Expected API cost: $0
```

Optional OpenAI Agents live demo after M7:

```text
Expected API cost: cents for a tiny local-tool-only run
Hard budget: less than $5
```

Budget guardrails:

1. No live API tests in default pytest.
2. Any future live tests must use a `live_api` marker and require an explicit environment variable.
3. Use a separate API project with a low budget limit where possible.
4. Use short prompts and short outputs.
5. Avoid web search, code interpreter, file search, hosted shell, image, audio, or other paid built-in tools.
6. Keep OpenAI traces as recorded fixtures for normal tests.

## Risks And Mitigations

### Risk: Generic OTel Spans Lack Agent Semantics

Mitigation:

Require explicit `agentlint.*` attributes and warn when they are absent.

### Risk: Adapter Warnings Become A Second Diagnostic System

Mitigation:

Keep adapter warnings limited to import fidelity. Policy and structural violations remain AgentLint diagnostics after normalization.

### Risk: OTLP JSON Shape Is Too Broad

Mitigation:

Support a documented subset first and ignore unrelated fields. Add broader compatibility only when fixtures require it.

### Risk: Imported Trace Order Is Unstable

Mitigation:

Sort deterministically by explicit sequence, timestamp, and span ID.

### Risk: Sensitive Payloads Leak Through Import Or Reports

Mitigation:

Keep reports metadata-only. Preserve raw imported values in native IR only when required by event schema, and keep redaction tests around downstream reports.

### Risk: OpenAI Demo Costs More Than Expected

Mitigation:

Do not make OpenAI live demo part of M7 verification. Keep it optional, gated, tiny, and local-tool-only.

## Deferred After Milestone 7

1. OpenAI Agents SDK adapter implementation.
2. Live OpenAI Agents demo script.
3. OpenTelemetry Collector integration.
4. Binary Protobuf OTLP parsing.
5. Vendor-specific OTel exports.
6. GenAI semantic convention auto-mapping beyond explicit `agentlint.*` attributes.
7. Full value graph modeling.
8. Adapter-level performance benchmarks.
9. Runtime gating.

## Completion Checklist

- [ ] Adapter package exists.
- [ ] Adapter warning/result models exist.
- [ ] OTLP-style JSON subset is parsed.
- [ ] OTel attributes decode correctly.
- [ ] OTel spans map to all current AgentLint event types.
- [ ] Parent edges map from `parentSpanId`.
- [ ] AgentLint semantic edges map from explicit attributes.
- [ ] Unsupported/missing metadata creates warnings.
- [ ] Import CLI exists.
- [ ] Import CLI writes native IR JSON to `--output`.
- [ ] External OpenTelemetry fixtures exist.
- [ ] Expected import outputs or equivalent adapter assertions exist.
- [ ] Imported traces run through existing checks.
- [ ] Offline demo generator exists.
- [ ] README documents demo workflow.
- [ ] Architecture and roadmap docs record the adapter order decision.
- [ ] Research note records M7 findings.
- [ ] Verification passes.
- [ ] Milestone 7 build report is written after implementation.
