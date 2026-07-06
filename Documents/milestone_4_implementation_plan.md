# Milestone 4 Implementation Plan

Status: finalized for implementation.

Milestone 4 is the first policy-enforcement milestone. Milestone 3 made policies loadable and validated; Milestone 4 should evaluate those policies against native AgentLint IR traces and emit actionable diagnostics for curated failure scenarios.

## Objective

Implement core offline safety checks over structurally valid native traces.

Milestone 4 is complete when:

1. AgentLint can evaluate a validated policy against a native trace.
2. Tool, approval, data-flow, and provenance policy checks emit stable diagnostics.
3. Policy rule severities map to diagnostic severities.
4. Policy exceptions can suppress matching policy diagnostics.
5. `agentlint validate TRACE.json --policy POLICY.yaml` runs structural validation first, then policy checks.
6. Each Milestone 4 diagnostic code has at least one failing fixture and one passing fixture.
7. Diagnostics explain the policy rule, related trace events, and remediation.

## Current Baseline

Milestone 3 implemented:

1. Native trace schema validation.
2. Structural trace validation.
3. Diagnostic models and formatting.
4. YAML policy models and loader.
5. Policy examples.
6. `agentlint policy validate POLICY.yaml`.
7. `agentlint validate TRACE.json --policy POLICY.yaml` as policy pre-validation only.

Current enforcement gap:

1. `agentlint validate --policy` validates the policy file but does not evaluate it.
2. `DiagnosticCode` contains only structural diagnostic codes.
3. `agentlint.passes` contains only `validate_structure`.
4. There is no policy evaluation pass.
5. Data-flow and provenance checks have no V1 metadata binding convention yet.

## Finalized Scope

Milestone 4 should implement:

1. Policy diagnostic codes.
2. Policy severity mapping.
3. Policy exception matching.
4. Tool policy checks.
5. Approval checks.
6. Basic data-flow checks using explicit event metadata and `data_flow` edges.
7. Basic provenance checks using `Claim.evidence` and `provenance` edges.
8. Policy fixtures and tests.
9. CLI execution of policy checks via `validate --policy`.
10. Documentation and build report updates.

Milestone 4 should not implement:

1. A new `agentlint check` command.
2. JSON reports.
3. `--format`.
4. `--fail-on`.
5. Directory or multiple-trace traversal.
6. Report redaction.
7. Full value graph modeling.
8. Semantic contradiction detection.
9. Model-assisted claim verification.
10. External trace adapters.
11. Runtime gating.
12. OPA/Rego.

## Reevaluated Decisions

### D4.1 Policy Evaluation Pass Ownership

Decision:

Create a policy evaluation pass under `agentlint.passes`.

Proposed public API:

```python
def evaluate_policy(trace: Trace, policy: Policy) -> list[Diagnostic]:
    ...
```

Files:

```text
src/agentlint/passes/policy.py
src/agentlint/passes/__init__.py
```

Reasoning:

The loader should return parsed policy objects only, and the CLI should orchestrate. Policy checks are analysis passes over a trace and policy, so they belong beside structural validation.

Implementation consequence:

1. Keep policy models in `agentlint.policy`.
2. Keep policy evaluation in `agentlint.passes.policy`.
3. Future report emitters can consume diagnostics from both structural and policy passes.

### D4.2 Structural Validation Gates Policy Evaluation

Decision:

`agentlint validate --policy` should run policy checks only after trace loading and structural validation succeed without error diagnostics.

Reasoning:

Policy checks depend on coherent event references, event ordering, tool-call/result relationships, and evidence references. Running policy checks on structurally invalid traces would create noisy or misleading follow-on diagnostics.

Implementation consequence:

CLI order:

```text
load policy if provided
load trace
run structural validation
if structural error diagnostics: print them and exit 1
if policy provided: run policy evaluation
print policy diagnostics and fail only on error severity
```

### D4.3 Diagnostic Codes

Decision:

Add Milestone 4 policy diagnostic codes to `DiagnosticCode`.

