# Milestone 2 Implementation Plan

Status: implemented.

Milestone 2 proves the linter pipeline with structural trace validation and stable diagnostics.

Milestone 1 made native JSON traces load into AgentLint IR v1 and added schema-level validation. Milestone 2 should shift from "can this trace be parsed?" to "does this parsed trace have structurally coherent relationships?" It should not introduce policy YAML, tool authorization, data-flow policy, approval policy, provenance semantics, reports, or external adapters.

## Objective

Implement structural validation over AgentLint IR v1 traces.

Milestone 2 is complete when:

1. AgentLint has a diagnostics model with stable codes, severity, message, related events, optional policy reference, and remediation.
2. AgentLint has a structural validation pass that emits diagnostics for trace consistency failures.
3. `agentlint validate TRACE.json` loads a native trace, runs structural validation, prints human-readable diagnostics, and exits non-zero on structural errors.
4. Fixture traces exist for each structural diagnostic code.
5. Unit and fixture tests cover every structural violation and at least one passing trace.
6. Human-readable output is understandable without opening the raw trace.

## Current Baseline

Milestone 1 implemented:

1. `src/agentlint/ir/v1/models.py`
2. `src/agentlint/ir/v1/loaders.py`
3. `agentlint validate TRACE.json`
4. Native trace examples under `examples/traces/`
5. CLI, loader, and model tests

Milestone 1 validation currently rejects these at Pydantic construction time:

1. Duplicate event IDs.
2. Duplicate edge IDs.
3. Edge endpoints that reference missing events.

That was reasonable for IR construction in Milestone 1, but Milestone 2 requires stable diagnostic codes for structural problems. Therefore Milestone 2 should move these relationship checks out of Pydantic model construction and into the structural validation pass.

## Working Assumptions

1. Schema validation and structural validation are separate stages.
2. Schema validation should reject malformed JSON, unsupported event types, invalid field types, and required fields that are necessary to instantiate basic event objects.
3. Structural validation should emit AgentLint diagnostics for coherent but invalid trace relationships.
4. Structural diagnostics should be stable and code-addressable.
5. All Milestone 2 structural diagnostics should use severity `error`.
6. Policy-specific severity overrides begin in Milestone 3.
7. JSON report output and CI threshold flags begin in Milestone 5.
8. No external network calls are needed.

## Finalized Architecture Decisions

The Milestone 2 architecture decisions were reevaluated and finalized in `Documents/milestone_2_architecture_decisions.md`. The implementation plan below follows that decision record.

### A2.1 Move Relationship Checks Out Of Pydantic Construction

Decision:

Move duplicate ID and missing edge endpoint checks from `Trace` validators into `agentlint.passes.structural`.

Reasoning:

Milestone 2 requires diagnostics such as `DUPLICATE_EVENT_ID` and `MISSING_EVENT_REFERENCE`. If Pydantic rejects these before a `Trace` object exists, the structural pass cannot produce stable AgentLint diagnostics with related event IDs and remediation.

Implementation consequence:

1. Keep Pydantic field validation for field shape and primitive constraints.
2. Remove or relax `Trace.reject_duplicate_event_ids`.
3. Remove or relax edge endpoint validation in `Trace.validate_edges`.
4. Let `Trace` preserve lists exactly as authored.
5. Ensure downstream structural checks do not assume event IDs are unique until duplicate checks pass.
6. Treat `approval.subject_event` as an optional event reference checked by the structural pass.

### A2.2 Relax Tool Call Arguments Enough For Diagnostics

Decision:

Represent missing tool call arguments in the IR so the structural pass can emit `TOOL_CALL_MISSING_ARGUMENTS`.

Reasoning:

The Milestone 2 roadmap explicitly lists "tool calls with missing required arguments." If `ToolCallEvent.arguments` remains schema-required, missing arguments will remain a Pydantic validation error rather than an AgentLint diagnostic.

Implementation consequence:

Change `ToolCallEvent.arguments` from required to:

```python
arguments: dict[str, JsonValue] | None = None
```

The structural pass emits an error when a `tool_call` event has `arguments is None`.

An empty argument object `{}` should be allowed structurally. Tool-specific required argument validation belongs to policy or tool schema work later.

### A2.3 Add Explicit Claim Evidence References

Decision:

Extend `Claim` with explicit event-level evidence references:

```python
evidence: list[str] = Field(default_factory=list)
```

Reasoning:

Milestone 2 includes "final answers referencing nonexistent evidence." The current minimal `Claim` model has `id` and `text` but no way to reference evidence directly. Event-level evidence references are enough for structural validation and match the current event-to-event edge strategy.

Implementation consequence:

1. Add `Claim.evidence`.
2. Structural validation emits `INVALID_EVIDENCE_REFERENCE` if a claim evidence ID does not match an event ID.
3. Do not emit `UNSUPPORTED_CLAIM` for empty evidence yet. Unsupported claims belong to Milestone 4 provenance checks.
4. Optionally validate `EVIDENCE_AFTER_CLAIM` in Milestone 4, not Milestone 2, unless the evidence reference is structurally impossible.

### A2.4 Keep Full Value Graph Deferred

Decision:

Continue deferring full value graph modeling.

Reasoning:

Milestone 2 checks structural relationships, not private-to-public or untrusted-to-privileged flows. Event-level relationships are sufficient for duplicate IDs, missing references, tool call/result matching, ordering, and explicit evidence references.

Implementation consequence:

Do not add value nodes, value endpoints, sensitivity labels, trust labels, source labels, or sink labels in Milestone 2.

### A2.5 Diagnostics Before Reports

Decision:

Implement diagnostic models and a small terminal formatter, but do not build the report subsystem yet.

Reasoning:

Milestone 2 needs human-readable diagnostic output. Milestone 5 owns human-readable terminal reports, JSON reports, summary counts, and CI threshold behavior. A lightweight formatter in `diagnostics` is enough now and can later feed the report layer.

Implementation consequence:

Create:

```text
src/agentlint/diagnostics/models.py
src/agentlint/diagnostics/formatting.py
```

Do not create JSON report output yet.

### A2.6 Deterministic Structural Pass

Decision:

Detect duplicates before building lookup maps, and build event lookup maps only from IDs that appear exactly once.

Reasoning:

Duplicate IDs make references ambiguous. Structural diagnostics should be deterministic and should avoid cascading from arbitrary lookup targets.

Implementation consequence:

Emit diagnostics in this order:

1. Duplicate event IDs.
2. Duplicate edge IDs.
3. Missing event references.
4. Tool call argument issues.
5. Tool result matching issues.
6. Event ordering issues.
7. Evidence reference issues.

## Research Track

### R2.1 Diagnostic Model Shape

Questions:

1. Which fields are required for a useful structural diagnostic?
2. Should severity be a string literal or enum?
3. How should related events be represented?
4. How should remediation text be represented?
5. Should diagnostics include source references now?

Expected decision:

Use a Pydantic diagnostic model:

```python
class Diagnostic(BaseModel):
    code: DiagnosticCode
    severity: Severity
    message: str
    related_events: list[str] = Field(default_factory=list)
    related_edges: list[str] = Field(default_factory=list)
    policy_reference: str | None = None
    remediation: str | None = None
```

Use literals or enums for:

1. `Severity`: `error`, `warning`, `info`
2. `DiagnosticCode`: stable structural codes listed in R2.2

Final decision: use Python 3.12 `StrEnum` for `Severity` and `DiagnosticCode`. Source references can wait until report formatting needs them. Related event and edge IDs are enough for Milestone 2.

Output:

1. Final diagnostic model decision.
2. Tests that diagnostics serialize predictably.

### R2.2 Structural Diagnostic Codes

Questions:

1. Which diagnostic codes should Milestone 2 define?
2. Which current schema errors should become structural diagnostics?
3. Which checks should remain schema validation?

Expected decision:

Milestone 2 structural diagnostic codes:

1. `DUPLICATE_EVENT_ID`
2. `DUPLICATE_EDGE_ID`
3. `MISSING_EVENT_REFERENCE`
4. `TOOL_RESULT_WITHOUT_MATCHING_CALL`
5. `TOOL_CALL_MISSING_ARGUMENTS`
6. `INVALID_EVENT_ORDER`
7. `INVALID_EVIDENCE_REFERENCE`

Schema validation should still handle:

1. Malformed JSON.
2. Unknown event types.
3. Missing event `id`, `type`, or `sequence`.
4. Invalid primitive field types.
5. Unknown fields outside explicit extension fields.

Output:

1. Diagnostic code list in code and tests.
2. One failing fixture per code.

Scope note:

`MISSING_EVENT_REFERENCE` covers missing edge endpoints and missing `approval.subject_event`. Tool result `call_id` problems use `TOOL_RESULT_WITHOUT_MATCHING_CALL`. Claim evidence problems use `INVALID_EVIDENCE_REFERENCE`.

### R2.3 Tool Call And Tool Result Matching

Questions:

1. How should a tool result identify its matching tool call?
2. Is `tool_name` enough?
3. What should happen when `call_id` is missing?
4. What should happen when `call_id` points to a non-tool-call event?
5. Should a matching result occur after its call?

Expected decision:

Use `ToolResultEvent.call_id` as the precise structural link to a `ToolCallEvent.id`.

Rules:

1. If a `tool_result` has no `call_id`, emit `TOOL_RESULT_WITHOUT_MATCHING_CALL`.
2. If `call_id` does not reference an existing event, emit `TOOL_RESULT_WITHOUT_MATCHING_CALL`.
3. If `call_id` references an event that is not `tool_call`, emit `TOOL_RESULT_WITHOUT_MATCHING_CALL`.
4. If `call_id` references a tool call with a different `tool_name`, emit `TOOL_RESULT_WITHOUT_MATCHING_CALL`.
5. If the matching tool result sequence is before or equal to the tool call sequence, emit `INVALID_EVENT_ORDER`.

Output:

1. Tests for matched and unmatched tool results.
2. Fixture for unmatched tool result.
3. Fixture for invalid tool result ordering.

### R2.4 Event Ordering Rules

Questions:

1. Which ordering rules are structural rather than policy?
2. How should ordering work when duplicate sequences exist?
3. Should sequences need to be contiguous?
4. Should timestamps matter?

Expected decision:

Use `sequence` as the authoritative Milestone 2 ordering field.

Structural ordering rules:

1. For every edge, `from_event.sequence` should be less than or equal to `to_event.sequence`.
2. For `parent`, `data_flow`, `approval_for`, and `provenance`, a non-backward edge is expected.
3. For tool call/result matching, the result must have a greater sequence than its call.
4. Evidence references in claims should point to prior or same-sequence events only if implemented as part of `INVALID_EVENT_ORDER`; otherwise defer evidence-after-claim to Milestone 4.

Recommended Milestone 2 boundary:

1. Do not require contiguous sequence numbers.
2. Do not require globally unique sequence numbers.
3. Do not use timestamps for structural ordering yet.
4. Emit `INVALID_EVENT_ORDER` only for edges or tool results that clearly point backward or for tool results at the same sequence as their matching call.

Output:

1. Fixture for backward edge ordering.
2. Fixture for tool result before tool call.

### R2.5 Final Answer Evidence References

Questions:

1. Should evidence be represented through claim fields, provenance edges, or both?
2. Should missing evidence be an error if a claim has no evidence?
3. Should evidence occurring after a claim be Milestone 2 or Milestone 4?

Expected decision:

Use `Claim.evidence` for Milestone 2 invalid-reference checks. Provenance edges remain available but are event-to-event and do not identify claim-specific evidence.

Rules:

1. If a claim lists an evidence event ID that does not exist, emit `INVALID_EVIDENCE_REFERENCE`.
2. If a final answer has no claims, do not emit a diagnostic.
3. If a claim has no evidence, do not emit a diagnostic in Milestone 2.
4. Unsupported claims and evidence-after-claim checks belong to Milestone 4 unless the project decides to include a narrow ordering check now.

Output:

1. Claim model update.
2. Fixture for missing evidence reference.
3. Passing fixture with valid evidence reference.

### R2.6 CLI Behavior

Questions:

1. Should `agentlint validate` run only schema validation or also structural validation?
2. What should successful output look like?
3. What should failure output look like?
4. Should warnings affect exit code?

Expected decision:

In Milestone 2, `agentlint validate TRACE.json` should run both schema validation and structural validation.

Successful output:

```text
valid trace: trace_tool_flow_valid
events: 5
edges: 5
diagnostics: 0
```

Failure output:

```text
error[DUPLICATE_EVENT_ID]: duplicate event id "evt_1"
  related events: evt_1
  remediation: Ensure every event id is unique within the trace.
```

Exit behavior:

1. Exit `0` when there are no `error` diagnostics.
2. Exit `1` when there is at least one `error` diagnostic.
3. Since Milestone 2 emits only errors, no fail-threshold flag is needed.

Output:

1. CLI tests for passing structural validation.
2. CLI tests for failing structural validation.

### R2.7 Fixture Layout

Questions:

1. Should fixtures stay flat under `examples/traces/`?
2. Should expected output snapshots exist in Milestone 2?
3. How much fixture corpus belongs in Milestone 2 versus Milestone 6?

Expected decision:

Keep Milestone 2 examples under `examples/traces/` for now. Add explicit structural fixture names:

```text
examples/traces/structural_duplicate_event_id.json
examples/traces/structural_duplicate_edge_id.json
examples/traces/structural_missing_event_reference.json
examples/traces/structural_tool_result_without_call.json
examples/traces/structural_tool_call_missing_arguments.json
examples/traces/structural_invalid_event_order.json
examples/traces/structural_invalid_evidence_reference.json
examples/traces/structural_valid_tool_flow.json
```

Do not add golden report snapshots yet. Milestone 6 owns expected diagnostic snapshots and broader fixture corpus discipline.

Output:

1. Fixture per structural diagnostic code.
2. Parametrized fixture tests mapping file names to expected diagnostic codes.

### R2.8 Type Checking Decision

Questions:

1. Should Milestone 2 add Pyright or mypy?
2. Will diagnostic and pass code benefit enough to justify the dependency/configuration?

Expected decision:

Evaluate after diagnostics and structural pass are implemented. If configuration is low friction, add one type checker in Milestone 2. If it creates churn around Pydantic unions, defer again and record why.

Output:

1. Short decision entry in `Documents/research_note.md`.
2. Optional config and verification command.

## Build Track

### B2.1 Add Diagnostic Models

Files to create or update:

```text
src/agentlint/diagnostics/__init__.py
src/agentlint/diagnostics/models.py
src/agentlint/diagnostics/formatting.py
```

Implement:

1. `Severity`
2. `DiagnosticCode`
3. `Diagnostic`
4. `format_diagnostic`
5. `format_diagnostics`

Formatting should avoid printing raw trace payload values. It should print code, severity, message, related event IDs, related edge IDs, and remediation.

### B2.2 Adjust IR V1 Models For Structural Diagnostics

Files to update:

```text
src/agentlint/ir/v1/models.py
tests/test_ir_v1_models.py
tests/test_ir_v1_loader.py
```

Changes:

1. Move duplicate event ID validation out of Pydantic.
2. Move duplicate edge ID validation out of Pydantic.
3. Move missing edge endpoint validation out of Pydantic.
4. Change `ToolCallEvent.arguments` to optional.
5. Add `Claim.evidence`.
6. Preserve strict field validation for IDs, event types, edge types, sequences, and JSON-safe payloads.
7. Keep user message `content`, developer instruction `content`, model call `input`, final answer `content`, and claim `id`/`text` schema-required.
8. Reject empty optional reference strings at schema level.

