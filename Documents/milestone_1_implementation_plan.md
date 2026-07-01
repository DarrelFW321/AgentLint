# Milestone 1 Implementation Plan

Milestone 1 defines the first canonical AgentLint trace representation and makes the package capable of loading and validating native AgentLint traces.

Milestone 0 established the project skeleton, CLI, tests, examples, architecture note, glossary, and research baseline. Milestone 1 should stay focused on the native trace format and intermediate representation, leaving structural lint checks, policy evaluation, reports, and external adapters for later milestones.

## Objective

Create the first real AgentLint intermediate representation and native JSON trace loader.

Milestone 1 is complete when:

1. AgentLint has versioned Pydantic models for the native trace format and IR.
2. Native JSON traces can be loaded through a CLI command.
3. Valid traces produce an in-memory IR object.
4. Invalid traces produce clear schema validation errors.
5. Raw source references are preserved for debugging.
6. Example passing and failing native traces exist.
7. Tests cover the supported event types, edge types, and validation failure paths.

## Working Assumptions

1. The native trace format should be JSON for V1.
2. The native trace format and IR can initially be the same model family, as long as code boundaries allow future adapters to normalize external traces into the same IR.
3. The IR should be graph-shaped, not just a linear event list.
4. Event order, parent links, data-flow links, approval links, and provenance links should be represented as separate relationships.
5. Milestone 1 validates schema shape and referential integrity only where required to construct the IR. Deeper structural checks and diagnostic codes begin in Milestone 2.
6. The CLI should add only `agentlint validate` in this milestone. `check`, `explain`, report formats, policy files, and CI failure thresholds remain out of scope.
7. AgentLint should not make network calls during validation.

## Research Track

The research track should answer enough design questions to avoid churn in the first IR implementation.

### R1.1 Native Trace Format Shape

Questions:

1. What top-level fields should a native trace require?
2. How should trace metadata be represented?
3. Should events and edges be arrays, maps, or both?
4. How should raw source locations and adapter metadata be preserved?
5. What minimal examples demonstrate the format clearly?

Expected decision:

Use a simple versioned JSON object:

```json
{
  "schema_version": "agentlint.ir.v1",
  "trace_id": "trace_001",
  "metadata": {},
  "events": [],
  "edges": []
}
```

Each event should have:

1. `id`
2. `type`
3. `sequence`
4. Optional `timestamp`
5. Optional `actor`
6. Type-specific payload fields
7. Optional `metadata`
8. Optional `source_ref`

Each edge should have:

1. `id`
2. `type`
3. `from_event`
4. `to_event`
5. Optional `metadata`
6. Optional `source_ref`

Output:

1. Final native trace shape documented in code and examples.
2. At least one minimal valid trace fixture.
3. At least one realistic valid trace fixture with model, tool, result, and final answer events.

### R1.2 Event Model

Questions:

1. Which fields are common across all events?
2. Which event payload fields are required for each event type?
3. How should model input/output, tool arguments, tool results, approvals, claims, and final answers be represented before policy checks exist?
4. How strict should Milestone 1 be about event payload contents?

Required event types:

1. `user_message`
2. `developer_instruction`
3. `model_call`
4. `tool_call`
5. `tool_result`
6. `approval`
7. `final_answer`

Expected decision:

Use discriminated Pydantic models keyed by `type`. Keep payloads structured enough for later checks, but avoid over-modeling semantic details before Milestone 2 and Milestone 4.

Suggested payload direction:

1. `user_message`: `content`
2. `developer_instruction`: `content`
3. `model_call`: `input`, optional `output`, optional `model`
4. `tool_call`: `tool_name`, `arguments`
5. `tool_result`: `tool_name`, optional `call_id`, `result`
6. `approval`: `decision`, optional `subject_event`, optional `approved_by`, optional `reason`
7. `final_answer`: `content`, optional `claims`

Output:

1. Pydantic event models.
2. Tests for every supported event type.
3. Examples showing the intended event payload style.

### R1.3 Edge Model

Questions:

1. Which edge types are required for V1?
2. Should edge endpoints reference only events, or should they eventually reference values and claims too?
3. How should the implementation leave room for future value-level data flow?
4. Which referential checks belong in Milestone 1 versus Milestone 2?

Required edge types:

1. `parent`
2. `data_flow`
3. `approval_for`
4. `provenance`

Expected decision:

Milestone 1 edges should reference events only. The models should leave room for future value or claim references without requiring them immediately.

Milestone 1 should reject edges whose `from_event` or `to_event` does not exist, because unresolved references prevent reliable IR construction. More nuanced ordering and semantic checks should wait for Milestone 2.

Output:

1. Pydantic edge models.
2. Referential integrity validation for edge endpoints.
3. Tests for every supported edge type.

### R1.4 Source References And Raw Debugging Data

Questions:

1. What source reference fields are useful for native traces and later external adapters?
2. How much raw source data should be preserved?
3. How should sensitive raw data be handled before report redaction exists?

Expected decision:

Define a small `SourceRef` model:

1. Optional `source`
2. Optional `path`
3. Optional `line`
4. Optional `column`
5. Optional `raw_id`

Avoid duplicating full raw trace payloads inside every IR object in Milestone 1. Preserve stable raw identifiers and locations now; revisit richer raw snapshots when adapters arrive.

Output:

1. Shared `SourceRef` model.
2. Examples showing source references.
3. Tests proving source references survive load/validation.

### R1.5 CLI Scope And Error Output

Questions:

1. What should `agentlint validate` accept?
2. Should it validate one file, multiple files, or directories in Milestone 1?
3. What should successful output look like before reports exist?
4. How should schema errors be shown without introducing the full diagnostics model too early?

Expected decision:

Implement:

```bash
agentlint validate TRACE.json
```

Milestone 1 can validate a single file path. Directory traversal and multiple trace handling can wait until report and CI behavior are designed.

Successful validation should print a concise summary:

```text
valid trace: trace_001
events: 5
edges: 3
```

Invalid validation should exit non-zero and print Pydantic validation messages in a readable form. Stable AgentLint diagnostic codes begin in Milestone 2.

Output:

1. CLI design for `validate`.
2. Tests for success, malformed JSON, schema errors, and missing file behavior.

### R1.6 Type Checking Decision

Questions:

1. Should Milestone 1 introduce pyright or mypy?
2. Is the codebase complex enough to benefit from a type-checker gate now?
3. Which tool best fits the current Python/Pydantic code style?

Expected decision:

Evaluate pyright and mypy quickly after the first Pydantic models exist. If one works without significant configuration churn, add it as a development dependency and verification command. If not, defer strict type checking to Milestone 2 and keep Ruff plus tests as the gate.

Output:

1. Short entry in `Documents/research_note.md` recording the decision.
2. Optional type-checker config only if it is low-friction.

## Build Track

### B1.1 Add IR Package Structure

Files to create:

```text
src/agentlint/ir/v1/__init__.py
src/agentlint/ir/v1/models.py
src/agentlint/ir/v1/loaders.py
```

Potential responsibilities:

1. `models.py`: Pydantic models and enums.
2. `loaders.py`: JSON file loading and conversion into `Trace`.
3. `__init__.py`: public exports for the v1 model package.

Keep the v1 namespace explicit so later schema versions can coexist.

### B1.2 Implement Core Models

Models to implement:

1. `Trace`
2. `TraceMetadata`
3. `SourceRef`
4. `EventBase`
5. One event model for each required event type.
6. `Edge`
7. Enum or literal type definitions for event and edge types.

Validation requirements:

1. `schema_version` must equal `agentlint.ir.v1`.
2. `trace_id` must be non-empty.
3. Event IDs must be non-empty.
4. Event sequence values must be integers.
5. Edge endpoint IDs must refer to existing events.
6. Edge IDs must be non-empty.

Consider enforcing duplicate event ID and duplicate edge ID rejection in Milestone 1, because model construction should not allow ambiguous graph references. Full duplicate diagnostic codes still belong in Milestone 2.

### B1.3 Add Native JSON Loader

Implement a loader that:

1. Reads a JSON file from disk.
2. Reports malformed JSON distinctly from schema validation errors.
3. Validates the JSON into `Trace`.
4. Returns the `Trace` model.
5. Does not perform policy checks.
6. Does not send data to external services.

The loader should be usable by both CLI code and tests.

### B1.4 Add `agentlint validate`

Update [src/agentlint/cli.py](D:/repos/trace_checker/src/agentlint/cli.py) to add:

```bash
agentlint validate TRACE.json
```

Expected behavior:

1. Existing `version` and `doctor` behavior remains unchanged.
2. A valid trace exits with code 0.
3. A missing file exits non-zero with a clear message.
4. Malformed JSON exits non-zero with a clear message.
5. Schema validation errors exit non-zero with readable error details.

Avoid adding policy flags, report formats, directory recursion, or fail thresholds in this milestone.

### B1.5 Add Example Traces

Files to create:

```text
examples/traces/native_minimal_valid.json
examples/traces/native_tool_flow_valid.json
examples/traces/native_invalid_missing_event_ref.json
examples/traces/native_invalid_schema.json
```

Examples should be small but realistic enough to teach the format.

The valid tool-flow trace should include:

1. A user message.
2. A model call.
3. A tool call.
4. A tool result.
5. A final answer.
6. Parent or data-flow edges connecting the relevant events.
7. A provenance edge from evidence to final answer if the example includes a claim.

### B1.6 Add Tests

Test files to create or update:

```text
tests/test_cli.py
tests/test_ir_v1_models.py
tests/test_ir_v1_loader.py
```

