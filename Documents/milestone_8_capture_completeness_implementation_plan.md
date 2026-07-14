# Milestone 8 Implementation Plan: Capture Completeness Reporting

Status: implemented. See `Documents/milestone_8_build_report.md`.

## Goal

Make every AgentLint report state which parts of an execution were captured well enough to check, so a passing policy result cannot be mistaken for verification of behavior that the adapter never observed.

Milestone 8 is a reporting and trace-provenance milestone. It does not improve inference, reconstruct missing events, or make an incomplete trace complete.

## Why This Comes Before Another Framework Adapter

The OpenTelemetry adapter proved that external traces can enter the existing IR and checks, but it also exposed an important ambiguity: adapter warnings are printed during import and then lost when the normalized trace is checked later. A report can consequently say that all represented checks passed without saying that approvals, data flow, or provenance were unavailable.

The first-class OpenAI Agents adapter will have similar capability boundaries. Defining one adapter-independent completeness contract first prevents each adapter from inventing its own warning vocabulary and gives later adapters a stable reporting target.

## Final Architecture Decisions

### 1. Completeness Describes Capture, Not Safety

Capture completeness and policy diagnostics answer different questions:

1. Capture completeness: what evidence did the adapter observe and preserve?
2. Policy diagnostics: did the represented behavior violate the configured policy?

Completeness must not be encoded as ordinary safety diagnostics. A trace may have no policy violations while still having partial capture. Conversely, a trace with complete capture may contain violations.

### 2. Completeness Is Per Trace

Coverage belongs to each imported or captured trace because a report can contain traces from different adapters, framework versions, or capture sessions. The report summary may aggregate those profiles, but it must not replace the per-trace record.

### 3. Use Explicit Capability States

Each capability uses one of four states:

```text
captured     The adapter claims the capability was captured for the trace.
partial      Some relevant evidence was captured, but known gaps remain.
unavailable  The adapter or source format cannot provide the capability.
unknown      No trustworthy completeness declaration is available.
```

`unknown` is required for existing native traces and third-party producers that do not declare capture behavior. It must not be treated as `captured`. `unavailable` is a positive adapter claim that a capability could not be obtained.

Do not add a percentage score. The denominator for concepts such as approvals and data flow is generally unknowable, so a numeric score would imply unjustified precision.

### 4. Report a Fixed V1 Capability Set

The first completeness schema covers:

1. `agent_runs`
2. `model_calls`
3. `tool_calls`
4. `tool_arguments`
5. `tool_results`
6. `approvals`
7. `data_flow`
8. `provenance`
9. `final_answers`

The set is intentionally fixed and versioned. Adapters must not invent report keys. A later schema version may add framework guardrails, handoffs, retries, or richer value-level coverage after real adapter evidence justifies them.

### 5. Preserve Completeness Through Normalization

Add an optional typed `capture` field to the native `Trace` model. This is an additive IR v1 change: existing trace files remain valid, and traces without the field receive an `unknown` profile when checked.

The field contains:

```text
schema_version: agentlint.capture.v1
adapter: stable adapter identifier
adapter_version: optional adapter version
framework: optional source framework identifier
framework_version: optional source framework version
capabilities: fixed capability map
notes: sanitized, non-payload explanatory strings
```

Each capability entry contains `status` and an optional sanitized `reason`. Reasons may describe structural limitations, such as "OTel input contained no explicit approval attributes", but must not contain prompts, tool arguments, results, or other raw trace values.

An optional top-level field is preferable to an import sidecar because completeness must survive the existing `import -> normalized IR file -> check` workflow. It is preferable to an untyped metadata convention because reports and adapters need schema validation and stable enumeration.

Serialization of traces that do not contain capture metadata must omit the optional field rather than writing `capture: null`, preserving current normalized output where possible.

### 6. Adapter Results and Traces Share One Model

`AdapterResult` should expose `capture` and require it to match the profile attached to the normalized trace. A shared helper should attach the profile when constructing an adapter result so two copies cannot drift.

Adapter warnings remain for malformed or dropped source records. Completeness describes the overall capability boundary; warnings describe concrete import incidents. For example:

```text
coverage.tool_arguments = partial
warning = one tool span had invalid arguments JSON
```

### 7. Reports Carry Per-Run Coverage and an Aggregate Summary

Extend `TraceCheckResult` with a capture profile. Invalid inputs that cannot be parsed use an `unknown` profile with a sanitized reason.

Extend the report summary with counts of traces whose overall coverage is:

1. `captured`
2. `partial`
3. `unavailable`
4. `unknown`