Codes:

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

Milestone 3 defined rule IDs but deliberately did not add diagnostic codes. Milestone 4 now emits concrete findings, so diagnostic codes should be stable and code-addressable.

Implementation consequence:

1. Keep existing structural codes unchanged.
2. Map each `RuleId` to a `DiagnosticCode`.
3. Keep `INVALID_EVIDENCE_REFERENCE` as a structural code for missing claim evidence event IDs.
4. Use `INVALID_PROVENANCE_REFERENCE` for policy/provenance relationship failures, such as claim evidence lacking a required provenance edge.

### D4.4 Rule Severity Mapping

Decision:

Policy rule severity controls emitted diagnostic severity.

Mapping:

```text
PolicySeverity.ERROR   -> Severity.ERROR
PolicySeverity.WARNING -> Severity.WARNING
PolicySeverity.INFO    -> Severity.INFO
PolicySeverity.OFF     -> no diagnostic
```

If a policy omits a rule severity, use built-in defaults:

```text
error: all tool, approval, data-flow, and invalid-provenance rules
warning: unsupported_claim, evidence_after_claim
```

Reasoning:

Policies should not need to list every rule to get useful checks, but explicit policy severity must win. `off` supports gradual adoption.

Implementation consequence:

Create helpers such as:

```python
def severity_for_rule(policy: Policy, rule_id: RuleId) -> Severity | None: ...
def diagnostic_for_rule(...): ...
```

### D4.5 Policy Reference Field

Decision:

Set `Diagnostic.policy_reference` to:

```text
POLICY_ID:RULE_ID
```

Example:

```text
customer_support_v1:missing_approval
```

Reasoning:

Milestone 5 reports will need policy references. Milestone 4 can populate the existing field without introducing reports.

Implementation consequence:

All policy diagnostics should set:

```python
policy_reference=f"{policy.policy_id}:{rule_id.value}"
```

Policy diagnostics should be returned deterministically:

1. Tool checks in trace event order.
2. Approval target and mismatch checks in trace event order.
3. Required approval checks in trace event order.
4. Data-flow checks by sink/action event order, then source event order.
5. Provenance checks by final-answer event order, then claim order.

### D4.6 Policy Exceptions

Decision:

Implement basic policy exception suppression in Milestone 4.

Exception matching rules:

1. Exception applies only if the emitted rule ID is listed in `exception.rules`.
2. If `match.tool` is set, it must equal the diagnostic tool context.
3. If `match.source` is set, it must equal the diagnostic source context.
4. If `match.sink` is set, it must equal the diagnostic sink context.
5. If `match.event` is set, it must equal one of the diagnostic related event IDs.
6. Ignore `expires` in Milestone 4.

Reasoning:

Exceptions are part of the policy language and are important for adoption. Exact-match suppression is useful and small enough for Milestone 4. Expiration semantics can wait until reports and CI workflows exist.

Implementation consequence:

Create an internal context object or simple helper:

```python
class PolicyDiagnosticContext:
    rule_id: RuleId
    tool: str | None
    source: str | None
    sink: str | None
    related_events: list[str]
```

Suppress diagnostics before returning them from `evaluate_policy`.

### D4.7 Tool Policy Checks

Decision:

Implement these checks for `ToolCallEvent` events:

1. `UNKNOWN_TOOL`
2. `UNAUTHORIZED_TOOL_CALL`
3. `DISALLOWED_TOOL_ARGUMENT`

Rules:

1. Unknown tool: `event.tool_name` is absent from `policy.tools`.
2. Unauthorized tool call: tool policy `permission` is `denied`.
3. Required argument missing: an `ArgumentPolicy.required` argument key is absent.
4. Disallowed argument type: value type is not in `allowed_types`.
5. Disallowed argument value: value is not in `allowed_values`.
6. Extra argument names without matching `ArgumentPolicy` entries are allowed.

Avoid cascading:

