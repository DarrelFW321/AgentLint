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

The AgentLint intermediate representation should be graph-shaped. Event order, data dependencies, approval links, and provenance links are different relationships over the same execution trace and should not be collapsed into a single event list.

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

Recommended first adapter: OpenAI Agents tracing.

Reasoning: it is agent-native and likely to produce a stronger initial safety demo than a generic span format.

Recommended second adapter: OpenTelemetry.

Reasoning: it gives AgentLint a broader interoperability story after the first agent-native adapter works.

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

## Milestone 8: Optional OPA/Rego Experiment

Goal: evaluate whether Rego is useful for advanced custom policies over AgentLint facts.

Deliverables:

1. `agentlint facts` command exporting derived facts JSON.
2. Experimental Rego input format.
3. Example Rego policies for simple tool and approval checks.
4. Documentation explaining that built-in AgentLint diagnostics remain the default.
5. Tests comparing equivalent built-in and Rego-backed decisions for a few simple cases.

Exit criteria:

1. Rego can express useful custom checks over AgentLint facts.
2. Rego integration does not weaken built-in diagnostics.
3. The project has enough evidence to decide whether Rego should remain experimental, become supported, or be deferred.

## Milestone 9: Research Evaluation

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

## Milestone 10: Runtime Gating Prototype

Goal: explore online policy decisions after the offline linter is stable.

Deliverables:

1. Partial-trace representation.
2. Pending-tool-call evaluation API.
3. Decisions:
   - `allow`
   - `block`
   - `warn`
   - `require_approval`
4. Decision logs for later audit.
5. Runtime-specific diagnostics for partial information.

Exit criteria:

1. Runtime checks reuse the same IR, policies, and analysis concepts where possible.
2. Partial-information limitations are explicit.
3. Runtime mode is treated as a separate product surface, not a replacement for offline CI checks.

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
