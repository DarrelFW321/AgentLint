# AgentLint Milestones

This document is the build roadmap for AgentLint. It turns the current product idea and research framing into implementation milestones with concrete deliverables and exit criteria.

## Finalized Direction

AgentLint should use a compiler-inspired trace analysis pipeline:

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

The compiler model is a good fit because AgentLint has multiple input formats, a canonical intermediate representation, analysis passes, diagnostics, and multiple report outputs. Product messaging should still stay simple: AgentLint imports traces, checks policies, and reports violations.

The roadmap is governed by one bounded product question:

> Did this recorded agent run violate a developer-defined policy that can be verified from the captured evidence?

Milestones should prioritize deterministic regression detection over completed agent tests. The initial product is not a runtime authorization system, approval interface, observability platform, universal taint tracker, semantic answer judge, or compliance suite. Tool policies are trace-conformance contracts; approvals, data flow, and provenance are checked only when represented by explicit evidence. Insufficient policy-required evidence produces `not_verifiable`.

The AgentLint intermediate representation should be graph-shaped. Event order, data dependencies, approval links, and provenance links are different relationships over the same execution trace and should not be collapsed into a single event list.

The post-Milestone 10 scope-alignment work is specified in `Documents/milestone_11_scope_alignment_implementation_plan.md`. M11 consolidates rule activation, evidence requirements, diagnostic paths, and the primary consumer workflow before another framework adapter is added.

## Rego And OPA Decision

OPA/Rego should not be the core policy engine for V1.

For V1, AgentLint should own:

1. The trace semantics.
2. The intermediate representation.
3. The analysis passes.
4. The built-in checks.
5. The diagnostics and remediation text.

The V1 policy interface should be a purpose-built YAML configuration. This will be easier for developers to adopt and easier for AgentLint to map to high-quality diagnostics.

OPA/Rego should be introduced later as an optional advanced backend over exported AgentLint facts:

```text
trace -> AgentLint IR -> AgentLint facts JSON -> Rego policy -> optional decisions
```

This preserves Rego's strength for custom declarative policy without making early AgentLint depend on a general-purpose policy language before the IR and diagnostics are stable.

## Initial Tooling

Recommended implementation stack:

1. Python 3.12 or newer.
2. uv for dependency and project management.
3. Pydantic for IR, policy, and report schemas.
4. Typer for the CLI.
5. Rich for human-readable terminal output.
6. PyYAML or ruamel.yaml for YAML policy files.
7. pytest for tests.
8. Ruff for linting and formatting.
9. Pyright or mypy for type checking.

Later or optional tools:

1. Hypothesis for malformed trace fuzzing.
2. pytest-benchmark for performance checks.
3. OPA CLI for Rego experiments.
4. SARIF output for code-scanning and CI integrations.
5. NetworkX only if the custom graph layer becomes too complex.

## Milestone 0: Project Skeleton And Research Baseline

Goal: establish the codebase, terminology, and research record before implementation grows.

Deliverables:

1. Python package skeleton.
2. CLI entry point.
3. Test harness.
4. Example directory layout for traces, policies, and expected reports.
5. Architecture note describing the pipeline.
6. Glossary for trace, event, value, source, sink, approval, claim, provenance, violation, and diagnostic.
7. Research note updated with early design decisions and limitations.

Exit criteria:

1. `agentlint --help` runs locally.
2. `pytest` runs with at least one placeholder or smoke test.
3. Documentation explains what the first implementation is and is not trying to prove.

## Milestone 1: Native Trace Format And IR

Goal: define the first canonical AgentLint trace representation.

Deliverables:

1. `agentlint.ir.v1` JSON schema.
2. Pydantic models for traces, events, values, edges, claims, and source references.
3. Event types:
   - `user_message`
   - `developer_instruction`
   - `model_call`
   - `tool_call`
   - `tool_result`
   - `approval`
   - `final_answer`
4. Edge types:
   - `parent`
   - `data_flow`
   - `approval_for`
   - `provenance`
5. Basic native JSON adapter.
6. CLI command to load and validate a native trace.

Exit criteria:

