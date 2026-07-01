# Milestone 2 Build Report

Build date: 2026-07-01

Status: complete.

## Scope

Milestone 2 implemented structural trace validation and stable diagnostics for native AgentLint IR v1 traces.

Implemented:

1. Diagnostic model and formatter.
2. Structural validation pass.
3. IR v1 relaxations needed to preserve structurally invalid traces.
4. CLI validation flow that runs schema validation followed by structural validation.
5. Structural fixtures for each Milestone 2 diagnostic code.
6. Tests for diagnostics, IR model boundaries, loading, structural validation, and CLI behavior.

Deferred:

1. Policy loading.
2. Tool authorization checks.
3. Approval policy checks.
4. Data-flow policy checks.
5. Provenance semantic checks.
6. Reports and JSON output.
7. External adapters.
8. Full value graph modeling.

## Implementation Summary

New packages and modules:

1. `src/agentlint/diagnostics/models.py`
2. `src/agentlint/diagnostics/formatting.py`
3. `src/agentlint/passes/structural.py`

Key behavior changes:

1. Duplicate event IDs, duplicate edge IDs, and missing event references are now structural diagnostics rather than Pydantic construction errors.
2. `ToolCallEvent.arguments` is optional so missing arguments can produce `TOOL_CALL_MISSING_ARGUMENTS`.
3. `Claim.evidence` records event-level evidence references for structural validation.
4. Optional reference strings remain non-empty when present.
5. `agentlint validate TRACE.json` exits `1` on structural error diagnostics and prints diagnostics to stderr.

Milestone 2 diagnostic codes:

1. `DUPLICATE_EVENT_ID`
2. `DUPLICATE_EDGE_ID`
3. `MISSING_EVENT_REFERENCE`
4. `TOOL_RESULT_WITHOUT_MATCHING_CALL`
5. `TOOL_CALL_MISSING_ARGUMENTS`
6. `INVALID_EVENT_ORDER`
7. `INVALID_EVIDENCE_REFERENCE`

## Fixture Coverage

Added structural fixtures under `examples/traces/`:

1. `structural_valid_tool_flow.json`
2. `structural_duplicate_event_id.json`
3. `structural_duplicate_edge_id.json`
4. `structural_missing_event_reference.json`
5. `structural_tool_result_without_call.json`
6. `structural_tool_call_missing_arguments.json`
7. `structural_invalid_event_order.json`
8. `structural_invalid_evidence_reference.json`

Also added `native_malformed.json` so loader tests do not need to create malformed JSON in the system temp directory.

## Verification

Commands run on Python 3.12.10:

```text
py -3.12 -m agentlint --help
```

Result: passed.

```text
py -3.12 -m agentlint version
```

Result: passed, printed `0.0.0`.

```text
py -3.12 -m agentlint doctor
```

Result: passed, reported Python 3.12.10 and `Python >=3.12: yes`.

```text
py -3.12 -m agentlint validate examples\traces\structural_valid_tool_flow.json
```

Result: passed.

```text
valid trace: trace_structural_valid_tool_flow
events: 5
edges: 5
diagnostics: 0
```

```text
py -3.12 -m agentlint validate examples\traces\structural_duplicate_event_id.json
```

Result: passed as an expected failure path, exited `1`.

```text
error[DUPLICATE_EVENT_ID]: duplicate event id "evt_duplicate"
  related events: evt_duplicate
  remediation: Ensure every event id is unique within the trace.
```

```text
py -3.12 -m pytest
```

Result: passed, `57 passed`.

```text
py -3.12 -m ruff check .
```

Result: passed. Ruff emitted cache-write warnings for the existing local `.ruff_cache`, but exited `0`.

```text
py -3.12 -m ruff format --check .
```

Result: passed. Ruff emitted the same cache-write warnings, but exited `0`.

```text
git diff --check
```

Result: passed.

## Notes

The Ruff cache warning appears local to the workspace cache directory permissions and did not affect lint or format results.