1. If tool is unknown, do not run authorization, approval, or argument checks for that call.
2. If tool is denied, emit `UNAUTHORIZED_TOOL_CALL` and skip argument checks.
3. Missing `arguments is None` remains structural validation and should stop policy checks before this pass runs.

JSON type mapping:

1. `null`: `None`
2. `boolean`: `bool`
3. `integer`: `int` excluding `bool`
4. `number`: `int` or `float` excluding `bool`
5. `string`: `str`
6. `array`: `list`
7. `object`: `dict`

Reasoning:

These checks directly use Milestone 3 tool policy fields and produce immediately useful findings without a full tool-schema language.

### D4.8 Approval Checks

Decision:

Implement approval checks over `ApprovalEvent`, `approval_for` edges, and `ApprovalEvent.subject_event`.

Checks:

1. `MISSING_APPROVAL`
2. `APPROVAL_AFTER_ACTION`
3. `ACTION_AFTER_DENIAL`
4. `APPROVAL_MISMATCH`

Approval target resolution:

1. `ApprovalEvent.subject_event` is a target if present.
2. An `approval_for` edge from approval event to another event is also a target.
3. If both are present and disagree, emit `APPROVAL_MISMATCH`.
4. If an approval target resolves to an event that is not a `ToolCallEvent`, emit `APPROVAL_MISMATCH`.

Tool-call approval evaluation:

1. Only known allowed tools with `approval: required` need approval checks.
2. Prior `denied` approval for the tool call emits `ACTION_AFTER_DENIAL`.
3. Prior `approved` approval satisfies the requirement.
4. Approved approval after the tool call emits `APPROVAL_AFTER_ACTION`.
5. No matching approval or denial emits `MISSING_APPROVAL`.

Avoid cascading:

1. If `ACTION_AFTER_DENIAL` is emitted, do not also emit `MISSING_APPROVAL`.
2. If `APPROVAL_AFTER_ACTION` is emitted, do not also emit `MISSING_APPROVAL`.

Reasoning:

This uses the current IR without adding approval request events or runtime gating concepts.

### D4.9 V1 Data-Flow Metadata Convention

Decision:

Use explicit event metadata and event-level `data_flow` edges for Milestone 4 data-flow checks.

Metadata conventions:

```json
{
  "metadata": {
    "sources": ["customer_profile"],
    "sinks": ["web_search.query"]
  }
}
```

Supported forms:

1. `metadata.sources`: list of source names.
2. `metadata.source`: one source name, accepted as shorthand.
3. `metadata.sinks`: list of sink names.
4. `metadata.sink`: one sink name, accepted as shorthand.

Derived sink labels:

1. `ToolCallEvent` arguments synthesize sink labels as `tool_name.argument_name`.
2. `FinalAnswerEvent` synthesizes the sink label `final_answer`.

Unknown labels:

1. Source labels not found in `policy.sources` are ignored.
2. Sink labels not found in `policy.sinks` are ignored, except `final_answer` remains usable for `SENSITIVE_FINAL_ANSWER`.
3. Non-string source/sink metadata labels are ignored.

Reasoning:

The full value graph remains deferred, but Milestone 4 needs concrete, testable data-flow checks. Event-level metadata plus `data_flow` edges is enough for curated fixtures and keeps adapter binding flexible.

Implementation consequence:

1. Add helpers to normalize metadata values into `list[str]`.
2. Ignore unknown and non-string source/sink labels rather than emitting schema errors; metadata is free-form JSON.
3. Add fixture comments in docs or fixture names to make metadata conventions visible.

### D4.10 Data-Flow Reachability

Decision:

Use transitive reachability over `data_flow` edges.

Rules:

1. Build a directed graph from edges where `edge.type == "data_flow"`.
2. For each sink/action/final-answer event, find upstream source-labeled events.
3. Only traverse unique event IDs after structural validation succeeds.
4. Do not infer data flow from parent edges.

Reasoning:

Data-flow checks should follow explicit data dependencies rather than chronological order. Transitive reachability catches multi-step flows while staying deterministic.

Implementation consequence:

Create internal helpers:

```python
def upstream_events(trace: Trace, event_id: str) -> list[Event]: ...
def source_labels(event) -> list[str]: ...
def sink_labels(event) -> list[str]: ...
```

### D4.11 Data-Flow Checks

Decision:

Implement these checks:

1. `PRIVATE_TO_PUBLIC_SINK`
2. `SECRET_EXPOSURE`
3. `UNTRUSTED_TO_PRIVILEGED_ACTION`
4. `SENSITIVE_FINAL_ANSWER`

Rules:

1. `PRIVATE_TO_PUBLIC_SINK`: a source with sensitivity `private` or `secret` reaches a sink with visibility `public`.
2. `SECRET_EXPOSURE`: a source with sensitivity `secret` reaches any sink with visibility `public`, `model`, or `private`.
3. `UNTRUSTED_TO_PRIVILEGED_ACTION`: a source with trust `untrusted` reaches a tool call whose tool policy has risk `high` or `critical`, approval `required`, or permission `denied`.
4. `SENSITIVE_FINAL_ANSWER`: a source with sensitivity `private` or `secret` reaches a final answer.

Avoid cascading:

1. If a `SECRET_EXPOSURE` diagnostic is emitted for a source/sink/event combination, do not also emit `PRIVATE_TO_PUBLIC_SINK` for the same combination.
2. `SENSITIVE_FINAL_ANSWER` may coexist with `SECRET_EXPOSURE` because it describes a different policy concern.

Reasoning:

These rules cover the key V1 data-handling scenarios while keeping semantics explicit and fixture-driven.

### D4.12 Provenance Checks

Decision:

Implement provenance checks using `FinalAnswerEvent.claims`, `Claim.evidence`, and `provenance` edges.

Checks:

1. `UNSUPPORTED_CLAIM`
2. `INVALID_PROVENANCE_REFERENCE`
3. `EVIDENCE_AFTER_CLAIM`

Rules:

1. Unsupported claim: a claim has an empty `evidence` list.
2. Invalid provenance reference: a claim evidence event exists but there is no `provenance` edge from the evidence event to the final answer event.
3. Evidence after claim: an evidence event sequence is greater than the final answer event sequence.

Boundary:

1. Missing evidence event IDs remain `INVALID_EVIDENCE_REFERENCE` from structural validation.
2. Do not check semantic relevance of evidence text.
3. Do not detect contradictions.
4. Do not require every provenance edge to be claim-specific.

Reasoning:

This makes explicit claim-to-evidence annotations useful without requiring model-assisted semantic checking. It also aligns with the existing graph-shaped IR and W3C-style provenance framing.

### D4.13 CLI Behavior

Decision:

Extend existing `agentlint validate --policy` behavior.

Without policy:

```text
agentlint validate TRACE.json
```

Still runs schema and structural validation only.

With policy:

```text
agentlint validate TRACE.json --policy POLICY.yaml
```

Runs:

1. Policy load/schema validation.
2. Trace load/schema validation.
3. Structural validation.
4. Policy evaluation if structural validation has no error diagnostics.

Output:

1. Policy load/schema errors print to stderr and exit `1`.
2. Structural diagnostics print to stderr and exit based on error severity.
3. Policy diagnostics print to stderr.
4. Success stdout includes `diagnostics: N` for structural plus policy diagnostics.
5. Exit `1` if any emitted diagnostic has severity `error`.
6. Exit `0` if diagnostics are only `warning` or `info`.

Do not add:

1. `agentlint check`
2. `--format`
3. `--fail-on`
4. JSON output

Reasoning:

Milestone 5 owns the final command/report/CI surface. Milestone 4 still needs a usable way to run checks, and `validate --policy` is already the current integration point.

### D4.14 Fixture Strategy

Decision:

Keep Milestone 4 fixtures flat under `examples/traces/`.

Required passing fixtures:

1. `policy_tool_valid.json`
2. `policy_approval_valid.json`
3. `policy_data_flow_valid.json`
4. `policy_provenance_valid.json`