1. Valid native traces load into the IR.
2. Invalid native traces produce schema errors.
3. Raw source references are preserved for debugging.
4. Example passing and failing native traces exist.

## Milestone 2: Structural Trace Validation

Goal: prove the linter pipeline with checks that do not require complex policy logic.

Deliverables:

1. Structural validation pass.
2. Diagnostics model with code, severity, message, related events, policy reference, and remediation.
3. Checks for:
   - Duplicate event identifiers.
   - Missing event references.
   - Tool results without matching tool calls.
   - Tool calls with missing required arguments.
   - Invalid event ordering.
   - Final answers referencing nonexistent evidence.
4. Unit tests and fixture tests for each structural violation.

Exit criteria:

1. Structural violations produce stable diagnostic codes.
2. Diagnostics identify the relevant event IDs.
3. Human-readable output is understandable without opening the raw trace.

## Milestone 3: YAML Policy DSL V1

Goal: define a practical policy format for the first useful safety checks.

Deliverables:

1. Versioned YAML policy schema.
2. Policy loader and validator.
3. Policy concepts:
   - Tool permissions.
   - Approval requirements.
   - Tool risk levels.
   - Source sensitivity.
   - Sink visibility.
   - Trust labels.
   - Rule severity overrides.
   - Exceptions.
4. Example policies for customer-support, research, and coding agents.

Example shape:

```yaml
version: 1

tools:
  send_email:
    permission: allowed
    approval: required
    risk: high

sources:
  gmail.read:
    sensitivity: private

sinks:
  web_search.query:
    visibility: public

rules:
  unknown_tool: error
  missing_approval: error
  private_to_public_sink: error
  unsupported_claim: warning
```

Exit criteria:

1. Policies validate before trace checks run.
2. Policy errors are reported separately from trace violations.
3. Example policies can be used by the CLI.

## Milestone 4: Core Offline Safety Checks

Goal: make AgentLint useful on curated agent failure scenarios.

Deliverables:

1. Tool policy checks:
   - `UNKNOWN_TOOL`
   - `UNAUTHORIZED_TOOL_CALL`
   - `DISALLOWED_TOOL_ARGUMENT`
2. Approval checks:
   - `MISSING_APPROVAL`
   - `APPROVAL_AFTER_ACTION`
   - `ACTION_AFTER_DENIAL`
   - `APPROVAL_MISMATCH`
3. Data-flow checks:
   - `PRIVATE_TO_PUBLIC_SINK`
   - `SECRET_EXPOSURE`
   - `UNTRUSTED_TO_PRIVILEGED_ACTION`
   - `SENSITIVE_FINAL_ANSWER`
4. Provenance checks using explicit annotations:
   - `UNSUPPORTED_CLAIM`
   - `INVALID_PROVENANCE_REFERENCE`
   - `EVIDENCE_AFTER_CLAIM`

Exit criteria:

1. Each check has at least one failing fixture and one passing fixture.
2. Diagnostics explain what happened, why it violated policy, and what to inspect.
3. Analysis remains offline and does not send trace data to external services.

## Milestone 5: Reports And CI Behavior

Goal: make AgentLint usable in local development and continuous integration.

Deliverables:

1. Human-readable terminal report.
2. JSON report.
3. Summary output with counts by severity.
4. Exit code behavior based on `--fail-on`.
5. CLI commands:
   - `agentlint check`
   - `agentlint validate`
   - `agentlint explain`
6. Redaction support for sensitive values in reports.

Exit criteria:

1. CI can fail on errors while allowing warnings.
2. JSON reports are stable enough for automated consumers.
3. Human reports avoid leaking raw private or secret values by default.

## Milestone 6: Fixture Corpus And Test Discipline

Goal: create the evidence base for both engineering confidence and the future research note.

Deliverables:

1. Curated fixture corpus:
   - Passing traces.
   - Malformed traces.
   - Missing approval traces.
   - Private-to-public data-flow traces.
   - Unsupported-claim traces.
   - Untrusted-to-privileged-action traces.
2. Expected diagnostic snapshots or golden reports.
3. Parametrized pytest suite over fixtures.
4. Regression tests for every violation code.
5. Initial performance smoke test over multiple traces.

