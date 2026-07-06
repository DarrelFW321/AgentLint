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
  passes/         validation and analysis passes, including policy evaluation
  policy/         policy loading and validation
  diagnostics/    diagnostic models and formatting helpers
  reports/        report emitters
```

Milestone 5 implements the first native IR model package under `agentlint.ir.v1`, diagnostics, structural and policy evaluation passes under `agentlint.passes`, YAML policy loading and validation under `agentlint.policy`, shared check execution, and text/JSON reports under `agentlint.reports`. External adapters remain a separate boundary for later milestones.

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

## Current Policy DSL V1

Milestone 3 implemented YAML policy definition and validation. Milestone 4 implements offline policy evaluation over structurally valid native traces.

Policy files use:

1. `version: 1`
2. `policy_id`
3. `metadata`
4. `tools`
5. `sources`
6. `sinks`
7. `rules`
8. `exceptions`

The policy package provides strict Pydantic models and a safe YAML loader. Duplicate YAML mapping keys are rejected before schema validation because silent overwrites are unsafe for policy files.

Policy concepts implemented in the schema:

1. Tool permissions.
2. Approval requirements.
3. Tool risk levels.
4. Shallow argument constraints.
5. Source sensitivity.
6. Source trust.
7. Sink visibility.
8. Rule severity overrides.
9. Structured exceptions.

`agentlint policy validate POLICY.yaml` validates policy files and prints a small summary. `agentlint validate TRACE.json --policy POLICY.yaml` validates the policy, validates the trace structurally, then runs policy checks against the trace.

## Current Policy Evaluation

Milestone 4 implements `agentlint.passes.evaluate_policy(trace, policy)`.

Policy evaluation emits diagnostics for:

1. Unknown tools.
2. Denied tool calls.
3. Missing, incorrectly typed, or disallowed configured tool arguments.
4. Missing approvals.
5. Approvals recorded after actions.
6. Actions executed after denial.
7. Approval target mismatches.
8. Private data reaching public sinks.
9. Secret data reaching public, model-visible, or private sinks.
10. Untrusted sources influencing privileged tool calls.
11. Sensitive data reaching final answers.
12. Unsupported final-answer claims.
13. Missing provenance edges from evidence to final answers.
14. Evidence events that occur after final answers.

Policy evaluation is intentionally explicit:

1. Structural validation gates policy evaluation.
2. Data-flow checks use only `data_flow` edges and event metadata labels.
3. Source metadata supports `source` and `sources`.
4. Sink metadata supports `sink` and `sinks`.
5. Tool-call arguments also synthesize sink labels as `tool_name.argument_name`.
6. Final answers synthesize the sink label `final_answer`.
7. Provenance checks use `Claim.evidence` and `provenance` edges.
8. Policy rule severities map to diagnostic severities.
9. Policy exceptions suppress exact matching diagnostics only.

## Current Reports And CI Behavior

Milestone 5 implements `agentlint check` as the report and CI command.

`agentlint check` supports:

1. One or more explicit native trace file paths.
2. Optional `--policy POLICY.yaml`.
3. `--format text`.
4. `--format json`.
5. `--fail-on error|warning|info|never`.

Reports use schema version:

```text
agentlint.report.v1
```

Report data includes:

1. AgentLint version.
2. Summary counts by trace status.
3. Summary counts by diagnostic severity.
4. Fail threshold.
5. Per-trace check results.
6. Diagnostics.
7. Sanitized trace input errors.
8. Redaction metadata.

Reports do not include raw trace payload values by default. User message content, developer instruction content, model inputs and outputs, tool arguments, tool results, final-answer content, and policy metadata values are omitted from report models.

`agentlint explain CODE` prints a short explanation for every supported diagnostic code.

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

Milestone 5 does not implement:

1. Directory traversal.
2. `--output` report file writing.
3. SARIF.
4. GitHub Actions workflow annotations.
5. HTML reports.
6. Pull request annotations.
7. External trace adapters.
8. Runtime gating.
9. Full value graph modeling.
10. Natural-language data-flow inference.
11. Provenance semantic relevance checking.
12. Contradiction detection.
13. Policy preset packaging.

Those pieces begin in later milestones.
