# Milestone 1 R1 Research Findings

Research date: 2026-06-30

This document records objective findings for Milestone 1 research. It complements `Documents/milestone_1_implementation_plan.md` and should be treated as the reasoning record for the first native AgentLint trace format and IR implementation.

## Research Method

The research was split across three parallel subagent tracks and then consolidated:

1. Native trace and IR shape.
2. Pydantic v2 modeling mechanics.
3. CLI, testing, and build implications.

The research used the local project documents first:

1. `Documents/research_note.md`
2. `Documents/milestone_1_implementation_plan.md`
3. `Documents/milestones.md`
4. `Documents/architecture.md`
5. `Documents/requirements_specification.md`
6. `README.md`
7. `pyproject.toml`
8. `src/agentlint/cli.py`
9. `tests/test_cli.py`

Official primary documentation was used where implementation mechanics depended on current tool behavior.

## Summary Decisions

1. Milestone 1 should define a native JSON trace format named `agentlint.ir.v1`.
2. The native trace format and first IR can share one Pydantic model family, as long as the package boundary remains adapter-ready.
3. The top-level trace should contain `schema_version`, `trace_id`, `metadata`, `events`, and `edges`.
4. Events should be Pydantic discriminated union members keyed by `type`.
5. Edges should be event-to-event in Milestone 1.
6. Source references should be small stable pointers, not full raw trace payload snapshots.
7. Milestone 1 should reject malformed JSON, schema errors, duplicate event IDs, duplicate edge IDs, and edge references to missing events.
8. Stable AgentLint diagnostic codes, remediation text, and deeper structural checks belong to Milestone 2.
9. `agentlint validate TRACE.json` should validate one file only and report schema-level success or failure.
10. No new runtime dependencies are required for Milestone 1.

## R1.1 Native Trace Format Shape

### Finding

The native trace should be a simple versioned JSON object:

```json
{
  "schema_version": "agentlint.ir.v1",
  "trace_id": "trace_001",
  "metadata": {},
  "events": [],
  "edges": []
}
```

### Reasoning

The roadmap calls for a canonical AgentLint IR and a native trace format in Milestone 1. The architecture note says the IR should be graph-shaped rather than only sequential. A top-level `events` list plus `edges` list preserves both chronological event order and graph relationships without prematurely adding a graph library.

Arrays are preferable to maps in the first native format because:

1. They preserve input order directly.
2. They are natural for human-authored fixtures.
3. Duplicate identifiers can be detected explicitly instead of being overwritten by object keys.
4. They keep the format close to common exported trace shapes.

### Implementation Consequence

Implement a `Trace` model with:

1. `schema_version: Literal["agentlint.ir.v1"]`
2. `trace_id: str`
3. `metadata: dict[str, JsonValue]`
4. `events: list[Event]`
5. `edges: list[Edge]`

Reject empty `trace_id` values and unknown top-level fields.

## R1.2 Native Format And IR Boundary

### Finding

The native trace format and the first IR can initially be the same Pydantic model family.

### Reasoning

Milestone 1 has no external adapters yet. Maintaining separate native input models and IR models would add ceremony before there is a real adapter boundary to protect. The package layout should still use a versioned namespace such as `agentlint.ir.v1` so later adapters can normalize external formats into the same IR.

### Implementation Consequence

Create:

```text
src/agentlint/ir/v1/__init__.py
src/agentlint/ir/v1/models.py
src/agentlint/ir/v1/loaders.py
```

Do not add adapter-specific assumptions to these models.

## R1.3 Event Model

### Finding

Milestone 1 should support these event types:

1. `user_message`
2. `developer_instruction`
3. `model_call`
4. `tool_call`
5. `tool_result`
6. `approval`
7. `final_answer`

Each event should share common fields:

1. `id`
2. `type`
3. `sequence`
4. Optional `timestamp`
5. Optional `actor`
6. Optional `metadata`
7. Optional `source_ref`

### Reasoning

These event types are listed in the Milestone 1 roadmap and match the product requirements for representing user input, developer instructions, model activity, tools, approvals, and final answers. `sequence` is needed even when timestamps are absent or unreliable. `metadata` and `source_ref` provide extension points without accepting unknown fields silently.