Update Milestone 1 tests that currently expect Pydantic errors so they now expect structural diagnostics.

### B2.3 Add Structural Validation Pass

Files to create:

```text
src/agentlint/passes/structural.py
tests/test_structural_pass.py
```

Implement:

```python
def validate_structure(trace: Trace) -> list[Diagnostic]:
    ...
```

Checks:

1. Duplicate event IDs.
2. Duplicate edge IDs.
3. Missing event references from edges.
4. Tool results without matching tool calls.
5. Tool calls with missing `arguments`.
6. Invalid event ordering.
7. Final answer claims that reference nonexistent evidence.

Implementation notes:

1. Count duplicate event and edge IDs before building lookup maps.
2. Build lookup maps only for IDs that appear once.
3. Avoid cascading diagnostics where possible, but do not hide independent problems.
4. Preserve deterministic diagnostic ordering.

Recommended diagnostic order:

1. Duplicate event IDs.
2. Duplicate edge IDs.
3. Missing event references.
4. Tool call argument issues.
5. Tool result matching issues.
6. Event ordering issues.
7. Evidence reference issues.

### B2.4 Update CLI Validation Flow

Files to update:

```text
src/agentlint/cli.py
tests/test_cli.py
```

Flow:

```text
load native trace
if schema error: print schema error and exit 1
run validate_structure(trace)
if structural diagnostics: print diagnostics and exit 1
print valid trace summary and diagnostics: 0
exit 0
```

Do not add:

1. `check`
2. `explain`
3. `--policy`
4. `--format`
5. `--fail-on`
6. Directory traversal

### B2.5 Add Structural Fixtures

Files to create:

```text
examples/traces/structural_valid_tool_flow.json
examples/traces/structural_duplicate_event_id.json
examples/traces/structural_duplicate_edge_id.json
examples/traces/structural_missing_event_reference.json
examples/traces/structural_tool_result_without_call.json
examples/traces/structural_tool_call_missing_arguments.json
examples/traces/structural_invalid_event_order.json
examples/traces/structural_invalid_evidence_reference.json
```

Use synthetic content only.

The passing fixture should include:

1. User message.
2. Model call.
3. Tool call.
4. Tool result with `call_id`.
5. Final answer with a claim whose evidence references the tool result.
6. Forward edges.

### B2.6 Add Tests

Test files to create or update:

```text
tests/test_diagnostics.py
tests/test_structural_pass.py
tests/test_cli.py
tests/test_ir_v1_models.py
tests/test_ir_v1_loader.py
```

Test coverage:

1. Diagnostic model serialization.
2. Diagnostic formatting.
3. Every structural diagnostic code.
4. Passing structural validation fixture.
5. Deterministic diagnostic ordering.
6. CLI success with `diagnostics: 0`.
7. CLI failure with diagnostic code output.
8. Schema validation still fails distinctly from structural validation.
9. CLI tests assert stdout for success summaries and stderr for structural diagnostics.

### B2.7 Update Documentation

Documents to update or create:

1. `README.md`
   - Explain that `validate` now runs schema and structural validation.
2. `Documents/architecture.md`
   - Add diagnostics and structural pass details.
3. `Documents/research_note.md`
   - Add dated Milestone 2 planning and build decisions.
4. `Documents/milestone_2_research.md`
   - Optional if R2 research produces enough findings to preserve separately.
5. `Documents/milestone_2_build_report.md`
   - Required after implementation and verification.

## Suggested Work Order

1. Finalize diagnostic model fields and codes.
2. Add `diagnostics.models` and `diagnostics.formatting`.
3. Relax IR v1 model checks that should become structural diagnostics.
4. Add `Claim.evidence`.
5. Implement structural pass with duplicate and reference checks first.
6. Add tool call/result matching checks.
7. Add event ordering checks.
8. Add final answer evidence reference checks.
9. Add structural fixtures.
10. Add unit and fixture tests.
11. Update `agentlint validate` to run structural validation.
12. Update README, architecture, and research note.
13. Run full verification.
14. Write Milestone 2 build report.

