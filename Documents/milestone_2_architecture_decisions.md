# Milestone 2 Architecture Decisions

Decision date: 2026-06-30

Status: finalized for Milestone 2 implementation.

This document records the resolved architecture decisions for Milestone 2. Brainstorming notes are intentionally omitted; this is the implementation baseline.

## Research Basis

Local sources reviewed:

1. `Documents/milestone_2_implementation_plan.md`
2. `Documents/milestone_1_research.md`
3. `Documents/milestone_1_build_report.md`
4. `Documents/architecture.md`
5. `Documents/requirements_specification.md`
6. `src/agentlint/ir/v1/models.py`
7. `src/agentlint/ir/v1/loaders.py`
8. `src/agentlint/cli.py`

Primary implementation references reviewed:

1. Pydantic validators: https://docs.pydantic.dev/latest/concepts/validators/
2. Pydantic validation errors: https://docs.pydantic.dev/latest/errors/errors/
3. Pydantic model config: https://docs.pydantic.dev/latest/api/config/
4. Typer testing: https://typer.tiangolo.com/tutorial/testing/

## Final Decision Summary

1. Pydantic remains responsible for JSON/schema shape.
2. AgentLint structural passes are responsible for trace relationship correctness.
3. IR v1 must be relaxed enough to represent structurally invalid traces.
4. Milestone 2 diagnostics use stable string enum codes and severities.
5. `agentlint validate` runs schema validation first, then structural validation.
6. Milestone 2 keeps event-level relationships and continues deferring the full value graph.
7. Milestone 2 provides a lightweight diagnostic formatter, not a report subsystem.

## ADR-001: Schema Validation And Structural Validation Boundary

Decision:

Schema validation and structural validation are separate stages.

Pydantic schema validation owns:

1. Malformed JSON after loader parsing.
2. Required fields needed to instantiate IR objects.
3. Invalid primitive field types.
4. Unknown event and edge types.
5. Unknown fields outside explicit extension fields such as `metadata`.
6. Non-empty identifier field shape.
7. Strict integer event sequences.

AgentLint structural validation owns:

1. Duplicate event IDs.
2. Duplicate edge IDs.
3. References to missing events.
4. Tool call/result relationship consistency.
5. Missing tool call arguments.
6. Invalid structural ordering.
7. Invalid final-answer evidence references.

Reasoning:

Milestone 2 requires stable diagnostic codes and related event IDs. If Pydantic rejects relationship errors before a `Trace` exists, AgentLint cannot emit structural diagnostics. Pydantic should therefore validate object shape, while AgentLint validates trace semantics.

Consequences:

1. `Trace` must preserve event and edge lists even when IDs are duplicated.
2. Relationship checks currently implemented as Pydantic validators should move to `agentlint.passes.structural`.
3. Loader schema errors and structural diagnostics remain visibly different in CLI output.

## ADR-002: IR V1 Relaxations Needed For Diagnostics

Decision:

IR v1 should be relaxed only where necessary to represent Milestone 2 structural violations.

Required model changes:

1. Remove duplicate event ID rejection from `Trace`.
2. Remove duplicate edge ID rejection from `Trace`.
3. Remove edge endpoint existence checks from `Trace`.
4. Change `ToolCallEvent.arguments` to `dict[str, JsonValue] | None = None`.
5. Add `Claim.evidence: list[str] = Field(default_factory=list)`.

Fields that remain schema-required:

1. Event `id`, `type`, and `sequence`.
2. Edge `id`, `type`, `from_event`, and `to_event`.
3. User message `content`.
4. Developer instruction `content`.
5. Model call `input`.
6. Tool call `tool_name`.
7. Tool result `tool_name` and `result`.
8. Final answer `content`.
9. Claim `id` and `text`.

Reasoning:

Milestone 2 cannot diagnose a missing `tool_call.arguments` field if the event cannot be parsed. But a missing event `id` cannot be usefully diagnosed as a relationship problem because the event cannot participate in a stable graph. The boundary should relax only fields needed for structural checks.

Consequences:

1. Existing model tests that expect duplicate or missing-edge-reference Pydantic errors must move to structural pass tests.
2. Schema tests should continue covering invalid event types, invalid primitive types, unknown fields, and missing object-shape fields.
3. Empty tool arguments `{}` are structurally valid. Tool-specific required argument names remain future policy/tool-schema work.
4. Optional reference strings such as `call_id`, `subject_event`, and claim evidence entries should be non-empty when present.

## ADR-003: Diagnostic Model

Decision:

Milestone 2 diagnostics use a Pydantic model and Python 3.12 `StrEnum` values.

Model shape:

