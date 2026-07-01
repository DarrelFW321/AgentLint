# AgentLint Architecture

AgentLint uses a compiler-inspired pipeline for AI agent execution traces.

```text
raw traces
  -> adapters
  -> schema validation
  -> AgentLint IR
  -> enrichment passes
  -> analysis passes
  -> policy evaluation
  -> diagnostics and reports
```

The product goal is simple: import traces, check policies, and report actionable violations. The implementation uses compiler-style boundaries so input adapters, trace normalization, analysis, and reporting can evolve independently.

## Package Boundaries

```text
src/agentlint/
  cli.py          command-line interface
  version.py      package version metadata
  adapters/       external trace importers
  ir/             AgentLint intermediate representation
    v1/           native AgentLint IR v1 models and JSON loader
  passes/         validation and analysis passes
  policy/         policy loading and evaluation
  diagnostics/    diagnostic models and formatting helpers
  reports/        report emitters
```

Milestone 2 implements the first native IR model package under `agentlint.ir.v1`, a diagnostics model, and a structural validation pass under `agentlint.passes`. External adapters, policy evaluation, and report emitters remain separate boundaries for later milestones.

## Intermediate Representation Direction

The AgentLint IR should be graph-shaped rather than only sequential. Event order, data dependencies, approval links, and provenance links are distinct relationships over the same execution trace.

This distinction matters because different checks ask different questions:

1. Event order answers what happened when.
2. Data-flow edges answer what influenced what.
3. Approval links answer whether an action was authorized before execution.
4. Provenance links answer whether a final-answer claim is supported by observed evidence.

## Policy Direction

V1 should use a purpose-built YAML policy configuration and built-in AgentLint checks.

OPA/Rego is deferred until after the IR and diagnostics are stable. If added, it should operate over exported AgentLint facts as an optional advanced backend rather than replacing the built-in analysis engine.

## Current IR V1 Implementation

The native IR v1 format is a versioned JSON object with:

1. `schema_version`
2. `trace_id`
3. `metadata`
4. `events`
5. `edges`

Events are modeled as Pydantic discriminated unions keyed by `type`. Milestone 1 supports:

1. `user_message`
2. `developer_instruction`
3. `model_call`
4. `tool_call`
5. `tool_result`
6. `approval`
7. `final_answer`

Edges are event-to-event relationships. Milestone 1 supports:

1. `parent`
2. `data_flow`
3. `approval_for`
4. `provenance`

Schema validation covers object construction: malformed JSON, required fields, unsupported event or edge types, unknown fields outside explicit extension fields, non-empty identifiers, and strict integer event sequences.

Relationship integrity is handled by the structural validation pass rather than Pydantic model construction. This lets AgentLint preserve structurally invalid traces long enough to emit stable diagnostic codes.

## Current Structural Validation

Milestone 2 implements `agentlint.passes.validate_structure(trace)`.

The pass emits error diagnostics for:

1. `DUPLICATE_EVENT_ID`
2. `DUPLICATE_EDGE_ID`
3. `MISSING_EVENT_REFERENCE`
4. `TOOL_RESULT_WITHOUT_MATCHING_CALL`
5. `TOOL_CALL_MISSING_ARGUMENTS`
6. `INVALID_EVENT_ORDER`
7. `INVALID_EVIDENCE_REFERENCE`

Diagnostics are deterministic. Duplicate IDs are reported before relationship checks, and lookups are built only from event IDs that appear exactly once so references to duplicated IDs do not create arbitrary follow-on diagnostics.

`agentlint validate TRACE.json` now runs native trace loading, schema validation, structural validation, diagnostic formatting, and exit-code handling. It exits `0` when no error diagnostics are emitted and exits `1` for schema/load failures or structural errors.

## Current Non-Goals

Milestone 2 does not implement:

1. Policy loading.
2. Tool policy checks.
3. Approval policy checks.
4. Data-flow policy checks.
5. Provenance semantic checking.
6. Report generation.
7. External trace adapters.
8. Runtime gating.
9. Full value graph modeling.

Those pieces begin in later milestones.
