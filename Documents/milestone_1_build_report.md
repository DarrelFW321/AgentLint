# Milestone 1 Build Report

Build date: 2026-06-30

Milestone 1 implemented the first native AgentLint trace representation and schema validation path.

## Built Artifacts

1. `src/agentlint/ir/v1/__init__.py`
2. `src/agentlint/ir/v1/models.py`
3. `src/agentlint/ir/v1/loaders.py`
4. `examples/traces/native_minimal_valid.json`
5. `examples/traces/native_tool_flow_valid.json`
6. `examples/traces/native_invalid_missing_event_ref.json`
7. `examples/traces/native_invalid_schema.json`
8. `tests/test_ir_v1_models.py`
9. `tests/test_ir_v1_loader.py`
10. Updated `tests/test_cli.py`
11. Updated `README.md`
12. Updated `Documents/architecture.md`
13. Updated `Documents/research_note.md`
14. Updated `Documents/milestone_1_research.md`

## Implemented IR

The native trace format is `agentlint.ir.v1`.

Top-level trace fields:

1. `schema_version`
2. `trace_id`
3. `metadata`
4. `events`
5. `edges`

Supported event types:

1. `user_message`
2. `developer_instruction`
3. `model_call`
4. `tool_call`
5. `tool_result`
6. `approval`
7. `final_answer`

Supported edge types:

1. `parent`
2. `data_flow`
3. `approval_for`
4. `provenance`

Milestone 1 also includes a minimal `Claim` model for final-answer claims and a `SourceRef` model for stable source pointers.

## Implemented Validation

Milestone 1 validation covers:

1. Malformed JSON.
2. Required schema fields.
3. Exact `schema_version`.
4. Non-empty trace, event, edge, and claim identifiers.
5. Strict integer event sequences.
6. Duplicate event IDs.
7. Duplicate edge IDs.
8. Edge endpoints that reference missing events.
9. Unknown fields outside explicit extension fields.

Stable AgentLint diagnostic codes, remediation text, and semantic structural checks remain Milestone 2 work.

## Implemented CLI

Milestone 1 adds:

```bash
agentlint validate TRACE.json
```

Successful validation prints:

```text
valid trace: <trace_id>
events: <count>
edges: <count>
```

Invalid validation exits non-zero and prints readable schema, JSON, or file errors.

## R1 Decision Outcomes

1. Minimal claims are implemented.
2. Full value graph modeling is deferred.
3. Edge endpoints remain event-to-event.
4. Loader-owned file errors are implemented.
5. Generated JSON Schema is available through `Trace.model_json_schema()` but not committed as a generated artifact.
6. Duplicate IDs are validation errors now and can become stable diagnostics in Milestone 2.

## Verification Results

Verification passed on Python 3.12.10:

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

Results:

1. CLI help includes `validate`.
2. `version` prints `0.0.0`.
3. `doctor` reports Python 3.12.10 and `Python >=3.12: yes`.
4. Both valid native example traces validate successfully.
5. pytest passed: 28 tests passed.
6. Ruff lint passed.
7. Ruff format check passed.

## Remaining Caveats

1. `agentlint validate` validates only one native JSON trace file at a time.
2. No policy checks run yet.
3. No structural diagnostic codes exist yet.
4. No external adapters exist yet.
5. The local environment caveat from Milestone 0 still applies: `py -3.12 -m agentlint` is the reliable fallback in this shell.