Exit criteria:

1. Every supported violation has a stable example.
2. Reports are deterministic across test runs.
3. Adding a new check requires adding at least one fixture.

## Milestone 7: First External Adapter

Goal: show that AgentLint can analyze traces from a real agent ecosystem.

Implemented first adapter direction: OpenTelemetry with explicit AgentLint semantic attributes.

Reasoning: it gives AgentLint a real external tracing ecosystem while keeping routine tests and demos offline and zero-cost. OpenAI Agents tracing remains the recommended next adapter because it is agent-native and likely to produce a stronger live demo, but it requires API billing for live runs.

Deliverables:

1. External trace importer.
2. Adapter-specific normalization tests.
3. Documentation showing source fields mapped into AgentLint IR fields.
4. At least one realistic external trace checked by existing policies.
5. Clear warnings when source traces lack metadata required for precise checks.

Exit criteria:

1. External traces normalize into the same IR as native traces.
2. Existing checks run without adapter-specific logic.
3. Unsupported or ambiguous source data produces actionable adapter diagnostics.

## Milestone 8: Capture Completeness Reporting

Goal: make the evidence boundary of every checked trace explicit before adding deeper framework integrations.

Deliverables:

1. Versioned capture completeness model with `captured`, `partial`, `unavailable`, and `unknown` states.
2. Per-trace capability coverage for agent runs, model calls, tool calls, tool arguments, tool results, approvals, data flow, provenance, and final answers.
3. Capture metadata preserved through external normalization into native IR.
4. Per-run and aggregate completeness in text and JSON reports.
5. Conservative OpenTelemetry capability declarations and degradation for dropped source data.
6. A report schema bump to `agentlint.report.v2`.
7. Redaction and determinism tests for completeness explanations.

Exit criteria:

1. A passing report cannot silently imply that unavailable or unknown semantics were verified.
2. Existing native traces remain valid and receive an unknown profile when completeness is undeclared.
3. OpenTelemetry completeness survives the import-to-check workflow.
4. Existing policy and structural behavior remains unchanged.

## Milestone 9: First-Class OpenAI Agents Capture Adapter

Goal: let users capture and check OpenAI Agents SDK test runs without manually creating spans or AgentLint IR.

Deliverables:

1. Versioned OpenAI Agents snapshot contract.
2. OpenAI Agents SDK trace processor integration.
3. Fixture-first mapping tests that require no API calls.
4. Capture-session lifecycle and deterministic trace flushing.
5. Additive IR events for agent runs, handoffs, and guardrails.
6. Mapping for model generations and function-tool call/result flows.
7. Completeness profiles based on framework guarantees and observed capture incidents.
8. One-line in-process activation and an explicitly activated pytest plugin.
9. Optional live demo gated by `OPENAI_API_KEY` and a small explicit budget.

Exit criteria:

1. An existing supported agent test can be captured with at most one central setup step or explicit pytest activation.
2. Existing AgentLint checks run without adapter-specific policy logic.
3. Missing framework semantics are visible through completeness and warnings.
4. Default tests remain offline and zero-cost.
5. Empty, disabled, failed, and unsupported capture cannot appear as a clean pass.

## Milestone 10: Semantic Capture and Verifiability

Goal: prevent a clean policy result when evidence required by that policy was not captured, and provide focused helpers for semantics OpenAI Agents tracing cannot expose.

Deliverables:

1. Policy-specific minimum capture requirements using `partial` or `captured` levels.
2. Framework-independent inference of evidence required by configured policy constructs.
3. A `not_verifiable` trace outcome separate from violations and invalid input.
4. Report schema v3 with unmet evidence requirements and aggregate counts.
5. Nonzero CLI and pytest outcomes for invalid or not-verifiable traces independent of `--fail-on`.
6. OpenAI capture helpers for authoritative approvals, declared source/sink flow, and final output.
7. OpenAI adapter hardening for failures, retries, multiple traces, handoffs, guardrails, sensitive-data-disabled capture, and supported SDK versions.
8. A realistic offline customer-support example with passing, failing, and not-verifiable scenarios.

Exit criteria:

1. A trace cannot pass when its effective policy evidence requirements are unmet.
2. Known violations remain visible when unrelated evidence is incomplete.
3. Users annotate only semantics unavailable from framework tracing and never write raw spans or AgentLint IR.
4. Semantic helpers persist labels and relationships without raw source or sink values.
5. The pytest workflow enforces violations, invalid traces, empty capture, and unverifiable results.
6. Default tests remain offline and zero-cost.

The finalized build plan is `Documents/milestone_10_implementation_plan.md`. OPA/Rego remains deferred until concrete policy-language limitations justify an experimental backend.

## Milestone 11: Scope Alignment and Developer Workflow

Goal: align implemented behavior with the offline deterministic trace-linting contract before expanding the product surface.

Deliverables:

1. One compiled rule plan shared by policy evaluation and evidence assessment.
2. Focused policy activation that does not require unrelated evidence.
3. Compiler-style diagnostic paths over explicit IR relationships.
4. Improved semantic-helper ergonomics where public framework context is reliable.
5. End-to-end tests for the primary pytest and one-line capture workflows.
6. A realistic deterministic regression corpus with explicit realism tiers.
7. Consumer documentation that distinguishes trace conformance from authorization, enforcement, and semantic evaluation.

Exit criteria:

1. A rule cannot require evidence unless that same compiled rule is active.
2. Focused policies activate only implied or explicitly enabled checks.
3. Diagnostic paths never invent relationships absent from the trace.
4. Passed, failed, invalid, and not-verifiable outcomes are covered end to end.
5. No runtime enforcement, automatic taint inference, or semantic fact-checking enters the milestone.

The finalized build plan is `Documents/milestone_11_scope_alignment_implementation_plan.md`.

## Milestone 12: Research Evaluation

Goal: collect results suitable for a technical report or arXiv note.

Deliverables:

1. Evaluation dataset of representative traces.
2. Table of violation categories and detected examples.
3. False positive and false negative notes on hand-labeled fixtures.
4. Adapter fidelity analysis.
5. Performance measurements for local and CI-scale trace sets.
6. Limitations section updated with observed failure modes.
7. Case studies:
   - Customer-support private data leak.
   - Email action without approval.
   - Research answer with unsupported claim.
   - Browser action influenced by untrusted content.
   - Coding agent secret exposure.

Exit criteria:

1. The research note contains enough material for a first paper outline.
2. Claims about AgentLint's capabilities are backed by examples or measurements.
3. Limitations are concrete rather than generic.

## Deferred Product Explorations

Runtime gating is not a scheduled milestone for the initial AgentLint product. It may be reconsidered only after the offline linter has been evaluated with real users and must remain a separate product layer.

A future runtime-gating research proposal could explore:

1. Partial-trace representation.
2. Pending-tool-call evaluation API.
3. Decisions:
   - `allow`
   - `block`
   - `warn`
   - `require_approval`
4. Decision logs for later audit.
5. Runtime-specific diagnostics for partial information.

Any such proposal must satisfy these boundaries:

1. Runtime checks reuse the same IR, policies, and analysis concepts where possible.
2. Partial-information limitations are explicit.
3. Runtime mode is treated as a separate product surface, not a replacement for offline CI checks.
4. Approval collection, identity management, and contextual authorization are not silently absorbed into the offline linter.

## Cross-Cutting Requirements

These requirements apply throughout the milestones.

1. Preserve raw source references for debugging.
2. Redact sensitive values by default in reports.
3. Keep diagnostics stable and code-addressable.
4. Avoid external network calls during analysis unless the user explicitly enables them.
5. Make unsupported trace metadata visible rather than silently ignoring it.
6. Keep examples realistic enough to support both developer adoption and research evaluation.
7. Prefer explicit annotations for V1 data flow and provenance before attempting semantic inference.

## Near-Term Build Order

The immediate implementation sequence should be:

1. Create package skeleton and CLI.
2. Define native IR models.
3. Add schema validation.
4. Add structural checks.
5. Add diagnostics and text output.
6. Add YAML policy loading.
7. Add approval and tool checks.
8. Add basic data-flow checks.
9. Add explicit provenance checks.
10. Add JSON reports and CI exit behavior.
