# Milestone 9 Implementation Plan: OpenAI Agents Capture Adapter

Status: implemented. See `Documents/milestone_9_build_report.md`.

## Goal

Add the first framework-native AgentLint integration for Python applications built with the OpenAI Agents SDK. Users should be able to capture ordinary agent test runs without authoring OpenTelemetry spans or AgentLint IR, normalize the captured execution into the existing IR, and run existing structural and policy checks.

Milestone 9 proves the first-class adapter architecture. It does not claim that every OpenAI Agents feature or every application-specific safety meaning can be captured automatically.

## Research Basis

The OpenAI Agents SDK enables tracing by default around `Runner.run`, `Runner.run_sync`, and `Runner.run_streamed`. Its native tracing includes agent spans, model generations, function tools, handoffs, and guardrails. It exposes `add_trace_processor()` for an additional processor, `set_trace_processors()` for replacing processors, and `flush_traces()` for forcing buffered work to complete. The processor interface receives trace/span start and end callbacks and requires implementations to be thread-safe, non-blocking, and error-tolerant.

Official references:

1. [Agents SDK tracing guide](https://openai.github.io/openai-agents-python/tracing/)
2. [Tracing processor interface](https://openai.github.io/openai-agents-python/ref/tracing/processor_interface/)
3. [Tracing span data reference](https://openai.github.io/openai-agents-python/ref/tracing/)
4. [Agent lifecycle hooks](https://openai.github.io/openai-agents-python/ref/lifecycle/)
5. [Human-in-the-loop approvals](https://openai.github.io/openai-agents-python/human_in_the_loop/)
6. [Run result surfaces](https://openai.github.io/openai-agents-python/results/)

Research was reevaluated against the implemented AgentLint IR and capture-completeness contract before finalizing the decisions below.

## Final Scope

Milestone 9 includes:

1. Python OpenAI Agents SDK support.
2. A framework snapshot format independent of native SDK objects.
3. A custom tracing processor that records traces locally.
4. Deterministic normalization into AgentLint IR.
5. Additive IR events for agent runs, handoffs, and guardrails.
6. Function-tool call/result mapping.
7. Model-generation mapping.
8. Framework-specific capture completeness.
9. A one-line in-process instrumentation API.
10. A pytest plugin for test-session capture and checking.
11. Fixture-only default tests requiring no API key or network.
12. One optional, explicitly gated live demo.

Milestone 9 does not include:

1. Generic shell-command injection through `sitecustomize`.
2. Automatic interception of every `Runner` return value.
3. Automatic approval/denial capture from `RunState` mutation.
4. Hosted tool, computer, shell, apply-patch, realtime, voice, or sandbox-agent parity.
5. LangGraph, CrewAI, AutoGen, or other framework adapters.
6. Policy-required capture enforcement.
7. Hosted OpenAI trace download or dashboard scraping.

These limits keep the first integration useful and honest without relying on broad monkey-patching or private SDK internals.

## Architecture Decisions

### 1. Use Native Tracing, Not OpenTelemetry Translation

The OpenAI adapter consumes the Agents SDK tracing interface directly. It does not route SDK spans through the generic OpenTelemetry importer.

The pipeline is:

```text
OpenAI Agents SDK trace callbacks
  -> AgentLint OpenAI snapshot records
  -> OpenAI adapter normalization
  -> AgentLint IR v1
  -> existing structural/policy passes
  -> report v2 with capture completeness
```

This preserves native span types and avoids requiring users to add `agentlint.*` OpenTelemetry attributes.

### 2. Separate SDK Capture From Normalization

Do not make the normalizer depend directly on live SDK objects. Define strict, versioned snapshot models containing only stable exported fields needed by AgentLint:

```text
agentlint.openai_agents.snapshot.v1
trace_id
workflow_name
group_id
metadata
started_at
ended_at
spans[]
capture_incidents[]
sdk_version
```

Each span snapshot contains:

```text
trace_id
span_id
parent_id
started_at
ended_at
error
span_type
span_data
```

The processor converts SDK objects to snapshots at callback time using documented public properties and exported span data. The adapter normalizes snapshots separately. This gives fixture-only tests, protects the core from SDK object churn, and allows captured files to be replayed.

### 3. Use an Optional Dependency With a Tested Compatibility Window

Add an extra such as:

```toml
openai-agents = ["openai-agents>=0.18,<0.19"]
```

The exact lower bound must match the version used to create fixtures and must be rechecked immediately before B9 implementation. The adapter should detect the installed SDK version and fail clearly outside the tested range rather than silently interpreting changed span data.

The current [PyPI package version](https://pypi.org/project/openai-agents/) observed during planning is 0.18.1, but this is time-sensitive and is not a permanent compatibility promise.

### 4. Add Framework Events to IR Additively

The current IR cannot faithfully preserve native agent, handoff, or guardrail spans. Add three optional event variants while retaining `agentlint.ir.v1` compatibility:

```text
agent_run
  agent_name

handoff
  from_agent
  to_agent

guardrail
  guardrail_name
  triggered
```

Existing native files remain valid. Existing passes ignore the new events unless a check explicitly consumes them. Structural validation still validates IDs, ordering, and parent references.

Do not encode these spans only in metadata on unrelated events; doing so would discard framework structure and make later checks adapter-specific.

### 5. Normalize One Function Span Into Call and Result Events

An OpenAI `FunctionSpanData` combines a function name, input, and output. AgentLint represents tool calls and results separately.

Map deterministically:

```text
span_<id>                  -> tool_call event <span_id>:call
span_<id> with output      -> tool_result event <span_id>:result
tool_result.call_id        -> <span_id>:call
parent edge                -> native parent event when representable
parent edge call -> result -> explicit parent edge
```

Parse function input as JSON only when valid. Otherwise preserve a safe non-payload incident and set `tool_arguments` to partial. Do not put raw malformed input into warnings or reports.

An ended function span with no output produces only a tool call and records partial tool-result coverage. An SDK span error is preserved as symbolic metadata without copying sensitive error payloads.

### 6. Map Generation and Response Spans to Model Calls

Map `GenerationSpanData` to `model_call` using documented input, output, model, model configuration, and usage fields where present.

SDK 0.18.x OpenAI Responses runs may emit `response` spans containing a response identifier and usage instead of generation payloads. Map these to structural `model_call` events with nullable input/output and mark payload-dependent coverage partial. Recognize SDK custom `task` and `turn` spans as transparent hierarchy containers and collapse parent links through them; continue warning for other custom span names.

The SDK can omit sensitive generation and function payloads when `trace_include_sensitive_data` is false. Missing payloads must not cause the span itself to be discarded:

1. Emit the model/tool event with structural fields.
2. Use safe placeholders permitted by the IR where required.
3. Mark payload-dependent capabilities partial or unavailable.
4. Record a sanitized capture reason.

Do not include model configuration or raw usage details in AgentLint reports unless a later requirement needs them.

### 7. Do Not Infer Final Answers From the Last Generation

The last generation output is not universally equivalent to `RunResult.final_output`. Tool-use behavior can make a tool result final, interrupted runs can have no final output, and structured output can differ from raw model text.

The trace-processor-only path therefore does not emit `final_answer` by guessing from the last generation. It reports final-answer coverage as unavailable.

The pytest integration may offer an explicit helper:

```python
agentlint_openai.record_result(result)
```

This records `RunResult.final_output` when the test already has the result. The helper is optional for basic tool checks. Automatic result interception is deferred until it can preserve sync, async, and streamed runner behavior without broad monkey-patching.

### 8. Do Not Infer Approval Decisions From Tool Spans

The SDK human-in-the-loop flow exposes pending approvals through run-result interruptions and records decisions in `RunState`. The tracing span types do not provide a general approval event contract.

Milestone 9 therefore:

1. Reports approval coverage as unavailable in processor-only capture.
2. Provides an explicit helper for an application or future plugin to record approval/denial events.
3. Does not treat a successful function span as proof of approval.
4. Defers automatic `RunState.approve()` and `RunState.reject()` interception.

### 9. Preserve Existing OpenAI Trace Export Behavior by Default

`add_trace_processor()` adds AgentLint alongside the SDK's configured processors. `set_trace_processors()` replaces them and can disable the default OpenAI backend exporter.

The one-line API defaults to additive registration:

```python
from agentlint.integrations.openai_agents import instrument

instrument()
```

This avoids silently changing an application's existing tracing behavior. Provide an explicit local-only mode for users who intentionally want AgentLint to replace SDK trace processors:

```python
instrument(export_mode="local_only")
```

`local_only` must warn that it replaces existing processors and is intended for isolated test processes. Processor restoration is not promised unless the SDK exposes a public way to enumerate and restore the previous processor set.

Documentation must also state that the SDK includes potentially sensitive generation and function data by default and that users can disable that payload capture with `RunConfig.trace_include_sensitive_data=False` or `OPENAI_AGENTS_TRACE_INCLUDE_SENSITIVE_DATA=0`.

### 10. Keep Processor Callbacks Fast and Thread-Safe

The processor must:

1. Use a lock around mutable session state.
2. Perform only bounded object-to-snapshot conversion in callbacks.
3. Never run policy checks in a callback.
4. Never block on network I/O.
5. Catch callback errors and record capture incidents.
6. Make `force_flush()` write completed snapshots atomically.
7. Make `shutdown()` idempotent.

Normalization and policy checking happen after trace completion or test-session finalization.

### 11. Group by SDK Trace, Not Test by Default

One SDK trace becomes one AgentLint trace. Preserve `trace_id`, workflow name, group ID, parent IDs, timestamps, and safe source references.

The pytest plugin associates captured trace IDs with the active pytest node ID using a context variable. A test can produce zero, one, or many traces. Multi-trace tests remain separate AgentLint runs so failures identify the actual workflow trace.

### 12. Make Pytest the Zero-Change MVP Path

Add a pytest plugin with explicit activation:

```bash
pytest --agentlint --agentlint-policy agentlint.yaml
```

The plugin:

1. Starts an isolated capture session at pytest session start.
2. Sets the active node ID during each test.
3. Registers the OpenAI trace processor once.
4. Flushes completed traces after each test.
5. Normalizes and checks traces after capture.
6. Adds diagnostics to the test report or a dedicated terminal section.
7. Fails according to existing AgentLint diagnostic thresholds.
8. Fails clearly when OpenAI capture was requested but no supported traces were observed.
9. Leaves tests that do not run agents unchanged unless strict no-trace behavior is explicitly selected.

The plugin is activated through pytest's plugin entry point when the OpenAI extra is installed, but capture begins only when `--agentlint` is present.

Do not add generic `sitecustomize` injection in M9. It changes Python startup globally within a child process, is difficult to explain and debug, and is unnecessary to prove the first supported workflow.

### 13. Define Conservative OpenAI Capture Completeness

Processor-only baseline:

| Capability | Baseline | Reason |
| --- | --- | --- |
| Agent runs | Captured | The SDK traces each agent invocation with an agent span. |
| Model calls | Captured | The SDK traces model generations. |
| Tool calls | Partial | Function spans are supported; hosted and other tool families are not complete in M9. |
| Tool arguments | Partial | Depends on sensitive-data capture and valid exported input. |
| Tool results | Partial | Depends on supported function spans, completion, and sensitive-data capture. |
| Approvals | Unavailable | General approval decisions are not exposed by tracing spans. |
| Data flow | Unavailable | Parentage is not value-level data flow. |
| Provenance | Unavailable | The SDK does not provide AgentLint claim-evidence semantics. |
| Final answers | Unavailable | Trace spans do not provide the authoritative `RunResult.final_output`. |

Optional explicit result or approval helpers can improve the relevant entry to partial for that trace, but they must not promote overall framework support to captured without an exhaustive source guarantee.

### 14. Keep Routine Tests Offline and Free

Default tests use checked-in OpenAI snapshot fixtures and lightweight fake processor objects. They must not require:

1. `OPENAI_API_KEY`
2. API calls
3. Hosted trace export
4. Internet access
5. OpenAI billing

Add one optional test marker:

```text
live_openai
```

The live demo requires `OPENAI_API_KEY`, uses one short run, one local function tool at most, an explicitly selected inexpensive model, small inputs/outputs, no hosted tools, and a documented expected cost measured in cents. It never runs under default pytest.

## Proposed Public Interfaces

### Import a Recorded Snapshot

```bash
agentlint import openai-agents INPUT.json --output OUTPUT.agentlint.json
```

This mirrors the OpenTelemetry import workflow and makes adapter normalization independently testable.

### One-Line In-Process Capture

```python
from agentlint.integrations.openai_agents import instrument

session = instrument(output_dir=".agentlint/traces")
```

The returned session supports:

```python
session.flush()
session.close()
```

Repeated `instrument()` calls must be idempotent or fail clearly rather than registering duplicate processors.

### Pytest

```bash
pytest --agentlint --agentlint-policy agentlint.yaml
```

Optional settings belong under `[tool.pytest.ini_options]` or a dedicated AgentLint config section after the CLI behavior is stable.

## Implementation Phases

### Phase 1: Dependency and Snapshot Contract

1. Add the optional OpenAI Agents dependency extra.
2. Add supported-version detection and actionable incompatibility errors.
3. Define strict snapshot v1 models.
4. Add JSON loading/writing with sanitized schema errors.
5. Check in representative snapshots for generation, function, handoff, guardrail, errors, and missing sensitive data.

### Phase 2: IR Extensions

1. Add `AgentRunEvent`, `HandoffEvent`, and `GuardrailEvent` to IR v1.
2. Export the models from `agentlint.ir.v1`.
3. Add model, loader, structural, and backward-compatibility tests.
4. Update the glossary and architecture event list.

### Phase 3: Pure OpenAI Normalizer

1. Implement snapshot-to-IR conversion without importing the live SDK.
2. Generate deterministic event IDs and ordering.
3. Split function spans into tool call/result events.
4. Map agent, generation, handoff, and guardrail spans.
5. Preserve parent relationships where representable.
6. Emit adapter warnings for unsupported span types, malformed payloads, missing parent targets, and incomplete spans.
7. Attach the conservative OpenAI capture profile.
8. Add `agentlint import openai-agents`.

### Phase 4: Native Trace Processor

1. Implement the SDK `TracingProcessor` interface behind lazy imports.
2. Record trace/span lifecycle callbacks into an isolated session.
3. Make callback state thread-safe and non-blocking.
4. Implement deterministic flush and idempotent shutdown.
5. Add additive and explicit local-only registration modes.
6. Test with fake public-interface objects and, when installed, SDK-created local trace/span objects without model calls.

### Phase 5: In-Process Integration

1. Implement `instrument()` and the capture-session API.
2. Add duplicate-registration protection.
3. Add explicit `record_result()` and approval-recording helpers.
4. Document payload privacy and hosted-export behavior.
5. Add a local SDK tracing demo that creates native SDK spans without an API call.

### Phase 6: Pytest Plugin

1. Add explicit `--agentlint` activation.
2. Add policy and fail-threshold options.
3. Associate traces with pytest node IDs.
4. Flush and check traces deterministically.
5. Render concise diagnostics without duplicating full reports for every passing test.
6. Handle zero-capture, disabled tracing, processor failure, and child crash cases explicitly.
7. Document initial `pytest-xdist` limitations; either isolate by worker or reject unsupported parallel mode clearly.

### Phase 7: Optional Live Demo

1. Add a minimal local-function-tool agent example.
2. Gate it on `OPENAI_API_KEY` and `live_openai`.
3. Select a model explicitly rather than relying on the SDK default.
4. Keep a hard documented budget below five dollars and an expected cost in cents.
5. Save only sanitized or intentionally synthetic demo data.

### Phase 8: Documentation and Corpus

1. Add the OpenAI mapping table and completeness matrix.
2. Add setup for in-process and pytest workflows.
3. Explain hosted-export and sensitive-data settings.
4. Add OpenAI fixtures to the M6 corpus discipline.
5. Add an M9 build report with tested SDK version and known limitations.

## Expected Files

```text
src/agentlint/adapters/openai_agents.py
src/agentlint/adapters/openai_snapshot.py
src/agentlint/integrations/openai_agents.py
src/agentlint/integrations/pytest_openai.py
src/agentlint/ir/v1/models.py
src/agentlint/ir/v1/__init__.py
src/agentlint/cli.py
pyproject.toml
tests/test_openai_snapshot.py
tests/test_openai_agents_adapter.py
tests/test_openai_agents_integration.py
tests/test_pytest_openai.py
tests/test_ir_v1_models.py
tests/test_structural_pass.py
examples/external/openai_agents/*.json
examples/openai_agents/*.py
Documents/*.md
README.md
```

## Failure Behavior

AgentLint must produce an explicit error or incomplete result when:

1. The OpenAI Agents SDK is not installed.
2. The installed SDK version is outside the tested range.
3. SDK tracing is globally or per-run disabled.
4. A ZDR configuration makes SDK tracing unavailable.
5. The processor was not registered.
6. No supported traces were captured when capture was required.
7. A trace or span never completed.
8. Flush or snapshot persistence failed.
9. Snapshot schema validation failed.
10. A pytest worker configuration is unsupported.

It must not emit a clean policy result for an empty capture session.

## Testing Strategy

### Required Offline Tests

1. Snapshot schema validation and redacted errors.
2. Every supported span mapping.
3. One-to-many function span mapping.
4. Stable IDs and deterministic ordering.
5. Parent-edge mapping.
6. Unknown/unsupported span warnings.
7. Sensitive-data-disabled behavior.
8. Capture completeness baseline and degradation.
9. Processor concurrency and duplicate callback handling.
10. Flush and shutdown idempotence.
11. Pytest association and exit behavior.
12. No-trace and disabled-tracing failures.
13. Existing fixture-corpus and golden-report compatibility.
14. Report redaction forbidden strings.

### Optional Live Tests

1. One model call with a short prompt.
2. At most one local function-tool call.
3. Trace processor receives and normalizes the completed run.
4. Existing AgentLint policy checks run over the result.
5. Test is skipped unless both the marker and API key are present.

## Verification Commands

```powershell
py -3.12 -m pytest
py -3.12 -m pytest -m "not live_openai"
py -3.12 -m ruff check .
py -3.12 -m ruff format --check .
git diff --check
```

Optional live verification:

```powershell
py -3.12 -m pytest -m live_openai --run-live-openai
```

## Exit Criteria

Milestone 9 is complete when:

1. Recorded OpenAI Agents snapshots normalize deterministically into AgentLint IR.
2. Agent, generation, function, handoff, and guardrail spans are preserved without adapter-specific policy logic.
3. Function tool flows trigger existing tool and approval policy checks where the represented evidence permits them.
4. OpenAI traces include accurate M8 completeness profiles.
5. A user can activate in-process capture with one central call.
6. A user can check existing pytest agent tests through explicit plugin activation without changing each test.
7. Empty, disabled, failed, or unsupported capture cannot appear as a clean pass.
8. Default tests are deterministic, offline, and cost zero dollars.
9. The optional live demo remains below the five-dollar hard budget.
10. Existing OpenTelemetry and native workflows continue to pass.
11. Full pytest, Ruff, formatting, and diff checks pass.

## Deferred Points

1. Generic command wrapping and Python startup injection.
2. Automatic `Runner` result interception.
3. Automatic `RunState` approval interception.
4. Hosted and built-in tool parity.
5. Realtime, voice, and sandbox agents.
6. `pytest-xdist` support beyond an explicit safe baseline.
7. Policy-required capture enforcement.
8. LangGraph and other framework adapters.
9. Hosted trace retrieval.
10. Automatic provenance and value-level data flow.

## Final Judgment

M9 should build a deep, fixture-first OpenAI Agents integration around the SDK's documented tracing processor interface. The processor is sufficient for valuable agent, model, function-tool, handoff, and guardrail analysis, but it is not sufficient for authoritative approvals, final outputs, provenance, or value-level data flow. M8 completeness reporting lets AgentLint expose those boundaries honestly.

The pytest plugin is the appropriate low-configuration MVP because it controls a test process with explicit user activation. Broad startup injection and monkey-patching would increase adoption convenience but also increase intrusion and compatibility risk before the adapter contract has been proven.
