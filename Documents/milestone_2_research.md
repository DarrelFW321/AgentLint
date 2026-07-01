# Milestone 2 R2 Research Findings

Research date: 2026-06-30

This document records objective R2 research findings for Milestone 2. It follows the finalized architecture decisions in `Documents/milestone_2_architecture_decisions.md` and refines implementation details before build work begins.

## Research Method

The research was split across four parallel subagent tracks:

1. Diagnostics architecture.
2. Structural pass semantics.
3. IR/schema boundary changes.
4. CLI, fixtures, and testing.

The findings were then reevaluated against:

1. `Documents/milestone_2_architecture_decisions.md`
2. `Documents/milestone_2_implementation_plan.md`
3. `Documents/milestone_1_build_report.md`
4. `src/agentlint/ir/v1/models.py`
5. `src/agentlint/ir/v1/loaders.py`
6. `src/agentlint/cli.py`
7. Current tests and fixtures

Primary documentation considered:

1. Pydantic validators: https://docs.pydantic.dev/latest/concepts/validators/
2. Pydantic validation errors: https://docs.pydantic.dev/latest/errors/errors/
3. Pydantic model config: https://docs.pydantic.dev/latest/api/config/
4. Pydantic fields and defaults: https://docs.pydantic.dev/latest/concepts/fields/
5. Python `StrEnum`: https://docs.python.org/3/library/enum.html#enum.StrEnum
6. Typer testing: https://typer.tiangolo.com/tutorial/testing/

## Consensus Findings

All research tracks agreed on the core Milestone 2 boundary:

1. Pydantic should validate JSON/schema shape.
2. AgentLint structural passes should validate trace relationship semantics.
3. Current IR validators still block several intended structural diagnostics.
4. Diagnostics should be a small model and formatter layer, not the report subsystem.
5. `agentlint validate` should run schema validation and then structural validation.
6. Full value graph modeling should remain deferred.

## Current Implementation Gaps

The current codebase is still Milestone 1 behavior in several important places:

1. `Trace` rejects duplicate event IDs before a structural pass can run.
2. `Trace` rejects duplicate edge IDs before a structural pass can run.
3. `Trace` rejects missing edge endpoints before a structural pass can run.
4. `ToolCallEvent.arguments` is still schema-required.
5. `Claim` has no `evidence` field.
6. `agentlint validate` does not run structural validation.
7. Current model, loader, and CLI tests still expect some relationship problems to be schema errors.
8. No diagnostic model or structural pass exists yet.
9. No structural fixtures exist yet.

These gaps should be resolved in the Milestone 2 build.

## Reevaluated Decisions

### R2-D1: Keep The Schema Versus Structural Boundary

Decision:

Keep the finalized boundary from `milestone_2_architecture_decisions.md`.

Pydantic schema validation should reject object-shape failures. Structural validation should produce AgentLint diagnostics for relationship failures.

Reasoning:

Stable diagnostics require a parsed `Trace` object. Relationship errors that Pydantic rejects cannot receive AgentLint diagnostic codes, related event IDs, or remediation.

Implementation consequence:

Move duplicate ID and missing relationship checks from `Trace` validators into `validate_structure(trace)`.

### R2-D2: Relax Only Fields Needed For Structural Diagnostics

Decision:

Relax only these fields:

1. `ToolCallEvent.arguments` becomes `dict[str, JsonValue] | None = None`.
2. `Claim.evidence` is added as `list[str] = Field(default_factory=list)`.
3. Duplicate event IDs, duplicate edge IDs, and missing edge endpoints no longer fail Pydantic validation.

Keep these schema-required:

1. `schema_version`
2. `trace_id`
3. Event `id`, `type`, and `sequence`
4. Edge `id`, `type`, `from_event`, and `to_event`
5. User message `content`
6. Developer instruction `content`
7. Model call `input`
8. Tool call `tool_name`
9. Tool result `tool_name` and `result`
10. Final answer `content`
11. Claim `id` and `text`

Reasoning:

No Milestone 2 diagnostic needs to represent missing user message content, developer instruction content, model call input, or final answer content. Keeping these schema-required avoids weakening the IR without a specific diagnostic need.

Implementation consequence:

Update model tests so duplicate IDs and missing edge references parse successfully, while invalid primitive/object shape still raises schema errors.

### R2-D3: Optional Reference Strings Should Be Non-Empty When Present