Test coverage:

1. Existing CLI tests still pass.
2. Each required event type can be parsed.
3. Each required edge type can be parsed.
4. Valid examples load successfully.
5. Malformed JSON raises or returns the expected loader error.
6. Invalid schema raises or returns the expected validation error.
7. Missing edge endpoint is rejected.
8. Duplicate event IDs are rejected if implemented in Milestone 1.
9. `agentlint validate` succeeds for a valid file.
10. `agentlint validate` fails for invalid files.

### B1.7 Update Documentation

Documents to create or update:

1. `README.md`
   - Add `agentlint validate examples/traces/native_minimal_valid.json`.
   - Keep status honest that only schema validation exists.
2. `Documents/research_note.md`
   - Add dated Milestone 1 research/build decisions.
3. `Documents/architecture.md`
   - Add a short note that `ir/v1` now contains the first native model package.
4. Optional: `Documents/native_trace_format_v1.md`
   - Add only if the format needs more explanation than examples and docstrings can carry.

## Suggested Work Order

1. Finalize the native trace JSON shape.
2. Add `src/agentlint/ir/v1/` package.
3. Implement common models, event models, edge models, and `Trace`.
4. Add duplicate ID and edge endpoint validation.
5. Add JSON loader.
6. Add minimal valid and invalid example traces.
7. Add model and loader tests.
8. Add `agentlint validate`.
9. Add CLI tests for `validate`.
10. Update README and research notes.
11. Run tests, lint, and format checks.
12. Record build results in a Milestone 1 build report.

## Verification Plan

Required commands:

```bash
py -3.12 -m agentlint --help
py -3.12 -m agentlint version
py -3.12 -m agentlint doctor
py -3.12 -m agentlint validate examples/traces/native_minimal_valid.json
py -3.12 -m agentlint validate examples/traces/native_tool_flow_valid.json
py -3.12 -m pytest
py -3.12 -m ruff check .
py -3.12 -m ruff format --check .
```

Preferred workflow, if local scripts are on `PATH`:

```bash
uv run agentlint validate examples/traces/native_minimal_valid.json
uv run pytest
uv run ruff check .
uv run ruff format --check .
```

Optional, depending on R1.6:

```bash
py -3.12 -m pyright
```

or:

```bash
py -3.12 -m mypy src tests
```

## Non-Goals

Milestone 1 should not implement:

1. Structural diagnostic codes.
2. Policy YAML loading.
3. Tool authorization checks.
4. Approval policy checks.
5. Data-flow policy checks.
6. Provenance semantic checking.
7. Human-readable violation reports.
8. JSON report output.
9. CI fail thresholds.
10. External trace adapters.
11. Runtime gating.

## Risks And Mitigations

### Risk: Over-Modeling The IR Too Early

Mitigation: model only the fields needed for V1 examples and near-term checks. Preserve extensibility through `metadata` and source references instead of adding speculative fields.

### Risk: Confusing Schema Validation With Lint Diagnostics

Mitigation: Milestone 1 should use normal validation errors for malformed traces. Stable diagnostic codes and remediation text start in Milestone 2.

### Risk: Event-Level Data Flow Is Too Coarse

Mitigation: accept event-level edges for Milestone 1, but keep the edge model open to future value or claim references.

### Risk: Native Format Becomes Adapter-Specific

Mitigation: keep native field names framework-neutral. Do not mirror OpenAI Agents, LangSmith, OpenTelemetry, or MCP structures directly.

### Risk: Examples Leak Real Sensitive Data

Mitigation: use synthetic traces only. Keep examples realistic in shape, not in private content.

### Risk: CLI Grows Past The Milestone

Mitigation: add only `validate TRACE.json`. Defer directory traversal, reports, policies, and CI behavior until later milestones.

## Completion Checklist

- [x] Native trace shape is finalized.
- [x] `src/agentlint/ir/v1/` exists.
- [x] Pydantic models exist for `Trace`, events, edges, metadata, and source references.
- [x] Event types are supported: `user_message`, `developer_instruction`, `model_call`, `tool_call`, `tool_result`, `approval`, `final_answer`.
- [x] Edge types are supported: `parent`, `data_flow`, `approval_for`, `provenance`.
- [x] Native JSON loader exists.
- [x] Edge endpoint references are validated.
- [x] Duplicate event IDs are rejected or explicitly deferred to Milestone 2.
- [x] Example valid native traces exist.
- [x] Example invalid native traces exist.
- [x] `agentlint validate TRACE.json` exists.
- [x] CLI tests cover `validate`.
- [x] IR model tests cover all event and edge types.
- [x] Loader tests cover valid, malformed, and invalid traces.
- [x] README is updated with the new command.
- [x] Research note records Milestone 1 decisions.
- [x] Verification commands pass on Python 3.12.
- [x] Milestone 1 build report is written.
