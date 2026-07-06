# Milestone 4 Architecture Decisions

Decision date: 2026-07-01

Status: finalized for Milestone 4 implementation.

This document records the resolved D4 decisions for Milestone 4. It should be treated as the implementation baseline for core offline safety checks.

## Current State Evaluation

The repository is at the Milestone 3 boundary:

1. Native AgentLint IR v1 traces load and validate.
2. Structural validation emits stable diagnostics.
3. YAML Policy DSL V1 policies load and validate.
4. `agentlint validate TRACE.json --policy POLICY.yaml` validates the policy but does not enforce it.
5. `DiagnosticCode` contains structural codes only.
6. `agentlint.passes` contains structural validation only.

The current IR has the minimum relationships needed for first enforcement:

1. `tool_call` events with `tool_name` and `arguments`.
2. `approval` events with `decision` and optional `subject_event`.
3. `data_flow`, `approval_for`, and `provenance` edges.
4. `final_answer` claims with explicit `evidence` event IDs.
5. Free-form event metadata for V1 source/sink labels.

Milestone 4 should therefore add policy evaluation over existing trace and policy objects. It should not add a new IR version, a report subsystem, external adapters, or a full value graph.

## Research Basis

Local sources reviewed:

1. `Documents/requirements_specification.md`
2. `Documents/milestones.md`
3. `Documents/architecture.md`
4. `Documents/research_note.md`
5. `Documents/milestone_3_architecture_decisions.md`
6. `Documents/milestone_3_build_report.md`
7. `Documents/milestone_4_implementation_plan.md`
8. `src/agentlint/diagnostics/models.py`
9. `src/agentlint/ir/v1/models.py`
10. `src/agentlint/passes/structural.py`
11. `src/agentlint/policy/models.py`
12. `src/agentlint/cli.py`

External references reviewed:

1. OWASP Top 10 for Large Language Model Applications: https://owasp.org/www-project-top-10-for-large-language-model-applications/
2. W3C PROV-DM: https://www.w3.org/TR/prov-dm/
3. NIST SP 800-162, Attribute Based Access Control: https://csrc.nist.gov/pubs/sp/800/162/upd2/final

Relevant research implications:

1. OWASP highlights prompt injection, sensitive information disclosure, insecure plugin design, and excessive agency as LLM application risks. Milestone 4 should therefore cover untrusted-to-privileged influence, secret/sensitive disclosure, and tool/approval enforcement.
2. W3C PROV-DM frames provenance as information about entities, activities, and agents used to assess trustworthiness. Milestone 4 should keep provenance explicit and structural rather than semantic.
3. NIST ABAC reinforces attribute-driven authorization. Milestone 4 policy checks should use explicit policy attributes such as tool permission, approval requirement, risk, source sensitivity, source trust, and sink visibility.

## Final Decision Summary

1. Milestone 4 implements offline policy evaluation over structurally valid traces.
2. Structural validation gates policy evaluation.
3. Policy checks live in `agentlint.passes.policy`.
4. Policy diagnostics extend `DiagnosticCode`.
5. Policy rule severities map to diagnostic severities.
6. Policy exceptions suppress exact matching diagnostics.
7. Tool and approval checks use current tool and approval event fields.
8. Data-flow checks use explicit event metadata and transitive `data_flow` edges.
9. Provenance checks use `Claim.evidence` and `provenance` edges.
10. `agentlint validate --policy` runs policy checks, but Milestone 5 still owns `check`, reports, JSON output, and CI threshold flags.

## ADR-001: Milestone 4 Scope Boundary

Decision:

Milestone 4 implements core offline safety checks only.

In scope:

1. Tool policy checks.
2. Approval checks.
3. Basic data-flow checks.
4. Basic provenance checks.
5. Policy diagnostics.
6. Policy severity mapping.
7. Policy exception suppression.
8. CLI execution through `validate --policy`.

Out of scope:

1. JSON reports.
2. Human report summaries beyond current diagnostic formatting.
3. `agentlint check`.
4. `--format`.
5. `--fail-on`.
6. Directory or multi-trace validation.
7. Full value graph modeling.
8. Semantic claim verification.
9. Contradiction detection.
10. External adapters.
11. Runtime gating.
12. OPA/Rego.

Reasoning:

Milestone 4 must prove that AgentLint can find meaningful policy violations. It should not also redesign the CLI/report surface or infer data flow from raw natural language. Those concerns belong to later milestones.

Consequences:

1. Policy enforcement is available only through `agentlint validate --policy` for now.
2. Diagnostics remain the primary output.
3. Report and CI ergonomics remain Milestone 5 work.

## ADR-002: Policy Evaluation Pass Ownership

Decision:

Policy evaluation lives in:

```text
src/agentlint/passes/policy.py
```

Public API:

```python
def evaluate_policy(trace: Trace, policy: Policy) -> list[Diagnostic]:
    ...
```

Reasoning:

Policy evaluation is an analysis pass over an already parsed trace and policy. It should not live in the policy loader, IR model, diagnostics package, or CLI.

Consequences:

1. `agentlint.policy` continues to own policy schema and loading.
2. `agentlint.passes` owns analysis logic.
3. The CLI only orchestrates load, structural validation, policy evaluation, formatting, and exit code.

## ADR-003: Structural Validation Gates Policy Evaluation

Decision:

Policy evaluation runs only after structural validation emits no error diagnostics.

Reasoning:

Policy checks depend on unique event IDs, valid references, coherent tool call/result matching, and valid claim evidence references. Running policy checks on structurally invalid traces would produce arbitrary or noisy follow-on diagnostics.

Consequences:

1. `agentlint validate --policy` prints structural diagnostics and exits before policy evaluation when structural errors exist.
2. Policy pass code can assume event IDs are unique and references used by structural relationships resolve.
3. Tests should cover that structural failures gate policy evaluation.

## ADR-004: Policy Diagnostic Codes

Decision:

Add these policy diagnostic codes:

1. `UNKNOWN_TOOL`
2. `UNAUTHORIZED_TOOL_CALL`
3. `DISALLOWED_TOOL_ARGUMENT`
4. `MISSING_APPROVAL`
5. `APPROVAL_AFTER_ACTION`
6. `ACTION_AFTER_DENIAL`
7. `APPROVAL_MISMATCH`
8. `PRIVATE_TO_PUBLIC_SINK`
9. `SECRET_EXPOSURE`
10. `UNTRUSTED_TO_PRIVILEGED_ACTION`
11. `SENSITIVE_FINAL_ANSWER`
12. `UNSUPPORTED_CLAIM`
13. `INVALID_PROVENANCE_REFERENCE`
14. `EVIDENCE_AFTER_CLAIM`

Reasoning:

Milestone 3 defined `RuleId` values but did not emit diagnostics. Milestone 4 now implements concrete findings, so diagnostic codes should be added.

Consequences:

1. Structural diagnostic codes remain unchanged.
2. `INVALID_EVIDENCE_REFERENCE` remains structural and means a claim evidence event ID does not exist.
3. `INVALID_PROVENANCE_REFERENCE` is policy/provenance-specific and means the required provenance relationship is invalid or missing.

## ADR-005: Rule Severity Mapping

Decision:

Policy severity controls emitted diagnostic severity:

```text
off     -> no diagnostic
info    -> Severity.INFO
warning -> Severity.WARNING
error   -> Severity.ERROR
```

Default severities:

1. Error: all tool, approval, data-flow, and invalid-provenance rules.
2. Warning: `unsupported_claim` and `evidence_after_claim`.

Reasoning:

Policies should work even when they omit some rule severities, but explicit policy configuration must win. `off` supports gradual adoption.

Consequences:

1. Missing rule severity falls back to defaults.
2. A rule configured as `off` suppresses that rule before exception matching.
3. Warning-only and info-only diagnostics should not produce a non-zero exit in Milestone 4.

## ADR-006: Policy Reference

Decision:

Every policy diagnostic should set:

```text
policy_reference = "{policy_id}:{rule_id}"
```

Example:

```text
customer_support_v1:missing_approval
```

Reasoning:

The diagnostic model already has `policy_reference`. Filling it now improves CLI output and gives Milestone 5 reports a stable field.

Consequences:

1. Structural diagnostics may leave `policy_reference` empty.
2. Policy diagnostics should always include it.

## ADR-007: Diagnostic Ordering

Decision:

Policy diagnostics should be emitted deterministically in this order:

1. Tool checks in trace event order.
2. Approval target/mismatch checks in trace event order.
3. Required approval checks in trace event order.
4. Data-flow checks by sink/action event order, then source event order.
5. Provenance checks by final-answer event order, then claim order.

Reasoning:

Deterministic output is necessary for tests, future snapshots, and developer trust. Ordering by trace sequence makes diagnostics easier to inspect.

Consequences:

1. Tests should assert ordered code lists for multi-failure cases.
2. Avoid set iteration in user-visible diagnostic ordering.

## ADR-008: Policy Exceptions

Decision:

Implement exact-match exception suppression.

An exception matches a candidate diagnostic only when:

1. The candidate rule ID is in `exception.rules`.
2. `match.tool`, if set, equals the candidate tool context.
3. `match.source`, if set, equals the candidate source context.
4. `match.sink`, if set, equals the candidate sink context.
5. `match.event`, if set, equals one of the candidate related event IDs.

Do not evaluate `expires` in Milestone 4.

Reasoning:

Exceptions are required for practical adoption, but wildcard matching, expression logic, and expiration handling would make Milestone 4 too broad.

Consequences:

1. Suppression happens before diagnostics are returned.
2. Suppressed diagnostics do not appear in CLI output.
3. Expired exception warnings are deferred until reports or policy health checks exist.

## ADR-009: Tool Checks

Decision:

Implement tool checks on `ToolCallEvent`.

Rules:

1. `UNKNOWN_TOOL`: tool name does not exist in `policy.tools`.
2. `UNAUTHORIZED_TOOL_CALL`: tool exists and `permission` is `denied`.
3. `DISALLOWED_TOOL_ARGUMENT`: required argument is missing, type is not allowed, or value is not allowed.

Additional decisions:

1. Unknown argument names are allowed in Milestone 4 unless a configured argument policy explicitly constrains them.
2. Unknown tools do not run authorization, argument, or approval checks.
3. Denied tools do not run argument or approval checks.
4. Missing `arguments is None` remains structural validation.

JSON type mapping:

1. `null`: `None`
2. `boolean`: `bool`
3. `integer`: `int` excluding `bool`
4. `number`: `int` or `float` excluding `bool`
5. `string`: `str`
6. `array`: `list`
7. `object`: `dict`

Reasoning:

The Milestone 3 policy model supports shallow constraints. Enforcing only configured argument policies avoids accidental strict mode before a full tool-schema language exists.

Consequences:

1. `DISALLOWED_TOOL_ARGUMENT` should include the tool call event and argument name in the message.
2. Later milestones may add `allow_extra_arguments` or JSON Schema support.

## ADR-010: Approval Checks

Decision:

Implement approval checks using `ApprovalEvent.subject_event` and `approval_for` edges.

Approval target resolution:

1. `ApprovalEvent.subject_event` identifies the target if present.
2. An `approval_for` edge from an approval event to another event identifies a target.
3. If both forms exist and disagree, emit `APPROVAL_MISMATCH`.
4. If a target is not a `ToolCallEvent`, emit `APPROVAL_MISMATCH`.

Required approval rules:

1. Only known, allowed tools with `approval: required` need approval checks.
2. A prior `approved` approval satisfies the requirement.
3. A prior `denied` approval emits `ACTION_AFTER_DENIAL`.
4. An `approved` approval after the tool call emits `APPROVAL_AFTER_ACTION`.
5. No approval or denial emits `MISSING_APPROVAL`.

Avoid cascading:

1. `ACTION_AFTER_DENIAL` suppresses `MISSING_APPROVAL` for the same tool call.
2. `APPROVAL_AFTER_ACTION` suppresses `MISSING_APPROVAL` for the same tool call.

Reasoning:

This uses the existing IR without introducing runtime pending-action events. It is enough to catch missing, late, denied, and mismatched approvals in recorded traces.

Consequences:

1. Approval checks should not run for unknown or denied tools.
2. Approval checks are sequence-based, not timestamp-based.
3. Multiple prior approvals can be treated as satisfied if at least one prior approved event targets the action and no prior denied event targets it.

## ADR-011: V1 Data-Flow Metadata Convention

Decision:

Use explicit event metadata and `data_flow` edges for V1 data-flow checks.

Supported metadata fields:

```json
{
  "metadata": {
    "source": "customer_profile",
    "sources": ["customer_profile"],
    "sink": "web_search.query",
    "sinks": ["web_search.query"]
  }
}
```

Derived sink labels:

1. `ToolCallEvent` arguments synthesize `tool_name.argument_name` sink labels.
2. `FinalAnswerEvent` synthesizes `final_answer`.

Unknown labels:

1. Source labels not found in `policy.sources` are ignored.
2. Sink labels not found in `policy.sinks` are ignored, except `final_answer` remains usable for `SENSITIVE_FINAL_ANSWER`.
3. Non-string metadata labels are ignored.

Reasoning:

Milestone 4 needs concrete data-flow checks, but the full value graph is deferred. Explicit metadata and event-level data-flow edges provide a practical V1 binding.

Consequences:

1. No natural-language inference.
2. No tool payload inspection for source labels.
3. Fixture metadata should make sources and sinks explicit.

## ADR-012: Data-Flow Reachability

Decision:

Use transitive reachability over `data_flow` edges only.

Rules:

1. Build a directed graph from `data_flow` edges.
2. For each sink/action/final-answer event, compute upstream source-labeled events.
3. Traverse with a visited set to handle cycles.
4. Do not infer data flow from `parent`, `approval_for`, or `provenance` edges.

Reasoning:

Explicit data-flow edges should carry data dependency semantics. Parent order and provenance links answer different questions.

Consequences:

1. Data-flow precision depends on trace annotations.
2. Missing data-flow edges may lead to false negatives in Milestone 4.
3. This limitation should be documented.

## ADR-013: Data-Flow Checks

Decision:

Implement:

1. `PRIVATE_TO_PUBLIC_SINK`
2. `SECRET_EXPOSURE`
3. `UNTRUSTED_TO_PRIVILEGED_ACTION`
4. `SENSITIVE_FINAL_ANSWER`

Rules:

1. Private-to-public: a `private` or `secret` source reaches a `public` sink.
2. Secret exposure: a `secret` source reaches a `public`, `model`, or `private` sink.
3. Untrusted-to-privileged: an `untrusted` source reaches a tool call whose tool policy is high/critical risk, requires approval, or is denied.
4. Sensitive final answer: a `private` or `secret` source reaches a final answer.

Avoid cascading:

1. If `SECRET_EXPOSURE` is emitted for the same source/sink/event combination, suppress `PRIVATE_TO_PUBLIC_SINK` for that combination.
2. `SENSITIVE_FINAL_ANSWER` may coexist with `SECRET_EXPOSURE` because it describes final-answer exposure specifically.

Reasoning:

These checks cover the first useful safety cases while staying explicit and deterministic.

Consequences:

1. Data-flow diagnostics should include source and sink context for exception matching.
2. Diagnostics should not print raw source data.

## ADR-014: Provenance Checks

Decision:

Implement provenance checks over `FinalAnswerEvent.claims`, `Claim.evidence`, and `provenance` edges.

Rules:

1. `UNSUPPORTED_CLAIM`: claim has no evidence.
2. `INVALID_PROVENANCE_REFERENCE`: claim evidence exists but no `provenance` edge connects evidence event to final answer event.
3. `EVIDENCE_AFTER_CLAIM`: evidence event sequence is greater than final answer event sequence.