### Implementation Consequence

Use discriminated Pydantic models keyed by `type`:

```python
Event = Annotated[
    UserMessageEvent
    | DeveloperInstructionEvent
    | ModelCallEvent
    | ToolCallEvent
    | ToolResultEvent
    | ApprovalEvent
    | FinalAnswerEvent,
    Field(discriminator="type"),
]
```

Each event model should use a literal discriminator, for example:

```python
type: Literal["tool_call"]
```

Suggested payload fields:

1. `user_message`: `content`
2. `developer_instruction`: `content`
3. `model_call`: `input`, optional `output`, optional `model`
4. `tool_call`: `tool_name`, `arguments`
5. `tool_result`: `tool_name`, optional `call_id`, `result`
6. `approval`: `decision`, optional `subject_event`, optional `approved_by`, optional `reason`
7. `final_answer`: `content`, optional `claims`

## R1.4 Claims And Values

### Finding

Milestone 1 should avoid a full value-level graph, but it should leave an explicit path for later value and claim modeling.

### Reasoning

The roadmap mentions Pydantic models for values and claims, while the implementation plan intentionally narrows Milestone 1 to trace construction and event-level edges. The requirements also say data-flow and provenance precision may depend on explicit annotations. Implementing a rich `Value` graph now would overfit before Milestone 4 data-flow checks exist.

Claims are closer to the Milestone 1 surface because `final_answer` can contain optional structured claims. A minimal claim shape can support future provenance checks without semantic validation.

### Implementation Consequence

Use JSON-safe fields for arbitrary payloads in Milestone 1. Add a minimal `Claim` model only if needed by examples:

```text
id
text
metadata
source_ref
```

Defer first-class value nodes or value-to-value edges until data-flow checks need them. If the project wants to satisfy the roadmap wording strictly, define a local JSON value alias or lightweight value wrapper without using it as an edge endpoint yet.

## R1.5 Edge Model

### Finding

Milestone 1 should support these edge types:

1. `parent`
2. `data_flow`
3. `approval_for`
4. `provenance`

Each edge should contain:

1. `id`
2. `type`
3. `from_event`
4. `to_event`
5. Optional `metadata`
6. Optional `source_ref`

### Reasoning

The architecture note says event order, data-flow edges, approval links, and provenance links are distinct relationships. Event-to-event edges are coarse, but they are sufficient for Milestone 1 examples and avoid prematurely designing value-level or claim-level references.

### Implementation Consequence

Use exact string literals for edge types unless enum member reuse becomes necessary. Validate that every `from_event` and `to_event` exists in `events`.

## R1.6 Source References

### Finding

Source references should be small stable pointers:

1. Optional `source`
2. Optional `path`
3. Optional `line`
4. Optional `column`
5. Optional `raw_id`

### Reasoning

The roadmap says raw source references should be preserved for debugging, but security requirements say reports should avoid exposing private values unnecessarily. Storing full raw payloads inside every event or edge would create redaction work before reports exist. Stable pointers preserve debuggability without duplicating sensitive trace content.

### Implementation Consequence

Create a shared `SourceRef` model and attach it optionally to events, edges, and claims if claims are implemented.

## R1.7 Validation Boundary

### Finding

Milestone 1 validation should cover schema construction and minimal graph integrity:

1. Valid JSON parsing.
2. Required fields.
3. Exact `schema_version`.
4. Non-empty trace, event, and edge identifiers.
5. Strict integer `sequence` values.
6. Duplicate event ID rejection.
7. Duplicate edge ID rejection.
8. Edge endpoint references resolving to existing events.
9. Unknown fields rejected unless they are inside explicit `metadata` or payload fields.

### Reasoning

Unresolved or ambiguous IDs prevent reliable IR construction, so they belong in Milestone 1 even though stable duplicate/missing-reference diagnostics are listed under Milestone 2. The distinction is output quality: Milestone 1 may raise validation errors; Milestone 2 will produce AgentLint diagnostic codes, related events, and remediation.

