# Milestone 10 Implementation Plan: Semantic Capture and Verifiability

## Status

Final implementation plan after reviewing the Milestone 8 capture contract, Milestone 9 OpenAI Agents integration, current policy evaluator, report schema, pytest plugin, live SDK output, and deferred adapter work.

This milestone supersedes the roadmap's proposed Milestone 10 OPA/Rego experiment. OPA remains a possible later experiment, but it does not address the current product risk: a policy check can find no violation even when evidence required to evaluate that policy was unavailable.

## Goal

Make AgentLint distinguish these outcomes for each trace:

1. `passed`: required evidence was captured at the policy's required level and no enabled check found a violation.
2. `failed`: captured evidence demonstrates one or more structural or policy violations.
3. `not_verifiable`: the trace is structurally valid, but required evidence was not captured at the level needed to support a pass.
4. `invalid`: the trace could not be loaded or is structurally incoherent.

The milestone must also provide supported OpenAI Agents users with focused helpers for semantics that framework tracing cannot expose: approval decisions, source/sink flow declarations, and authoritative final output.

## User Outcome

The primary workflow remains:

```powershell
pytest --agentlint --agentlint-policy agentlint.yaml
```

The result must fail CI when:

1. Captured behavior violates policy.
2. A trace is invalid.
3. Evidence required by the policy is unavailable or below the configured minimum.
4. Capture was requested but no supported trace was captured.

Users should not instrument ordinary agent runs, model calls, function-tool calls, handoffs, or guardrails. They annotate only application semantics the SDK cannot know.

## Evidence Model Decision

### Keep Capture Completeness Separate from Diagnostics

Missing evidence is not proof of a policy violation. AgentLint must not emit `MISSING_APPROVAL`, `PRIVATE_TO_PUBLIC_SINK`, or another behavioral diagnostic merely because capture is incomplete.

Instead, checking produces an evidence assessment alongside diagnostics. The trace status is selected in this order:

```text
invalid structure/input
  -> invalid
behavioral diagnostics
  -> failed
unmet evidence requirements
  -> not_verifiable
otherwise
  -> passed
```

If a trace has both a known violation and incomplete evidence, its status is `failed`, while the report still lists unmet evidence requirements. This preserves the strongest known conclusion without hiding uncertainty.

### Do Not Put Verifiability Behind `--fail-on`

`--fail-on` controls diagnostic severity thresholds. It must not turn `invalid` or `not_verifiable` traces into successful CI runs. `report_should_fail()` will return true when any trace is invalid or not verifiable, or when diagnostics cross the selected threshold.

### Use Minimum Coverage Per Capability

A flat list of required capabilities is ambiguous because M8 defines four coverage levels. Add a policy capture contract with explicit minimum levels:

```yaml
version: 1
policy_id: customer_support

capture:
  require:
    tool_calls: captured
    tool_arguments: partial
    approvals: partial
```

Allowed requirement values are:

```text
partial | captured
```

`unavailable` and `unknown` are observations, not meaningful minimum requirements. Coverage satisfies a requirement as follows:

| Required | Captured observation | Partial observation | Unavailable/unknown |
|---|---:|---:|---:|
| `partial` | yes | yes | no |
| `captured` | yes | no | no |

Explicit requirements may strengthen inferred requirements but may not weaken them.

## Policy-to-Evidence Requirements

AgentLint will compile evidence requirements from the policy before evaluation. Requirements are based on policy constructs that can actually produce a conclusion, not on every rule's default severity in isolation.

### Inferred Requirements