Required failing fixtures:

1. `policy_unknown_tool.json`
2. `policy_unauthorized_tool_call.json`
3. `policy_disallowed_tool_argument.json`
4. `policy_missing_approval.json`
5. `policy_approval_after_action.json`
6. `policy_action_after_denial.json`
7. `policy_approval_mismatch.json`
8. `policy_private_to_public_sink.json`
9. `policy_secret_exposure.json`
10. `policy_untrusted_to_privileged_action.json`
11. `policy_sensitive_final_answer.json`
12. `policy_unsupported_claim.json`
13. `policy_invalid_provenance_reference.json`
14. `policy_evidence_after_claim.json`

Policy fixtures:

1. Reuse `examples/policies/customer_support.yaml`, `research.yaml`, and `coding.yaml` where possible.
2. Add narrow policy fixtures only when needed to test severity overrides or exceptions.

Reasoning:

Milestone 6 will introduce larger fixture corpus discipline. Milestone 4 should keep fixtures focused and directly tied to each diagnostic code.

### D4.15 Test Strategy

Decision:

Add focused tests for pass behavior, CLI behavior, severity, and exceptions.

Files:

```text
tests/test_policy_pass.py
tests/test_cli.py
tests/test_diagnostics.py
```

Coverage:

1. Every policy diagnostic code.
2. Passing fixture for each check family.
3. Rule severity mapping, including `off`.
4. Warning-only diagnostics exit `0`.
5. Error diagnostics exit `1`.
6. Policy exceptions suppress matching diagnostics.
7. Exceptions do not suppress non-matching diagnostics.
8. Structural errors gate policy evaluation.
9. CLI prints policy diagnostics to stderr.
10. Diagnostic serialization includes new codes.

## Build Track

### B4.1 Extend Diagnostic Codes

Files:

```text
src/agentlint/diagnostics/models.py
tests/test_diagnostics.py
```

Add all Milestone 4 policy diagnostic codes.

### B4.2 Add Policy Evaluation Helpers

Files:

```text
src/agentlint/passes/policy.py
src/agentlint/passes/__init__.py
```

Implement:

1. Rule-to-diagnostic-code mapping.
2. Rule severity mapping.
3. Policy diagnostic construction.
4. Exception matching.
5. Unique event lookup helper.
6. Metadata source/sink normalization helper.
7. Data-flow reachability helper.

### B4.3 Add Tool Checks

Implement:

1. Unknown tool.
2. Denied tool.
3. Required argument.
4. Allowed argument type.
5. Allowed argument value.

### B4.4 Add Approval Checks

Implement:

1. Approval target extraction.
2. Approval mismatch diagnostics.
3. Required approval checks.
4. Approval-after-action checks.
5. Action-after-denial checks.

### B4.5 Add Data-Flow Checks

Implement:

1. Private-to-public sink.
2. Secret exposure.
3. Untrusted-to-privileged action.
4. Sensitive final answer.

### B4.6 Add Provenance Checks

Implement:

1. Unsupported claim.
2. Invalid provenance edge/reference.
3. Evidence-after-claim.

### B4.7 Wire CLI Policy Evaluation

Files:

```text
src/agentlint/cli.py
tests/test_cli.py
```

Change `validate --policy` from pre-validation to enforcement after structural validation succeeds.

### B4.8 Add Fixtures

Files:

```text
examples/traces/policy_*.json
examples/policies/policy_checks.yaml
examples/policies/policy_checks_warning_only.yaml
examples/policies/policy_checks_with_exception.yaml
```

Prefer reusing existing example policies where practical. Add narrow policies only when tests need specific severities or exceptions.

### B4.9 Update Documentation

Files:

```text
README.md
Documents/architecture.md
Documents/research_note.md
Documents/milestone_4_build_report.md
```

Update:

1. Status to Milestone 4 after build.
2. Current CLI behavior.
3. Policy enforcement boundary.
4. Metadata conventions for V1 data-flow checks.
5. Build report after verification.