Boundaries:

1. Missing evidence event IDs remain structural `INVALID_EVIDENCE_REFERENCE`.
2. Do not check evidence relevance.
3. Do not detect contradiction.
4. Do not require claim-specific provenance edges beyond event-to-final-answer links.

Reasoning:

W3C PROV supports explicit provenance relationships, but AgentLint V1 should keep the check structural and transparent. Semantic relevance is deferred.

Consequences:

1. Provenance fixtures should include explicit evidence IDs.
2. `provenance` edges are required for supported claims in Milestone 4.

## ADR-015: CLI Behavior

Decision:

Extend `agentlint validate --policy` from pre-validation to enforcement.

Behavior without policy:

1. Load trace.
2. Run schema and structural validation.
3. Print existing success output.

Behavior with policy:

1. Load policy.
2. Load trace.
3. Run structural validation.
4. If structural errors exist, print them and exit `1`.
5. Run policy evaluation.
6. Print policy diagnostics to stderr.
7. Exit `1` if any emitted diagnostic has severity `error`.
8. Exit `0` if diagnostics are only `warning` or `info`.

Success stdout:

```text
valid policy: customer_support_v1
valid trace: trace_id
events: N
edges: N
diagnostics: N
```

Reasoning:

Milestone 4 needs a way to execute checks, and the existing `validate --policy` path is the smallest extension. The larger command/report surface remains Milestone 5.

Consequences:

1. `diagnostics: N` should include structural plus policy diagnostics.
2. Warnings may produce diagnostics and still exit `0`.
3. No `agentlint check` command yet.

## ADR-016: Fixture Strategy

Decision:

Keep Milestone 4 fixtures flat and explicit.

Trace fixtures:

1. Add at least one passing fixture per check family.
2. Add one failing fixture per policy diagnostic code.
3. Use metadata labels directly in traces for data-flow tests.
4. Keep fixtures synthetic and small.

Policy fixtures:

1. Reuse Milestone 3 example policies where practical.
2. Add narrow policy fixtures for severity and exception behavior.

Reasoning:

Milestone 6 owns broader fixture corpus discipline and golden report snapshots. Milestone 4 should create focused regression examples.

Consequences:

1. Fixture names should include the diagnostic code theme.
2. Tests should map fixture names to expected diagnostic codes.

## ADR-017: Test Strategy

Decision:

Add:

```text
tests/test_policy_pass.py
```

And update:

```text
tests/test_cli.py
tests/test_diagnostics.py
```

Required coverage:

1. Every Milestone 4 diagnostic code.
2. Passing tool, approval, data-flow, and provenance fixtures.
3. Rule severity mapping, including `off`, `info`, `warning`, and `error`.
4. Exception suppression and non-suppression.
5. Structural validation gating.
6. CLI policy diagnostics and exit codes.

Reasoning:

The policy pass will have enough branching to deserve a dedicated test file. CLI tests should stay narrow and not duplicate all pass tests.

## ADR-018: Deferred Work

Decision:

Defer:

1. Full value graph.
2. Natural-language data-flow inference.
3. Tool-result semantic inspection.
4. Claim/evidence semantic relevance.
5. Contradiction detection.
6. JSON reports.
7. Redaction policy.
8. `agentlint check`.
9. `--fail-on`.
10. Runtime gating.

Reasoning:

Milestone 4 should prove concrete offline checks. These deferred items need report contracts, adapter fidelity, or semantic analysis beyond the current IR.

## Implementation Checklist Impact

The Milestone 4 implementation plan should align to these decisions:

1. Add deterministic policy diagnostic ordering.
2. Ignore unknown source/sink metadata labels instead of failing.
3. Do not treat unknown argument names as disallowed in Milestone 4.
4. Use exact-match exception suppression only.
5. Keep structural validation as the policy-evaluation gate.
6. Keep `validate --policy` as the only policy enforcement CLI path until Milestone 5.