The overall state is derived conservatively from the capability entries:

1. `unknown` if any capability is unknown.
2. Otherwise `unavailable` if any capability is unavailable.
3. Otherwise `partial` if any capability is partial.
4. Otherwise `captured`.

The aggregate is for scanning only. Consumers must use the capability map when deciding whether a particular check had enough evidence.

The JSON report schema changes from `agentlint.report.v1` to `agentlint.report.v2`. Adding completeness silently to v1 would violate the existing stable automation contract. Report v1 readers should fail clearly on v2 rather than misinterpret it.

### 8. Text Reports State the Verification Boundary

The text renderer should add a compact block for every trace:

```text
capture: partial (opentelemetry)
  agent runs: captured
  model calls: captured
  tool calls: captured
  tool arguments: partial - one or more arguments were unavailable
  tool results: captured
  approvals: unavailable - no explicit approval semantics
  data flow: partial - only explicit AgentLint edges were captured
  provenance: unavailable - no explicit claim provenance
  final answers: captured
```

When no diagnostics are produced and overall coverage is not `captured`, append:

```text
Policy checks passed for the behavior represented in the trace; incomplete capture limited verification.
```

Do not print raw adapter notes or source values.

### 9. Native Traces Default to Unknown, Not Complete

AgentLint cannot infer how a native trace file was produced. A hand-authored native trace may intentionally model only one event. Therefore absence of a capture declaration means `unknown` across all capabilities.

Curated fixtures may declare complete or intentionally partial profiles when the fixture author is making an explicit test claim.

### 10. OpenTelemetry Uses Conservative Static Rules Plus Observed Degradation

The generic OpenTelemetry adapter starts from this baseline:

| Capability | Baseline | Reason |
| --- | --- | --- |
| Agent runs | partial | Generic spans do not guarantee an agent-run boundary. |
| Model calls | partial | Only explicitly typed AgentLint model spans are recognized. |
| Tool calls | partial | Only explicitly typed AgentLint tool spans are recognized. |
| Tool arguments | partial | Arguments require a valid explicit JSON attribute. |
| Tool results | partial | Results require explicitly typed result spans. |
| Approvals | partial | Approvals require explicit AgentLint approval attributes. |
| Data flow | partial | Only explicit AgentLint data-flow edges are preserved. |
| Provenance | partial | Only explicit claims and provenance edges are preserved. |
| Final answers | partial | Only explicitly typed final-answer spans are recognized. |

An adapter may promote a capability to `captured` only when its source contract can justify exhaustiveness, not merely because one matching event was observed. Generic OpenTelemetry therefore remains mostly `partial`. Concrete parsing failures may degrade a capability from `captured` to `partial`, or from `partial` to `unavailable` when none of that capability can be represented.

### 11. Enforcement Is a Separate Follow-On Contract

Milestone 8 reports completeness but does not make incomplete capture fail `agentlint check`. Existing `--fail-on` continues to apply only to diagnostics.

Coverage enforcement needs policy-aware dependency mapping, for example that `missing_approval` depends on tool calls and approvals while `unsupported_claim` depends on final answers and provenance. Adding a global fail switch first would be either too weak or unnecessarily block unrelated checks.

Milestone 9 may add policy configuration such as:

```yaml
coverage:
  tool_calls: required
  approvals: required
  provenance: optional
```

Until then, incomplete coverage is always visible in text and JSON reports and cannot silently appear as complete.

## Implementation Work

### Phase 1: Capture Models

1. Add `src/agentlint/capture/models.py` with `CaptureStatus`, `CaptureCapability`, `CapabilityCoverage`, and `CaptureCompleteness`.
2. Add constructors for an all-unknown profile and conservative overall-state derivation.
3. Enforce fixed capability keys and sanitized, bounded reason strings.
4. Export the public capture models from `agentlint.capture`.
5. Add optional `capture` to `agentlint.ir.v1.Trace`.

### Phase 2: Adapter Integration

1. Add the shared capture profile to `AdapterResult` construction.
2. Populate a conservative OpenTelemetry profile.
3. Degrade relevant capability entries when records or fields are dropped.
4. Keep incident warnings and completeness reasons consistent without duplicating raw data.
5. Serialize the profile into normalized OpenTelemetry output.

### Phase 3: Checking and Reports

1. Copy trace capture metadata into `TraceCheckResult`.
2. Generate an unknown profile for traces without declarations and invalid inputs.
3. Add overall capture counts to `ReportSummary`.
4. bump the report schema to `agentlint.report.v2`.
5. Render per-trace coverage in text output.
6. Add the limited-verification sentence for passing traces with incomplete coverage.
7. Keep report redaction guarantees intact.