Decision:

Optional reference fields should remain optional, but when present they should be non-empty strings.

Fields:

1. `ToolResultEvent.call_id`
2. `ApprovalEvent.subject_event`
3. `Claim.evidence` entries

Reasoning:

An empty string is not a meaningful graph reference. Treating `""` as a structural missing reference would produce confusing diagnostics. This is a shape constraint, not a relationship check.

Implementation consequence:

Use schema validation for empty optional reference values. Missing optional references can still become structural diagnostics where appropriate, such as a missing tool result `call_id`.

### R2-D4: Diagnostic Cardinality

Decision:

Define diagnostic cardinality explicitly:

1. Emit one `DUPLICATE_EVENT_ID` diagnostic per duplicated event ID.
2. Emit one `DUPLICATE_EDGE_ID` diagnostic per duplicated edge ID.
3. Emit one `MISSING_EVENT_REFERENCE` diagnostic per invalid reference site.
4. Emit one `TOOL_RESULT_WITHOUT_MATCHING_CALL` diagnostic per invalid tool result.
5. Emit one `TOOL_CALL_MISSING_ARGUMENTS` diagnostic per tool call with `arguments is None`.
6. Emit one `INVALID_EVENT_ORDER` diagnostic per invalid ordering relationship.
7. Emit one `INVALID_EVIDENCE_REFERENCE` diagnostic per invalid claim evidence reference.

Reasoning:

This keeps diagnostics deterministic and actionable. It avoids both under-reporting independent problems and over-reporting cascades from one ambiguous ID.

Implementation consequence:

Tests should assert diagnostic count and code for multi-failure scenarios, not only the presence of one code.

### R2-D5: Ambiguous Duplicate IDs Are Not Missing References

Decision:

References to duplicated event IDs should be treated as ambiguous, not missing.

Reasoning:

An ID that appears more than once exists, but it is not uniquely resolvable. Treating it as missing would be inaccurate, and resolving it arbitrarily would create nondeterministic behavior.

Implementation consequence:

The structural pass should:

1. Count IDs first.
2. Emit duplicate diagnostics first.
3. Build lookup maps only for IDs with exactly one occurrence.
4. Skip relationship checks that depend on ambiguous duplicate targets.

### R2-D6: Tool Result Matching Is A Staged Check

Decision:

Tool result matching should run in stages:

1. If `call_id` is missing, emit `TOOL_RESULT_WITHOUT_MATCHING_CALL`.
2. If `call_id` references no event, emit `TOOL_RESULT_WITHOUT_MATCHING_CALL`.
3. If `call_id` references a duplicated event ID, skip follow-on matching to avoid cascade from ambiguous ID.
4. If `call_id` references a non-tool-call event, emit `TOOL_RESULT_WITHOUT_MATCHING_CALL`.
5. If `tool_name` mismatches the referenced tool call, emit `TOOL_RESULT_WITHOUT_MATCHING_CALL`.
6. Only after a valid unique matching tool call exists, check ordering.

Reasoning:

Ordering diagnostics require a valid call/result relationship. If matching fails, ordering is not meaningful.

Implementation consequence:

`INVALID_EVENT_ORDER` for tool results should only be produced after a valid matching call is found.

### R2-D7: Event Ordering Uses Sequence Only

Decision:

Milestone 2 should use `sequence` only.

Rules:

1. Edges may point from an event to another event at the same sequence.
2. Edges may not point backward to a lower-sequence event.
3. Tool results must have a strictly greater sequence than their matching tool calls.
4. Sequences do not need to be contiguous.
5. Sequences do not need to be globally unique.
6. Timestamps are ignored for Milestone 2 ordering.

Reasoning:

Trace sources may have missing or inconsistent timestamps, and the current IR already requires sequence. Requiring unique or contiguous sequence values would overconstrain external adapters later.

Implementation consequence:

Create tests for same-sequence edge success and same-sequence tool result failure.

### R2-D8: Claim Evidence Is Structural Only

Decision:

`Claim.evidence` should support only structural reference checks in Milestone 2.

Rules:

1. Evidence entries are event IDs.
2. Missing evidence IDs produce `INVALID_EVIDENCE_REFERENCE`.
3. Empty evidence is allowed.
4. Claims with no evidence do not produce `UNSUPPORTED_CLAIM`.
5. Evidence-after-claim checks remain deferred unless the project later chooses to include them in provenance validation.