1. A non-empty tool inventory or enabled unknown/authorization tool checks requires `tool_calls: partial`.
2. Any tool argument constraint requires `tool_arguments: partial` and `tool_calls: partial`.
3. Any tool with `approval: required` requires `approvals: partial` and `tool_calls: partial`.
4. Configured source and sink policies with an enabled data-flow rule require `data_flow: partial`.
5. Secret or sensitive exposure checks that inspect tool payloads additionally require `tool_arguments: partial` or `tool_results: partial`, according to the evaluated sink surface.
6. Enabled final-answer sensitivity checks with relevant source policy require `final_answers: partial` and `data_flow: partial`.
7. Enabled provenance checks require `provenance: partial` and `final_answers: partial`.
8. Agent-run capture is not automatically required by policy v1 checks because current checks operate on events; users may require it explicitly.
9. Model-call capture remains explicitly configurable and is not inferred until a policy rule consumes model calls.

The implementation must encode this mapping in one tested policy compilation module. It must not scatter capture decisions across individual policy check functions.

### Conservative Scope

`partial` means checks can evaluate represented, explicitly captured semantics. It does not prove application-wide absence of unannotated flows or approvals. Documentation and report language must retain this limitation.

A user may require `captured` when their integration provides an exhaustive guarantee. OpenAI Agents M10 helpers will generally improve affected capabilities from `unavailable` to `partial`; they must not claim exhaustive coverage merely because one helper event exists.

This choice prevents the current OpenAI adapter's conservative whole-framework `tool_calls: partial` declaration from making every function-tool policy unusable. A policy that must prove exhaustive observation across function, hosted, computer-use, and other tool families must explicitly require `tool_calls: captured`; it will remain not verifiable until an adapter can make that guarantee.

## Data Model Changes

### Policy Models

Add to `src/agentlint/policy/models.py`:

1. `EvidenceRequirementLevel` with `partial` and `captured`.
2. `CaptureRequirements` with a fixed mapping over M8 `CaptureCapability` names.
3. Optional `capture` on `Policy`, defaulting to an empty requirement declaration.

Keep policy version `1`. This is an additive optional field, so existing policies remain valid and strict unknown-field rejection remains intact.

Reject:

1. Unknown capability names.
2. `unknown` or `unavailable` as required levels.
3. Empty or malformed requirement values.

### Checking Models

Add:

1. `TraceCheckStatus.NOT_VERIFIABLE = "not_verifiable"`.
2. `EvidenceRequirement` containing capability, required level, observed status, origin, and a sanitized reason.
3. `EvidenceAssessment` containing effective requirements and unmet requirements.
4. `evidence` on every `TraceCheckResult`.

Requirement origin is one of:

```text
inferred | explicit | inferred_and_explicit
```

No evidence model may include raw model inputs, tool arguments, tool results, approval reasons, or final-answer text.

### Report Contract

The check result shape changes, so bump the report schema from `agentlint.report.v2` to `agentlint.report.v3`.

Add to summary:

1. `not_verifiable` trace count.
2. Aggregate unmet requirement counts by capability.

Text output example:

```text
traces: 0 passed, 0 failed, 1 not verifiable, 0 invalid

trace: trace.json
status: not_verifiable
unmet evidence requirements:
  approvals: requires partial, observed unavailable
```

Passing incomplete traces may still display general capture limitations, but they pass only when those limitations are unrelated to effective policy requirements.

## Checking Pipeline

Implement the pipeline in this order:

1. Load and validate the trace.
2. Run structural validation.
3. Compile inferred and explicit evidence requirements from the policy.
4. Compare requirements with the trace capture declaration.
5. Run policy evaluation when structure is valid.
6. Preserve all known behavioral diagnostics even when evidence is incomplete.
7. Derive final status using the precedence defined above.
8. Build report v3 and determine process exit.

This milestone does not suppress policy diagnostics when evidence is incomplete. A captured violation remains useful evidence. Future rule-level tri-state evaluation may suppress conclusions that logically require absent inputs, but M10 will avoid that larger evaluator rewrite.

## Semantic Capture API

### Reuse the Existing OpenAI Capture Session

The current `OpenAICaptureSession.record_approval()` and `record_result()` methods are the starting point. Stabilize and document them rather than creating a second global instrumentation system.

### Approval Recording

Provide a public helper with explicit trace and subject linkage:

```python
session.record_approval(
    trace_id,
    subject_event=tool_call_event_id,
    decision="approved",
)
```

M10 must improve usability by exposing the AgentLint event ID associated with a captured function call, or by allowing a stable SDK tool-call ID that the adapter resolves to the normalized call event. Users must not guess generated `span_id:call` identifiers.

Do not infer approval from a guardrail pass, user message, or tool execution. None is an authoritative approval decision.

### Final Output Recording

Keep `session.record_result(trace_id, result)` and add supported run wrappers:

```python
result = await session.run(Runner, agent, input="...")
result = session.run_sync(Runner, agent, input="...")
```

The wrapper delegates to the SDK, records `RunResult.final_output`, returns the original result unchanged, and does not alter agent behavior. If reliable trace-ID association cannot be obtained from the SDK context, retain explicit `record_result()` as the supported path and document the wrapper as deferred rather than correlating by timing.

### Source, Sink, and Data-Flow Declarations

Add explicit session methods rather than pretending to track arbitrary Python values:

```python
source_id = session.record_source(
    trace_id,
    name="customer_profile",
    sensitivity="private",
    trust="trusted",
)

session.record_sink(
    trace_id,
    name="external_search.query",
    visibility="public",
    target_event=tool_call_id,
    source_events=[source_id],
)
```

The captured snapshot gains versioned AgentLint semantic span types that normalize to existing source/sink metadata and `data_flow` edges. Prefer explicit event declarations over Python object tainting in M10.

Do not implement implicit value tracking, monkeypatching, bytecode inspection, or equality-based payload correlation. Those approaches are intrusive, unreliable, and likely to retain sensitive values.

### Redaction

Semantic helpers record labels, stable IDs, classifications, and relationships only. They must not persist source values or sink payloads. Existing SDK sensitive-data settings remain independent and documented.

## OpenAI Agents Hardening

Expand fixture coverage for:

1. Failed function tools.
2. Failed model responses.
3. Multiple traces in one process.
4. Multiple agents and handoffs.
5. Guardrail pass and trip outcomes.
6. Retries and repeated tool calls.
7. Missing tool arguments when sensitive-data capture is disabled.
8. Missing tool results after failure or interrupted capture.
9. Explicit approval, source/sink, data-flow, and final-answer semantic records.
10. Unknown SDK span types and transparent container behavior.
11. Supported and unsupported SDK versions.
12. Snapshot writes and shutdown under partial failures.

The existing SDK version gate remains explicit. Do not silently accept an untested future minor version as fully supported.

## Realistic Example

Add `examples/openai_agents/customer_support/` containing:

1. A small OpenAI Agents customer-support agent.
2. `lookup_status`, allowed without approval.
3. `issue_refund`, allowed only with prior approval.
4. A private `customer_profile` source.
5. A public or external sink demonstrating declared data flow.
6. A policy declaring both behavioral rules and evidence requirements.
7. Offline fixture-based passing and failing checks.
8. Optional live tests gated by `OPENAI_API_KEY`.

Required scenarios:

1. Known low-risk tool passes.
2. Unknown tool fails.
3. Refund without approval fails when approval evidence is represented.
4. Approval requirement with unavailable capture is `not_verifiable`, not a clean pass.
5. Approved refund passes at the policy's configured minimum coverage.
6. Private-to-public declared flow fails.
7. Missing data-flow coverage is `not_verifiable` when required.
8. Final-output checks use the authoritative recorded result.

Keep default tests offline and zero-cost. Live examples must state their expected API use and remain opt-in.

## CLI and Pytest Behavior

### Existing `check` Command

`agentlint check` must render and serialize report v3, include unmet evidence requirements, and exit nonzero for `not_verifiable` regardless of `--fail-on`.

### Pytest Plugin

The plugin must:

1. Continue requiring explicit `--agentlint` activation.
2. Load policy before or during session setup so configuration errors fail early.
3. Capture all traces in the test session.
4. Import and check each completed snapshot.
5. Associate trace results with pytest node IDs where available.
6. Fail the pytest session for policy threshold failures, invalid traces, empty capture, or not-verifiable results.
7. Print a concise terminal summary and snapshot/report locations.
8. Avoid API calls unless the user's tests make them.

### Combined Non-Pytest Command

A generic `agentlint run -- <command>` wrapper remains deferred. Reliable child-process injection on Windows and cross-platform process lifecycle management require a separate design. M10 should make the supported pytest and one-line in-process paths complete first.

## Implementation Work Packages

### B10.1 Policy Evidence Contract

1. Add policy capture requirement models.
2. Add YAML loader validation tests.
3. Add representative policy fixtures.
4. Document additive policy v1 compatibility.

### B10.2 Requirement Compiler

1. Create a framework-independent policy-to-evidence compiler.
2. Merge inferred and explicit requirements using the stricter level.
3. Produce deterministic requirement ordering and origins.
4. Test every policy construct and rule-severity interaction.

### B10.3 Tri-State Check Outcome

1. Add evidence assessment models.
2. Add `not_verifiable` status.
3. Integrate evidence comparison into `check_trace()`.
4. Preserve behavioral diagnostics under incomplete capture.
5. Test precedence among failed, not verifiable, invalid, and passed.

### B10.4 Report v3

1. Bump the report schema.
2. Add not-verifiable and unmet-capability summaries.
3. Update text and JSON rendering.
4. Update `report_should_fail()` independently of `fail-on`.
5. Regenerate golden reports and fixture manifest expectations.

### B10.5 Semantic Snapshot Records

1. Define version-compatible explicit semantic span records.
2. Normalize approvals with stable subject resolution.
3. Add source, sink, and data-flow records without raw values.
4. Stabilize final-answer recording.
5. Degrade completeness deterministically when records are malformed or missing.

### B10.6 OpenAI Session API

1. Expose stable helper methods.
2. Resolve tool call identifiers safely.
3. Evaluate reliable `Runner` result wrapping.
4. Preserve additive and local-only processor modes.
5. Test flush, close, duplicate activation, and failure paths.

### B10.7 Pytest Enforcement

1. Enforce not-verifiable outcomes.
2. Improve per-test trace association in output.
3. Test passing, violation, unavailable evidence, invalid capture, and no-trace sessions.
4. Keep plugin activation explicit and default suite offline.

### B10.8 Customer-Support Example

1. Add policy, agent, tools, semantic capture, and fixtures.
2. Add offline regression tests.
3. Add optional budget-conscious live instructions.
4. Document exactly which conclusions are and are not supported.

### B10.9 Documentation and Roadmap

Update:

1. `README.md`.
2. `Documents/architecture.md`.
3. `Documents/requirements_specification.md`.
4. `Documents/adapters and instrumentation.md`.
5. `Documents/next steps.md`.
6. `Documents/milestones.md`.
7. `Documents/research_note.md`.
8. A new Milestone 10 build report.

Move the OPA/Rego experiment to a later unnumbered/deferred item and renumber later roadmap milestones only if maintaining contiguous milestone numbers is necessary.

## Test Plan

### Unit Tests

1. Requirement-level ordering and satisfaction.
2. Inferred requirement mapping for every relevant policy construct.
3. Explicit and inferred requirement merging.
4. Unknown capability and invalid-level rejection.
5. Status precedence.
6. Report v3 counts and process failure.
7. Semantic helper validation and redaction.
8. Adapter completeness upgrades and degradation.

### Integration Tests

1. Native trace plus policy with satisfied evidence.
2. Native trace plus missing required evidence.
3. OpenAI snapshot with tool-only policy.
4. OpenAI snapshot with approval-required policy and no approval capture.
5. OpenAI snapshot with explicit approval capture.
6. Declared private-to-public flow.
7. Recorded final output and provenance limitation.
8. Pytest subprocess outcomes for pass, fail, not verifiable, invalid, and empty capture.