### Implementation Consequence

Implement duplicate and endpoint checks in Pydantic validation. Do not implement these Milestone 2 checks yet:

1. Tool results without matching tool calls.
2. Tool calls with missing required arguments beyond schema-required fields.
3. Invalid event ordering.
4. Final answers referencing nonexistent claim-level evidence.
5. Stable diagnostic codes.
6. Remediation text.

## R1.8 Pydantic Modeling Mechanics

### Finding

Pydantic v2 has the required mechanics for Milestone 1:

1. Discriminated unions for events.
2. Field or model validators for graph invariants.
3. JSON Schema generation through `Trace.model_json_schema()`.
4. Strict validation controls for fields like `sequence`.
5. Structured validation error objects for CLI formatting.

### Reasoning

Official Pydantic documentation recommends discriminated unions when every union member has a common discriminator field. Pydantic validates only the matching union member and emits a JSON Schema discriminator. Pydantic model and field validators can enforce cross-field graph integrity, while JSON Schema generation can satisfy the `agentlint.ir.v1` schema deliverable without maintaining a separate hand-written schema.

Pydantic defaults to type coercion, so strictness must be deliberate. For example, `sequence` should not accept `"1"` as equivalent to `1`.

### Implementation Consequence

Use:

1. `Field(discriminator="type")` for `Event`.
2. `Literal[...]` for fixed schema, event, and edge strings.
3. `Field(strict=True)` or strict model config for `sequence`.
4. `ConfigDict(extra="forbid")` on IR models.
5. Validators for duplicate IDs and edge references.
6. `Trace.model_json_schema()` to publish or test the schema.

Prefer `dict[str, JsonValue]` and `JsonValue`-like payloads over `Any` so arbitrary Python objects do not enter the IR. Because `pyproject.toml` currently says `pydantic>=2.0`, confirm that the chosen Pydantic JSON value type exists at the declared lower bound. If not, either raise the lower bound deliberately or define a local recursive JSON alias.

Primary references:

1. Pydantic discriminated unions: https://docs.pydantic.dev/latest/concepts/unions/#discriminated-unions
2. Pydantic validators: https://docs.pydantic.dev/latest/concepts/validators/
3. Pydantic JSON Schema: https://docs.pydantic.dev/latest/concepts/json_schema/
4. Pydantic strict mode: https://docs.pydantic.dev/latest/concepts/strict_mode/
5. Pydantic model config: https://docs.pydantic.dev/latest/api/config/
6. Pydantic errors: https://docs.pydantic.dev/latest/errors/errors/

## R1.9 Loader And Error Reporting

### Finding

The native loader should parse JSON separately from schema validation.

### Reasoning

Milestone 1 requires malformed JSON and schema validation failures to be reported distinctly. Using `json.loads` first and `Trace.model_validate(data)` second makes that boundary explicit. It also allows the CLI to avoid printing raw trace input from validation errors, which is consistent with the later redaction requirement.

### Implementation Consequence

Implement a loader flow like:

```text
read file
json.loads
Trace.model_validate
return Trace
```

Define small loader exceptions or error result types for:

1. Missing/unreadable file.
2. Malformed JSON.
3. Schema validation failure.

When formatting Pydantic validation errors, print location, message, and type. Avoid dumping raw `input` values in CLI output.

## R1.10 CLI Scope

### Finding

Milestone 1 should add only:

```bash
agentlint validate TRACE.json
```

### Reasoning

The existing CLI is a Typer multi-command app with `version` and `doctor`. The Milestone 1 plan explicitly excludes directory traversal, multiple trace inputs, policy files, report formats, fail thresholds, and `check` or `explain` commands. Keeping `validate` single-file prevents the CLI from implying report or CI behavior before Milestone 5.

### Implementation Consequence

Add one Typer command with one positional path argument. There are two acceptable missing-file strategies:

1. Let Typer validate path existence and file-ness.
2. Let the loader handle path errors for custom AgentLint wording.

The second option gives more control and keeps all loader errors testable through the same path.

Successful output should be concise:

```text
valid trace: trace_001
events: 5
edges: 3
```

Primary references:

1. Typer testing: https://typer.tiangolo.com/tutorial/testing/
2. Typer path parameters: https://typer.tiangolo.com/tutorial/parameter-types/path/
3. PyPA `project.scripts`: https://packaging.python.org/en/latest/specifications/pyproject-toml/#entry-points

## R1.11 Test And Fixture Strategy

### Finding

Tests should split CLI behavior, model behavior, and loader behavior.

### Reasoning

The current test suite only covers Milestone 0 CLI smoke behavior. Milestone 1 introduces separate concerns: schema construction, graph integrity, file loading, and command behavior. Keeping these tests separate will make later diagnostics and report tests easier to add.

### Implementation Consequence

Add or update:

```text
tests/test_cli.py
tests/test_ir_v1_models.py
tests/test_ir_v1_loader.py
```

Add examples:

```text
examples/traces/native_minimal_valid.json
examples/traces/native_tool_flow_valid.json
examples/traces/native_invalid_missing_event_ref.json
examples/traces/native_invalid_schema.json
```

Test coverage should include:

1. Each event type parses.
2. Each edge type parses.
3. Valid examples load successfully.
4. Malformed JSON is distinct from schema errors.
5. Missing edge endpoints are rejected.
6. Duplicate event IDs are rejected.
7. Duplicate edge IDs are rejected.
8. `agentlint validate` succeeds for valid examples.
9. `agentlint validate` fails for invalid examples.

## R1.12 Dependency And Tooling Findings

### Finding

The current dependency set is sufficient for Milestone 1.

### Reasoning

`pyproject.toml` already declares Python 3.12 or newer, Pydantic, Typer, Rich, pytest, and Ruff. The console script entry point already maps `agentlint` to `agentlint.cli:main`.

`uv.lock` currently contains Pydantic 2.13.4 and Typer 0.26.8, but the declared dependency constraints are broader. Implementation should be written against declared constraints or update those constraints intentionally.

### Implementation Consequence

Do not add new runtime dependencies for Milestone 1. Re-evaluate a type checker after the first models exist, as already planned.

## R1.13 Documentation Findings

### Finding

Milestone 1 implementation should update the README, architecture note, and research note after the build.

### Reasoning

The current README honestly says trace validation begins in later milestones. Once `validate` exists, that statement must change, but the status should remain precise: Milestone 1 validates native trace schema and graph construction only.

### Implementation Consequence

After implementation:

1. Add `agentlint validate examples/traces/native_minimal_valid.json` to `README.md`.
2. Add a short `ir/v1` note to `Documents/architecture.md`.
3. Add a dated Milestone 1 build/research entry to `Documents/research_note.md`.
4. Write a Milestone 1 build report after verification.
5. Create `Documents/native_trace_format_v1.md` only if examples and docstrings are not enough.

## Resolved Open Questions

1. Implement a minimal `Claim` model in Milestone 1 with `id`, `text`, `metadata`, and `source_ref`. Do not implement semantic claim validation yet.
2. Do not raise the Pydantic lower bound for `JsonValue`. Use a Python 3.12 named recursive `JsonValue` type alias local to the IR model package.
3. Let the AgentLint loader own missing-file and unreadable-file handling so CLI error wording is consistent and directly testable.
4. Do not commit a generated JSON Schema file in Milestone 1. Expose schema generation through `Trace.model_json_schema()` and test that the event discriminator is present.
5. Reject duplicate event IDs and duplicate edge IDs as Milestone 1 validation errors. Stable AgentLint diagnostic codes for duplicates remain a Milestone 2 concern.

## Recommended R1 Decisions Before Build

1. Reject duplicate event and edge IDs in Milestone 1 as IR construction errors.
2. Reject missing edge endpoints in Milestone 1 as IR construction errors.
3. Keep edges event-to-event in Milestone 1.
4. Use discriminated event unions keyed by `type`.
5. Use explicit `metadata` fields and forbid unknown fields elsewhere.
6. Parse JSON separately from schema validation.
7. Keep `agentlint validate` single-file only.
8. Defer semantic structural checks and stable diagnostics to Milestone 2.
