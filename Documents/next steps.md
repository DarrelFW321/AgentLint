# Next Steps

Status: working direction after Milestone 10.

## Current Position

AgentLint now has a working core engine, policy-aware evidence enforcement, generic OpenTelemetry import, and a first-class OpenAI Agents capture path with explicit semantic helpers. The immediate priority is evaluating this workflow on realistic projects before expanding to another framework.

The current engine includes:

1. Native AgentLint IR v1.
2. Structural validation.
3. YAML policy DSL.
4. Offline policy checks.
5. Stable diagnostics.
6. Text and JSON reports.
7. CI exit thresholds.
8. Fixture corpus and golden report discipline.
9. Generic OpenTelemetry import.
10. Local OpenTelemetry SDK demos.

The engine is not perfect, but it is complete enough for useful adapter demos and first-class framework integration.

## Product Principle

Users should be expected to define their policies, because only they know what their tools, sources, sinks, approvals, and risk boundaries mean.

Users should not be expected to build adapters, write AgentLint IR, configure OpenTelemetry, run collectors, or manually add spans everywhere before AgentLint becomes useful.

AgentLint should not absorb every adjacent agent-safety concern. Its initial job is to lint completed traces, not to become an authorization service, approval UI, runtime gateway, observability backend, semantic evaluator, or compliance platform.

The target product experience should be:

```text
Install the adapter, define your policy, run your existing agent tests.
```

For supported frameworks:

```text
Zero-configuration capture where possible.
One-line setup where necessary.
Explicit annotations only for semantics the framework cannot know.
```

The governing product question is:

> Did this recorded agent run violate a developer-defined policy that can be verified from the captured evidence?

New work belongs in the initial scope when it materially improves deterministic policy-regression detection over recorded agent tests. Missing evidence must produce `not_verifiable`; it must not trigger speculative inference.

## Generic OpenTelemetry Boundary

Generic OpenTelemetry is useful, but it cannot be the main zero-config story.

OpenTelemetry can tell us that operations happened:

1. HTTP requests.
2. Function calls.
3. LLM calls, if instrumented.
4. Parent-child span structure.
5. Timing and errors.

AgentLint needs policy meaning:

1. This operation is a tool call.
2. This tool is `send_email`.
3. This source is `customer_profile`.
4. This source is private.
5. This sink is `web_search.query`.
6. This sink is public.
7. This private value flowed into that public sink.
8. This approval authorized this action.
9. This final-answer claim relied on this evidence.

Generic OTel does not standardize most of that meaning. Therefore:

```text
First-class framework adapters can be close to zero-config.
Generic OpenTelemetry import remains an advanced fallback.
```

## Framework Adapter Direction

AgentLint should build first-class framework adapters that use framework-native tracing/events.

For OpenAI Agents SDK, the likely approach is:

1. Register a custom trace processor.
2. Capture framework-native traces and spans.
3. Map agent runs, model calls, function tool calls, guardrails, and handoffs into AgentLint IR.
4. Flush traces at the end of a run or test.
5. Run existing structural and policy checks.

The trace processor does not expose an authoritative general approval decision or `RunResult.final_output`. M9 will report those capabilities as unavailable unless the application uses an explicit result or approval helper.

This avoids asking users to manually emit OpenTelemetry spans or AgentLint-specific attributes.

The intended M9 pytest shape is:

```bash
pytest --agentlint
```

## Setup Levels

AgentLint should support three setup levels.

### Level 1: Automatic Framework Capture

For officially supported frameworks, AgentLint should capture native framework events automatically.

Expected captured information:

1. Agent runs.
2. Model calls.
3. Function tool calls.
4. Tool names.
5. Tool arguments when available.
6. Tool results when available.
7. Parent-child execution structure.
8. Errors and retries.
9. Final output.
10. Framework-native guardrails or approvals when available.

The user should not need to:

1. Configure an OpenTelemetry Collector.
2. Configure OTLP exporters.
3. Export trace files manually.
4. Write AgentLint IR.
5. Wrap every tool manually.
6. Add AgentLint-specific span attributes.

### Level 2: One-Line Bootstrap

If automatic capture cannot be activated safely, require one central setup line:

```python
from agentlint_openai import instrument

instrument()
```

This should register framework tracing globally and require no per-tool or per-test changes.

### Level 3: Optional Semantic Annotations

Some semantics cannot be inferred from framework events or policy alone.

Optional helpers should cover:

1. Sensitive/private sources.
2. Public/private/model-visible sinks.
3. Approval events.
4. Claim evidence.
5. Trust boundaries.

Preferred shape:

```python
with agentlint.source("customer_profile"):
    customer = load_customer(account_id)

agentlint.approval.record("evt_send_email", decision="approved")
```

These should be helpers, decorators, or context managers. Users should not need to write raw OTel attributes for first-class adapters.

## Engine Readiness

The core engine is ready enough to continue with adapters.

Already useful checks:

1. `UNKNOWN_TOOL`
2. `DENIED_TOOL_CALL`
3. `DISALLOWED_TOOL_ARGUMENT`
4. `MISSING_APPROVAL`
5. `APPROVAL_AFTER_ACTION`
6. `ACTION_AFTER_DENIAL`
7. `APPROVAL_MISMATCH`
8. `PRIVATE_TO_PUBLIC_SINK`
9. `SECRET_EXPOSURE`
10. `UNTRUSTED_TO_PRIVILEGED_ACTION`
11. `SENSITIVE_FINAL_ANSWER`
12. `UNSUPPORTED_CLAIM`
13. `INVALID_PROVENANCE_REFERENCE`
14. `EVIDENCE_AFTER_CLAIM`
15. Structural trace errors.

Do not wait for a perfect analyzer before building adapters. The existing checks are enough to make a first-class adapter valuable.

## Milestone 8: Capture Completeness Reporting

Capture completeness is now implemented as the dedicated prerequisite milestone before the next framework adapter. The implementation results are recorded in `Documents/milestone_8_build_report.md`.

Reports should say what was actually captured:

```text
Capture coverage

Agent runs: captured
Model calls: captured
Tool calls: captured
Tool arguments: captured
Tool results: captured
Approvals: unavailable
Data flow: partial
Claim provenance: unavailable
```

A passing report with incomplete capture should not imply full verification.

Example wording:

```text
Policy checks passed for the behavior represented in the trace.
Approval and provenance coverage were not available.
```

Minimum statuses:

```text
captured | partial | unavailable | unknown
```

`unknown` is required for native or third-party traces that make no trustworthy completeness declaration. Completeness is stored per trace, included in adapter results, and rendered in report schema v2.

## Recommended Next Milestone

Milestone 9 is implemented and a live OpenAI Agents SDK run has validated the capture, import, and policy-check path. The next milestone is:

```text
M10: Semantic Capture and Verifiability
```

M10 is implemented. It maps configured policy constructs to minimum evidence requirements, adds a `not_verifiable` outcome, enforces it in CLI and pytest, and provides focused approval, source/sink flow, and final-output helpers. Results are recorded in `Documents/milestone_10_build_report.md`.

The scope review after M10 defines the next milestone as:

```text
M11: Scope Alignment and Developer Workflow
```

M11 is implemented. It consolidates the offline deterministic product with a compiled rule plan shared by evaluation and evidence assessment, focused rule activation, report v4 explicit diagnostic paths, context-aware semantic helpers, and consumer workflow verification. See `Documents/milestone_11_scope_alignment_implementation_plan.md` and `Documents/milestone_11_build_report.md`.

Generic command wrapping remains deferred. The supported pytest and one-line in-process workflows should become complete before cross-platform child-process injection is designed.

## Pytest Direction

A pytest plugin should be part of the first-class adapter story.

Target behavior:

1. Start capture at test-session startup.
2. Associate traces with pytest node IDs.
3. Flush traces after each relevant test.
4. Attach AgentLint diagnostics to failed tests.
5. Avoid changes to ordinary tests.
6. Work with async tests where possible.
7. Handle test parallelization explicitly or document limitations.

Target usage:

```bash
pytest --agentlint
```

or:

```bash
agentlint check --command "pytest"
```

## Failure Behavior

AgentLint should fail clearly when:

1. No supported agent traces were captured.
2. The requested adapter was not activated.
3. The framework version is unsupported.
4. Tracing was disabled.
5. Trace flushing failed.
6. Mandatory capture coverage is missing.
7. The child command exits before traces are collected.

It must not silently report zero violations when no meaningful trace was captured.

## OpenTelemetry Role Going Forward

OpenTelemetry remains valuable, but as:

1. An advanced importer.
2. A fallback for unsupported frameworks.
3. A useful internal/export format.
4. A demo and integration layer for users already running OTel.

It should not be positioned as equivalent to a first-class framework adapter.

## OpenAI Agents Live Demo

After fixture-based adapter support exists, add an optional live demo:

1. Require `OPENAI_API_KEY`.
2. Use a cheap model.
3. Use local tools only.
4. Avoid web search, code interpreter, file search, images, audio, and hosted tools.
5. Keep prompts and outputs small.
6. Do not run live tests in default pytest.
7. Mark any live tests explicitly.

Budget target:

```text
Routine tests: $0
Optional live demo: cents
Hard budget: less than $5
```

## Practical Roadmap

1. Evaluate policy-declared result-source and argument-sink boundaries against additional real OpenAI Agents projects and policies.
2. Measure false-positive, false-negative, annotation, and not-verifiable outcomes.
3. Measure whether explicit diagnostic paths reduce debugging time.
4. Complete M12 research evaluation using representative traces and hand-labeled outcomes.
5. Evaluate LangGraph only after the M11 workflow evidence is reviewed.
6. Keep OPA/Rego deferred until a concrete policy-language limitation appears.

## Product Promise

For supported frameworks:

```text
Install the adapter, define your policy, and run your existing tests.
AgentLint captures and checks the agent execution automatically.
```

For advanced semantic checks:

```text
Annotate only the sensitive boundaries the framework cannot understand on its own.
```

This promise is intentionally bounded. AgentLint verifies represented tool contracts, approval records, explicit data-flow paths, and explicit provenance relationships. It does not initially authorize actions, collect approvals, reconstruct arbitrary program data flow, or judge the semantic truth of final answers.