### Regression Tests

1. Existing policies without `capture` still load.
2. Existing trace files remain valid.
3. Existing behavioral diagnostic codes and messages remain stable unless report schema serialization changes require fixture updates.
4. OpenTelemetry and OpenAI imported capture declarations survive round trips.
5. Metadata-only reports contain no raw values.
6. Complete suite passes on Python 3.12.
7. Ruff linting, Ruff formatting, and `git diff --check` pass.

## Compatibility and Migration

1. Native IR remains `agentlint.ir.v1` because event and edge concepts already support the semantic records after normalization.
2. Capture remains `agentlint.capture.v1`; M10 evaluates existing statuses without changing their meaning.
3. Policy remains version 1 with an optional additive field.
4. Report schema becomes v3 because check statuses and report fields change.
5. Existing policies may become `not_verifiable` when their constructs infer evidence requirements that their traces do not declare. This is intentional correctness, but release notes must call it out as a CI behavior change.
6. Users can initially make requirements explicit and realistic for their integration; they cannot disable mandatory inferred evidence needed for an enabled policy conclusion.

## Risks and Mitigations

### Existing CI Begins Failing as Not Verifiable

This is expected when prior passes relied on missing evidence. Provide precise unmet-capability output, migration examples, and conservative inference tied only to configured policy constructs.

### Partial Coverage Is Misread as Exhaustive

Reports must state the configured minimum and observed level. Documentation must explain that `partial` validates represented annotations, not every possible application flow.

### Helpers Become Intrusive

Keep ordinary framework capture automatic. Require helpers only at approval, source/sink, and final-result boundaries that the SDK cannot expose.

### Incorrect Result-to-Trace Correlation

Do not correlate by wall-clock timing or "most recent trace." Ship a run wrapper only if the SDK provides reliable active trace identity; otherwise retain explicit trace association.

### Sensitive Data Leakage

Record semantic labels and IDs, never source values. Extend redaction tests to snapshots, normalized traces, reports, and exceptions.

### Status Proliferation Confuses Users

Use one fixed precedence and plain report language: violated, not verifiable, invalid, or passed. Keep capture status as supporting evidence rather than another check outcome.

## Explicit Deferrals

M10 does not include:

1. LangGraph or another framework adapter.
2. Generic command wrapping or automatic child-process injection.
3. Full Python value/taint tracking.
4. Automatic inference of sensitivity, trust, or approval intent.
5. Automatic claim-to-evidence extraction.
6. OPA/Rego integration.
7. SARIF, HTML, or hosted reporting.
8. Runtime blocking or approval gating.
9. Distributed trace correlation across services.
10. A claim that partial semantic annotations prove exhaustive application coverage.

## Exit Criteria

Milestone 10 is complete when:

1. Policies can declare minimum capture requirements.
2. AgentLint deterministically infers evidence needed by active policy constructs.
3. Unmet requirements produce `not_verifiable`, never a clean pass.
4. `not_verifiable` and invalid traces fail CLI and pytest regardless of diagnostic threshold.
5. Known policy violations remain visible even when other evidence is incomplete.
6. OpenAI users can record approvals, source/sink data-flow declarations, and authoritative final output without writing spans or AgentLint IR.
7. Semantic capture persists no raw source or sink values.
8. The customer-support example demonstrates pass, violation, and not-verifiable outcomes offline.
9. Optional live tests remain explicit and budget-conscious.
10. Existing native and adapter workflows remain compatible except for the documented stricter CI outcome.
11. Report v3 fixtures, documentation, and roadmap are current.
12. The full test suite and static checks pass.

## Recommended Build Order

Implement B10.1 through B10.4 first. This establishes the framework-independent correctness contract before adding more capture mechanisms. Then implement B10.5 and B10.6, followed by pytest enforcement and the realistic example. Documentation and fixture regeneration should be updated incrementally and finalized only after the complete workflow is verified.