### Phase 4: Fixtures and Tests

1. Unit-test strict capture models and all overall-state combinations.
2. Test backward compatibility for native traces without `capture`.
3. Test capture round-tripping through OpenTelemetry import and native loading.
4. Test OpenTelemetry baseline coverage and degradation from invalid/dropped fields.
5. Update report model, renderer, CLI, golden report, and determinism tests for report v2.
6. Add privacy tests proving reasons and notes do not expose prompt, argument, result, or answer values.
7. Add a mixed multi-trace report test covering captured, partial, unavailable, and unknown profiles.
8. Keep every existing structural and policy diagnostic behavior unchanged.

### Phase 5: Documentation

1. Document the four statuses and fixed capability set.
2. Add a capability matrix for the OpenTelemetry adapter.
3. Explain that passing means "no violation found in represented behavior" rather than full-system verification.
4. Document report v2 migration for machine consumers.
5. Update example import and check output.

## Files Expected to Change

```text
src/agentlint/capture/__init__.py
src/agentlint/capture/models.py
src/agentlint/adapters/common.py
src/agentlint/adapters/opentelemetry.py
src/agentlint/ir/v1/models.py
src/agentlint/checking.py
src/agentlint/reports/models.py
src/agentlint/reports/renderers.py
src/agentlint/cli.py
tests/test_capture_models.py
tests/test_opentelemetry_adapter.py
tests/test_checking.py
tests/test_reports.py
tests/test_cli.py
tests/test_fixture_corpus.py
examples/expected_reports/*.json
Documents/*.md
README.md
```

## Compatibility and Migration

1. Existing native IR v1 inputs remain valid because `capture` is optional.
2. Existing adapter callers must consume the new completeness field but retain access to `trace` and `warnings`.
3. JSON report consumers must migrate from `agentlint.report.v1` to `agentlint.report.v2`.
4. Text output gains coverage lines and should continue to be treated as human-oriented rather than a parsing API.
5. Policy behavior and diagnostic codes do not change in this milestone.

## Risks and Mitigations

### Adapter Overclaiming

Risk: an adapter marks a capability captured because it observed one event, even though other events could be missing.

Mitigation: require capability claims to follow documented source guarantees. Observation alone can degrade confidence but cannot prove exhaustiveness.

### Unknown Versus Unavailable Confusion

Risk: users interpret unknown as proof that the capability was absent.

Mitigation: define unknown as no trustworthy declaration and unavailable as a known source limitation in models, docs, and renderers.

### Report Churn

Risk: adding fields breaks golden reports and downstream JSON consumers.

Mitigation: bump the report schema, update exact goldens once, and keep ordering deterministic.

### Sensitive Reasons

Risk: adapter explanations copy raw source values into reports.

Mitigation: permit only predefined or sanitized structural reasons, bound their length, and add forbidden-string tests.

### False Sense of Precision

Risk: users treat the aggregate state as a measurement of trace quality.

Mitigation: avoid percentages and document the aggregate as a scan aid, not a policy sufficiency decision.

## Verification Commands

```powershell
py -3.12 -m pytest
py -3.12 -m ruff check .
py -3.12 -m ruff format --check .
git diff --check
```

Manual verification should import one OpenTelemetry fixture, check the normalized trace in text and JSON formats, and confirm that the completeness profile survives both steps.

## Exit Criteria

Milestone 8 is complete when:

1. Every checked trace has a completeness profile in text and JSON reports.
2. Existing native traces remain loadable and report `unknown` when they make no capture declaration.
3. OpenTelemetry imports persist a conservative capability profile into normalized IR.
4. Adapter parsing incidents degrade the relevant capability and remain available as warnings.
5. Passing incomplete traces display the limited-verification statement.
6. JSON reports use `agentlint.report.v2` and deterministic updated goldens.
7. Completeness data cannot contain raw sensitive payload values.
8. Existing structural and policy checks retain their behavior.
9. The full test, lint, formatting, and diff checks pass.

## Deferred Points

1. Policy-specific required coverage and CI failure behavior.
2. Mapping each diagnostic rule to its required capture capabilities.
3. Automatic completeness claims for the OpenAI Agents SDK.
4. Framework-version compatibility enforcement.
5. Runtime or partial-trace completeness.
6. Value-level and field-level completeness.
7. Numeric coverage scoring.
8. Cross-trace capture-session health and collector flush guarantees.