Reasoning:

Milestone 2 validates reference structure. It should not judge whether claim evidence is sufficient, relevant, or temporally valid. Those are provenance checks for later milestones.

Implementation consequence:

Do not implement `UNSUPPORTED_CLAIM`, `EVIDENCE_AFTER_CLAIM`, or semantic evidence compatibility in Milestone 2.

### R2-D9: Diagnostics Are Not Reports

Decision:

Implement diagnostics and lightweight formatting only.

Reasoning:

Milestone 5 owns report formats, JSON reports, summary counts, redaction policy, and CI threshold flags. Milestone 2 only needs readable structural validation output.

Implementation consequence:

Do not modify `reports/` for Milestone 2. Keep `diagnostics` focused on model and formatting helpers.

### R2-D10: CLI Tests Should Separate Stdout And Stderr

Decision:

CLI tests should assert stdout and stderr separately.

Expected behavior:

1. Success summary goes to stdout.
2. Schema/load errors go to stderr.
3. Structural diagnostics go to stderr.

Reasoning:

Typer's test runner exposes output streams separately, and Milestone 2 distinguishes success summaries from diagnostics.

Implementation consequence:

Update CLI tests to use `result.stdout` and `result.stderr` where appropriate. Keep `result.output` only when stream separation is irrelevant.

## Implementation Recommendations

### Diagnostics

Implement:

```text
src/agentlint/diagnostics/models.py
src/agentlint/diagnostics/formatting.py
```

Export from `src/agentlint/diagnostics/__init__.py`.

Use:

1. `Severity(StrEnum)`
2. `DiagnosticCode(StrEnum)`
3. `Diagnostic(BaseModel)`
4. `format_diagnostic`
5. `format_diagnostics`

Tests should cover:

1. Default severity.
2. JSON serialization with enum values.
3. Empty list defaults.
4. Optional `None` fields.
5. Formatting with and without related IDs/remediation.

### IR And Loader Tests

Move these current expectations from schema tests to structural pass tests:

1. Duplicate event IDs.
2. Duplicate edge IDs.
3. Missing edge endpoint references.

Add schema tests for:

1. Omitted `tool_call.arguments` parses as `None`.
2. Explicit `arguments: null` parses as `None`.
3. Empty `arguments: {}` remains valid.
4. Invalid arguments type remains a schema error.
5. Omitted `Claim.evidence` defaults to `[]`.
6. Valid evidence list parses.
7. Invalid evidence type remains a schema error.
8. Empty optional reference strings are schema errors.

### Structural Pass Tests

Add `tests/test_structural_pass.py`.

Cover:

1. One diagnostic code per structural fixture.
2. Deterministic diagnostic ordering.
3. Duplicate IDs plus references to duplicated IDs.
4. Missing references from edges and `approval.subject_event`.
5. Tool result matching failures.
6. Tool result ordering after valid matching.
7. Same-sequence edge allowed.
8. Same-sequence tool result rejected.
9. Claim evidence reference failures.

### CLI Tests

Keep CLI tests narrow:

1. One successful structural validation.
2. One structural failure.
3. One schema failure.
4. One missing file failure.

Structural branch coverage should live in structural pass tests, not CLI tests.

### Fixtures

Add the planned flat structural fixtures under `examples/traces/`:

1. `structural_valid_tool_flow.json`
2. `structural_duplicate_event_id.json`
3. `structural_duplicate_edge_id.json`
4. `structural_missing_event_reference.json`
5. `structural_tool_result_without_call.json`
6. `structural_tool_call_missing_arguments.json`
7. `structural_invalid_event_order.json`
8. `structural_invalid_evidence_reference.json`

Use `native_tool_flow_valid.json` as a base for the passing structural fixture, but add claim evidence referencing the tool result.

## Final R2 Build Guidance

The Milestone 2 build should proceed in this order:

1. Adjust IR v1 model boundary.
2. Add diagnostic model and formatter.
3. Implement structural pass.
4. Add structural fixtures.
5. Update tests.
6. Wire structural validation into CLI.
7. Update README, architecture, research note, and build report.
8. Run full verification.

Do not implement:

1. Report emitters.
2. JSON output.
3. Policy loading.
4. Data-flow labels.
5. Full value graph.
6. Unsupported claim checks.
7. External adapters.
8. Runtime gating.
