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

## Product Boundary

AgentLint is an offline deterministic checker for completed traces. The architecture is optimized for a developer workflow in which agent scenarios run during tests, supported adapters capture evidence, and AgentLint produces compiler-style diagnostics and a CI result.

The engine reasons only over represented facts. Framework-native capture, adapter declarations, and focused application annotations may supply those facts. Absence of a fact is not evidence that an unsafe event did not occur; policy-required missing evidence produces `not_verifiable`.

Policy-declared tool boundaries are a deterministic enrichment layer. A tool-result declaration may add a source label to an observed `tool_result`, and a tool-argument declaration may add a sink label to an observed `tool_call`. This enrichment never creates a `data_flow` edge; causal relationships remain explicit trace evidence.

The initial architecture does not include:

1. Runtime action authorization or enforcement.
2. Approval user interfaces or identity and role management.
3. General-purpose trace storage or observability dashboards.
4. Universal Python or cross-process taint tracking.
5. Natural-language inference of data flow.
6. Semantic truth or relevance judgments over final-answer claims.
7. Enterprise compliance or policy-administration services.

Runtime gates or probabilistic evaluators may later consume the same normalized facts, but they must remain separate product layers rather than expanding the deterministic linter's claims.

The accepted decision record is `Documents/architecture_decision_offline_trace_linter.md`.

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

Milestone 7 implements the first external adapter boundary with an OpenTelemetry importer. The importer normalizes supported OTLP-style JSON into native AgentLint IR v1, then existing structural checks, policy checks, and reports run unchanged.

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
agentlint.report.v4
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
9. Per-trace capture completeness.
10. Aggregate counts by overall capture status.

Reports do not include raw trace payload values by default. User message content, developer instruction content, model inputs and outputs, tool arguments, tool results, final-answer content, and policy metadata values are omitted from report models.

`agentlint explain CODE` prints a short explanation for every supported diagnostic code.

## Capture Completeness Direction

Milestone 8 implements an adapter-independent capture completeness contract before the first-class OpenAI Agents adapter.

Capture completeness records whether agent runs, model calls, tool calls, tool arguments, tool results, approvals, data flow, provenance, and final answers were `captured`, `partial`, `unavailable`, or `unknown`. It describes the evidence boundary of a trace; it is not a safety diagnostic and does not change whether represented behavior violates policy.

Completeness is attached to each trace so it survives normalization and appears in each report run. Existing native traces without a declaration remain valid and report `unknown`, because AgentLint cannot infer whether a hand-authored or externally generated trace is exhaustive.

Milestone 8 introduced `agentlint.report.v2`. Milestone 10 introduced report v3 with policy-specific evidence assessment and the `not_verifiable` outcome. Milestone 11 introduces report v4 with sanitized structured diagnostic paths.

## Current OpenTelemetry Adapter

Milestone 7 implements:

```text
agentlint import opentelemetry INPUT.json --output OUTPUT.json
```

The command imports a supported OTLP-style JSON trace into native AgentLint IR v1. Import warnings are printed to stderr, while the normalized native trace is written to the requested output file.

The adapter intentionally requires explicit `agentlint.*` attributes for agent-specific semantics. OpenTelemetry spans are generic operations, so AgentLint does not infer approvals, source/sink labels, data-flow edges, or provenance from arbitrary span names.

Important attributes include:

1. `agentlint.event.type`
2. `agentlint.event.id`
3. `agentlint.sequence`
4. `agentlint.content`
5. `agentlint.tool.name`
6. `agentlint.tool.arguments_json`
7. `agentlint.tool.result_json`
8. `agentlint.approval.decision`
9. `agentlint.approval.subject_event`
10. `agentlint.sources`
11. `agentlint.sinks`
12. `agentlint.data_flow.to`
13. `agentlint.approval_for.to`
14. `agentlint.provenance.to`
15. `agentlint.claims_json`

Parent span IDs become `parent` edges. Explicit AgentLint attributes become `data_flow`, `approval_for`, and `provenance` edges.

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

Milestone 9 additively extends IR v1 with framework events:

1. `agent_run`
2. `handoff`
3. `guardrail`

Existing passes remain framework-independent and ignore new event variants unless a check consumes them.

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

## Milestone 7 Non-Goals

Milestone 7 does not implement:

1. Directory traversal.
2. `--output` report file writing.
3. SARIF.
4. GitHub Actions workflow annotations.
5. HTML reports.
6. Pull request annotations.
7. OpenAI Agents SDK import.
8. Runtime gating.
9. Full value graph modeling.
10. Natural-language data-flow inference.
11. Provenance semantic relevance checking.
12. Contradiction detection.
13. Policy preset packaging.

Those pieces begin in later milestones.

## Current OpenAI Agents Adapter

Milestone 9 implements a first-class Python OpenAI Agents SDK integration using the SDK's tracing processor interface.

The integration separates capture from normalization:

```text
SDK traces and spans
  -> agentlint.openai_agents.snapshot.v1
  -> OpenAI Agents adapter
  -> AgentLint IR v1
  -> existing checks and report v4
```

Supported native mappings include agent runs, model generations or response records, function tools, handoffs, and guardrails. OpenAI Agents SDK 0.18.x `response` spans become structural `model_call` events; response ID is preserved as metadata while prompt/output payloads remain absent. One function span becomes a `tool_call` and, when output is available, a matching `tool_result`.

SDK custom spans named `task` and `turn` are recognized as transparent hierarchy containers. They do not become IR events, but parent relationships are collapsed through them to the nearest supported ancestor. Other custom span names remain unsupported and produce warnings. Parent edges use deterministic parent-first ordering.

The processor-only path reports approvals, data flow, provenance, and authoritative final answers as unavailable. Explicit session helpers can record a known approval or `RunResult.final_output`, improving that trace's corresponding coverage to partial without claiming exhaustive framework support.

## Milestone 10 Evidence Enforcement

Milestone 10 preserves the separation between behavioral diagnostics and capture completeness and adds policy-specific evidence assessment. Effective requirements are inferred from configured policy constructs and strengthened by optional `capture.require` policy entries.

A structurally valid trace with no known violation but insufficient required evidence is `not_verifiable`, not passed or failed. Invalid and not-verifiable traces produce nonzero CLI and pytest outcomes independently of diagnostic `--fail-on` thresholds. Reports use `agentlint.report.v4`, state required versus observed coverage, and may include sanitized paths containing only event labels and explicit edge references.

The OpenAI integration supports explicit semantic records for approvals, declared source/sink data-flow relationships, and authoritative final output. These helpers improve represented coverage but do not justify exhaustive claims. Implicit Python value tracking, generic child-process injection, and OPA/Rego remain deferred.