```python
class Severity(StrEnum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class DiagnosticCode(StrEnum):
    DUPLICATE_EVENT_ID = "DUPLICATE_EVENT_ID"
    DUPLICATE_EDGE_ID = "DUPLICATE_EDGE_ID"
    MISSING_EVENT_REFERENCE = "MISSING_EVENT_REFERENCE"
    TOOL_RESULT_WITHOUT_MATCHING_CALL = "TOOL_RESULT_WITHOUT_MATCHING_CALL"
    TOOL_CALL_MISSING_ARGUMENTS = "TOOL_CALL_MISSING_ARGUMENTS"
    INVALID_EVENT_ORDER = "INVALID_EVENT_ORDER"
    INVALID_EVIDENCE_REFERENCE = "INVALID_EVIDENCE_REFERENCE"


class Diagnostic(BaseModel):
    code: DiagnosticCode
    severity: Severity = Severity.ERROR
    message: str
    related_events: list[str] = Field(default_factory=list)
    related_edges: list[str] = Field(default_factory=list)
    policy_reference: str | None = None
    remediation: str | None = None
```

Reasoning:

`StrEnum` gives stable code-addressable values while preserving string-like behavior. Pydantic gives predictable serialization and validation for future report consumers.

Consequences:

1. Use `model_dump(mode="json")` in tests when asserting serialized diagnostics.
2. Milestone 2 emits only `error` diagnostics.
3. `warning` and `info` exist now to avoid reshaping diagnostics when policy severity overrides arrive later.
4. Source references are not embedded in diagnostics yet; related event and edge IDs are enough for Milestone 2.

## ADR-004: Diagnostic Formatting Before Reports

Decision:

Milestone 2 adds lightweight diagnostic formatting under `agentlint.diagnostics`, not full report generation.

Formatting target:

```text
error[DUPLICATE_EVENT_ID]: duplicate event id "evt_1"
  related events: evt_1
  remediation: Ensure every event id is unique within the trace.
```

Reasoning:

Milestone 2 needs readable validation output, but Milestone 5 owns report formats, summaries, JSON output, redaction policy, and CI threshold behavior. A small formatter keeps implementation focused and can later feed report emitters.

Consequences:

1. Do not create JSON report output in Milestone 2.
2. Do not add `--format` or `--fail-on`.
3. Avoid printing raw trace payload values in diagnostic formatting.

## ADR-005: Structural Pass Module Ownership

Decision:

The structural validation pass lives in:

```text
src/agentlint/passes/structural.py
```

Public API:

```python
def validate_structure(trace: Trace) -> list[Diagnostic]:
    ...
```

Reasoning:

The architecture already reserves `passes/` for validation and analysis passes. Structural validation is the first real pass and should not live in the loader, CLI, diagnostics, or IR packages.

Consequences:

1. The loader returns parsed IR only.
2. The CLI orchestrates load, pass execution, formatting, and exit code.
3. Future enrichment and policy checks can follow the same pass pattern.

## ADR-006: Structural Diagnostic Codes And Exact Scope

Decision:

Milestone 2 implements these diagnostic codes:

1. `DUPLICATE_EVENT_ID`
2. `DUPLICATE_EDGE_ID`
3. `MISSING_EVENT_REFERENCE`
4. `TOOL_RESULT_WITHOUT_MATCHING_CALL`
5. `TOOL_CALL_MISSING_ARGUMENTS`
6. `INVALID_EVENT_ORDER`
7. `INVALID_EVIDENCE_REFERENCE`

Scope details:

1. `DUPLICATE_EVENT_ID` is emitted once per duplicated event ID.
2. `DUPLICATE_EDGE_ID` is emitted once per duplicated edge ID.
3. `MISSING_EVENT_REFERENCE` is emitted once per invalid reference site and covers missing edge endpoints and missing `approval.subject_event`.
4. `TOOL_RESULT_WITHOUT_MATCHING_CALL` is emitted once per invalid tool result and covers absent `call_id`, missing referenced call, referenced non-tool-call event, and tool-name mismatch.
5. `TOOL_CALL_MISSING_ARGUMENTS` covers `arguments is None`, not empty `{}`.
6. `INVALID_EVENT_ORDER` covers backward edges and tool results that occur before or at the same sequence as their matching tool call.
7. `INVALID_EVIDENCE_REFERENCE` is emitted once per invalid claim evidence reference and covers `Claim.evidence` IDs that do not resolve to events.

Reasoning:

This set matches the Milestone 2 roadmap while preserving policy/provenance checks for later milestones.

Consequences:

1. One fixture should exist for each code.
2. Tests should assert both code and relevant event or edge IDs.
3. `INVALID_EVIDENCE_REFERENCE` is distinct from `MISSING_EVENT_REFERENCE` because evidence references are claim/provenance-specific and should remain easy to separate later.

## ADR-007: Reference Handling And Ambiguous IDs

Decision:

Structural validation detects duplicates before building lookup maps. Lookup maps should include only IDs that appear exactly once.

Reasoning:

If an ID appears multiple times, any reference to it is ambiguous. Producing follow-on diagnostics based on an arbitrary duplicate target would make output unstable and misleading.

Consequences:

1. Duplicate diagnostics are emitted first.
2. Reference checks may skip references to duplicated IDs to avoid cascading noise.
3. Missing-reference diagnostics are reserved for IDs that do not appear at all.
4. Diagnostic ordering must be deterministic.