## Verification Plan

Required commands:

```text
py -3.12 -m agentlint --help
py -3.12 -m agentlint policy validate examples\policies\customer_support.yaml
py -3.12 -m agentlint validate examples\traces\policy_tool_valid.json --policy examples\policies\customer_support.yaml
py -3.12 -m agentlint validate examples\traces\policy_unknown_tool.json --policy examples\policies\customer_support.yaml
py -3.12 -m agentlint validate examples\traces\policy_missing_approval.json --policy examples\policies\customer_support.yaml
py -3.12 -m agentlint validate examples\traces\policy_private_to_public_sink.json --policy examples\policies\customer_support.yaml
py -3.12 -m agentlint validate examples\traces\policy_unsupported_claim.json --policy examples\policies\research.yaml
py -3.12 -m pytest
py -3.12 -m ruff check .
py -3.12 -m ruff format --check .
git diff --check
```

Expected behavior:

1. Passing fixtures exit `0`.
2. Error fixtures exit `1`.
3. Warning-only fixtures exit `0`.
4. Each failure prints the expected diagnostic code.
5. Tests pass.
6. Ruff lint and format checks pass.
7. Whitespace check passes.

## Risks And Mitigations

### Risk: Data-Flow Checks Overpromise Precision

Mitigation:

Use explicit metadata and `data_flow` edges only. Document that Milestone 4 does not infer values from natural language or tool payloads.

### Risk: Policy Diagnostics Cascade From One Cause

Mitigation:

Apply staged checks: structural validation gates policy evaluation, unknown tools stop tool-specific checks, denied tools stop argument checks, and approval-after-action/action-after-denial suppress missing-approval for the same action.

### Risk: Provenance Checks Become Semantic

Mitigation:

Only check explicit evidence lists, provenance edges, and sequence ordering. Defer relevance and contradiction checks.

### Risk: CLI Validate Becomes A Report System Too Early

Mitigation:

Keep current diagnostic formatting and exit behavior. Defer summaries, JSON, `check`, `--format`, and `--fail-on` to Milestone 5.

### Risk: Exceptions Hide Too Much

Mitigation:

Use exact matching only. Ignore broad expression logic and do not implement wildcard matching in Milestone 4.

## Completion Checklist

- [x] Policy diagnostic codes exist.
- [x] Policy evaluation pass exists.
- [x] Rule severity mapping exists.
- [x] Policy exception suppression exists.
- [x] `UNKNOWN_TOOL` is implemented.
- [x] `UNAUTHORIZED_TOOL_CALL` is implemented.
- [x] `DISALLOWED_TOOL_ARGUMENT` is implemented.
- [x] `MISSING_APPROVAL` is implemented.
- [x] `APPROVAL_AFTER_ACTION` is implemented.
- [x] `ACTION_AFTER_DENIAL` is implemented.
- [x] `APPROVAL_MISMATCH` is implemented.
- [x] `PRIVATE_TO_PUBLIC_SINK` is implemented.
- [x] `SECRET_EXPOSURE` is implemented.
- [x] `UNTRUSTED_TO_PRIVILEGED_ACTION` is implemented.
- [x] `SENSITIVE_FINAL_ANSWER` is implemented.
- [x] `UNSUPPORTED_CLAIM` is implemented.
- [x] `INVALID_PROVENANCE_REFERENCE` is implemented.
- [x] `EVIDENCE_AFTER_CLAIM` is implemented.
- [x] Data-flow metadata conventions are represented in fixtures.
- [x] Passing fixtures exist for each check family.
- [x] Failing fixtures exist for every policy diagnostic code.
- [x] Tests cover severity `off`, `info`, `warning`, and `error` behavior where relevant.
- [x] Tests cover exception suppression.
- [x] CLI runs policy checks after structural validation.
- [x] README is updated.
- [x] Architecture note is updated.
- [x] Research note records Milestone 4 decisions.
- [x] Verification commands pass on Python 3.12.
- [x] Milestone 4 build report is written.