## Verification Plan

Required commands:

```bash
py -3.12 -m agentlint --help
py -3.12 -m agentlint version
py -3.12 -m agentlint doctor
py -3.12 -m agentlint validate examples/traces/structural_valid_tool_flow.json
py -3.12 -m agentlint validate examples/traces/structural_duplicate_event_id.json
py -3.12 -m pytest
py -3.12 -m ruff check .
py -3.12 -m ruff format --check .
```

Expected command behavior:

1. The valid structural fixture exits `0`.
2. The duplicate event fixture exits `1` and prints `DUPLICATE_EVENT_ID`.
3. pytest passes.
4. Ruff lint and format checks pass.

Optional, depending on R2.8:

```bash
py -3.12 -m pyright
```

or:

```bash
py -3.12 -m mypy src tests
```

## Non-Goals

Milestone 2 should not implement:

1. YAML policy loading.
2. Tool authorization policy checks.
3. Approval policy checks.
4. Data-flow policy checks.
5. Secret/private/trust label propagation.
6. Unsupported claim detection.
7. Evidence relevance or contradiction checking.
8. JSON reports.
9. HTML reports.
10. CI threshold flags.
11. Multiple trace or directory validation.
12. External trace adapters.
13. Runtime gating.
14. Full value graph modeling.

## Risks And Mitigations

### Risk: Structural Diagnostics Require Invalid IR Objects

Mitigation: Treat IR v1 as a parsed trace representation, not a semantically valid trace graph. Let the structural pass decide whether relationships are coherent.

### Risk: Duplicate IDs Make Lookups Ambiguous

Mitigation: Detect duplicates before building maps. Build lookup maps only for IDs that appear exactly once, then avoid relationship checks that would rely on ambiguous duplicate IDs.

### Risk: CLI Output Becomes A Report System Too Early

Mitigation: Keep formatting simple and diagnostics-focused. Defer summary tables, JSON output, redaction policies, and fail thresholds to Milestone 5.

### Risk: Tool Call Argument Checks Become Tool-Specific

Mitigation: In Milestone 2, only detect missing `arguments` field. Do not validate required argument names or types for specific tools.

### Risk: Provenance Checks Expand Too Far

Mitigation: In Milestone 2, only detect nonexistent evidence IDs. Unsupported claims, irrelevant evidence, evidence-after-claim, and contradictions remain Milestone 4 work.

### Risk: Moving Checks Out Of Pydantic Breaks Milestone 1 Tests

Mitigation: Update tests to reflect the new architecture: schema tests cover parse shape; structural tests cover relationship diagnostics.

## Completion Checklist

- [x] Diagnostic model exists.
- [x] Diagnostic formatter exists.
- [x] Structural pass exists.
- [x] Duplicate event IDs produce `DUPLICATE_EVENT_ID`.
- [x] Duplicate edge IDs produce `DUPLICATE_EDGE_ID`.
- [x] Missing edge endpoint references produce `MISSING_EVENT_REFERENCE`.
- [x] Tool results without matching calls produce `TOOL_RESULT_WITHOUT_MATCHING_CALL`.
- [x] Tool calls with missing arguments produce `TOOL_CALL_MISSING_ARGUMENTS`.
- [x] Invalid structural ordering produces `INVALID_EVENT_ORDER`.
- [x] Final answer claims with nonexistent evidence produce `INVALID_EVIDENCE_REFERENCE`.
- [x] IR v1 models are adjusted so these issues can be represented and diagnosed.
- [x] `Claim.evidence` exists.
- [x] Structural fixture traces exist.
- [x] Tests cover every structural diagnostic code.
- [x] CLI validate runs structural validation.
- [x] README is updated.
- [x] Architecture note is updated.
- [x] Research note records Milestone 2 decisions.
- [x] Verification commands pass on Python 3.12.
- [x] Milestone 2 build report is written.