Recommended ordering:

1. Duplicate event IDs.
2. Duplicate edge IDs.
3. Missing event references.
4. Tool call argument issues.
5. Tool result matching issues.
6. Event ordering issues.
7. Evidence reference issues.

## ADR-008: Event Ordering Semantics

Decision:

Milestone 2 uses `sequence` as the only ordering source.

Rules:

1. Edge `from_event.sequence` must be less than or equal to `to_event.sequence`.
2. Tool result sequence must be greater than matching tool call sequence.
3. Sequence numbers do not need to be contiguous.
4. Sequence numbers do not need to be globally unique.
5. Timestamps are preserved but not used for ordering checks in Milestone 2.

Reasoning:

The IR already has `sequence`, and timestamps are optional. Requiring contiguous or unique sequence numbers would overconstrain traces from external systems and is not necessary for structural validation.

Consequences:

1. A same-sequence edge is allowed.
2. A same-sequence tool call/result pair is invalid because a result cannot structurally occur at the same moment as the call it returns from.
3. Evidence-after-claim ordering remains deferred to Milestone 4 unless evidence references become structurally impossible.
4. Tool result ordering is checked only after a valid unique matching tool call exists.

## ADR-009: Evidence Representation

Decision:

Milestone 2 represents explicit final-answer evidence with `Claim.evidence: list[str]`.

Rules:

1. Evidence entries are event IDs.
2. Missing evidence IDs produce `INVALID_EVIDENCE_REFERENCE`.
3. Empty evidence lists are allowed in Milestone 2.
4. Claims with no evidence do not produce `UNSUPPORTED_CLAIM` in Milestone 2.
5. Provenance edges remain event-to-event and are not claim-specific yet.

Reasoning:

This gives Milestone 2 a concrete way to validate nonexistent evidence references without implementing semantic provenance. Unsupported claims and evidence relevance require policy/provenance logic and belong later.

Consequences:

1. Passing structural fixtures should include at least one claim with valid evidence.
2. Failing fixtures should include one claim evidence ID that does not exist.
3. No value graph or claim-to-value graph is introduced.

## ADR-010: CLI Validation Flow

Decision:

`agentlint validate TRACE.json` runs schema validation and then structural validation.

Flow:

```text
load native trace
if schema/load error: print schema/load error and exit 1
run validate_structure(trace)
if error diagnostics exist: print diagnostics and exit 1
print trace summary with diagnostics: 0 and exit 0
```

Successful output:

```text
valid trace: trace_tool_flow_valid
events: 5
edges: 5
diagnostics: 0
```

Reasoning:

Milestone 2 should make `validate` a real trace validation command without adding the later `check` command or policy/report flags.

Consequences:

1. Schema errors and structural diagnostics have distinct output paths.
2. Structural diagnostics print to stderr.
3. No directory traversal or multiple-trace validation in Milestone 2.
4. No `--policy`, `--format`, or `--fail-on` flags in Milestone 2.

## ADR-011: Fixture And Test Strategy

Decision:

Keep Milestone 2 fixtures flat under `examples/traces/` and add structural fixture names.

Required fixtures:

1. `structural_valid_tool_flow.json`
2. `structural_duplicate_event_id.json`
3. `structural_duplicate_edge_id.json`
4. `structural_missing_event_reference.json`
5. `structural_tool_result_without_call.json`
6. `structural_tool_call_missing_arguments.json`
7. `structural_invalid_event_order.json`
8. `structural_invalid_evidence_reference.json`

Reasoning:

The project already uses `examples/traces/`. A flat layout is enough for Milestone 2 and avoids introducing fixture-corpus structure before Milestone 6.

Consequences:

1. Add parametrized tests mapping fixture path to expected diagnostic code.
2. Do not add golden output snapshots yet.
3. Do not add expected report files yet.

## ADR-012: Deferred Work

Decision:

These remain out of scope for Milestone 2:

1. Full value graph modeling.
2. Sensitivity, secrecy, trust, source, and sink labels.
3. Policy loading and policy severity overrides.
4. Tool-specific argument schemas.
5. Approval policy checks.
6. Unsupported claim detection.
7. Evidence relevance and contradiction checks.
8. JSON reports and CI threshold flags.
9. External adapters.
10. Runtime gating.

Reasoning:

Milestone 2 is the structural validation layer. These items require policy semantics, data-flow semantics, report contracts, adapter fidelity, or runtime behavior that belongs to later milestones.

## Implementation Checklist Impact

Before implementation starts, update the Milestone 2 plan and tests to reflect these finalized decisions:

1. Relationship validators move from IR model construction to `passes.structural`.
2. `ToolCallEvent.arguments` becomes optional.
3. `Claim.evidence` is added.
4. `approval.subject_event` missing references are covered by `MISSING_EVENT_REFERENCE`.
5. Diagnostics use `StrEnum`.
6. Structural diagnostics are formatted but not reported as JSON.
7. CLI tests should distinguish stdout success summaries from stderr errors and diagnostics.
