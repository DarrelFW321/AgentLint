# Milestone 4 Build Report

Build date: 2026-07-01

Status: complete.

## Scope

Milestone 4 implemented core offline policy enforcement over structurally valid native AgentLint IR traces.

Implemented:

1. Policy diagnostic codes.
2. Policy evaluation pass.
3. Rule severity mapping.
4. Exact-match policy exception suppression.
5. Tool policy checks.
6. Approval checks.
7. Explicit metadata and `data_flow` data-handling checks.
8. Final-answer provenance checks.
9. `agentlint validate TRACE.json --policy POLICY.yaml` enforcement.
10. Policy check fixtures and tests.
11. README, architecture note, research note, and implementation-plan updates.

Deferred:

1. `agentlint check`.
2. JSON reports.
3. `--format`.
4. `--fail-on`.
5. Directory or multiple-trace traversal.
6. Report redaction.
7. Full value graph modeling.
8. Natural-language data-flow inference.
9. Model-assisted claim verification.
10. Semantic contradiction detection.
11. External trace adapters.
12. Runtime gating.

## Implementation Summary

New module:

1. `src/agentlint/passes/policy.py`

Updated modules:

1. `src/agentlint/diagnostics/models.py`
2. `src/agentlint/passes/__init__.py`
3. `src/agentlint/cli.py`

New test file:

1. `tests/test_policy_pass.py`

Updated tests:

1. `tests/test_cli.py`
2. `tests/test_diagnostics.py`
3. `tests/test_policy_loader.py`

New policy fixtures:

1. `examples/policies/policy_checks.yaml`
2. `examples/policies/policy_checks_warning_only.yaml`
3. `examples/policies/policy_checks_with_exception.yaml`

New trace fixtures:

1. `examples/traces/policy_tool_valid.json`
2. `examples/traces/policy_approval_valid.json`
3. `examples/traces/policy_data_flow_valid.json`
4. `examples/traces/policy_provenance_valid.json`
5. `examples/traces/policy_unknown_tool.json`
6. `examples/traces/policy_unauthorized_tool_call.json`
7. `examples/traces/policy_disallowed_tool_argument.json`
8. `examples/traces/policy_missing_approval.json`
9. `examples/traces/policy_approval_after_action.json`
10. `examples/traces/policy_action_after_denial.json`
11. `examples/traces/policy_approval_mismatch.json`
12. `examples/traces/policy_private_to_public_sink.json`
13. `examples/traces/policy_secret_exposure.json`
14. `examples/traces/policy_untrusted_to_privileged_action.json`
15. `examples/traces/policy_sensitive_final_answer.json`
16. `examples/traces/policy_unsupported_claim.json`
17. `examples/traces/policy_invalid_provenance_reference.json`
18. `examples/traces/policy_evidence_after_claim.json`

Key behavior:

1. `evaluate_policy(trace, policy)` returns deterministic policy diagnostics.
2. Structural validation gates policy evaluation in the CLI.
3. Rule severity `off` suppresses diagnostics before exception matching.
4. Rule severities `info`, `warning`, and `error` map to diagnostic severities.
5. `validate --policy` exits `1` for policy error diagnostics.
6. `validate --policy` exits `0` for warning-only or info-only diagnostics.
7. Policy diagnostics include `policy_reference`.
8. Unknown source/sink metadata labels are ignored.
9. Extra tool arguments are allowed unless a configured argument policy constrains them.

## Verification

Commands run on Python 3.12.10:

```text
py -3.12 -m agentlint --help
```

Result: passed. Help lists `validate` and `policy`.

```text
py -3.12 -m agentlint policy validate examples\policies\customer_support.yaml
```

Result: passed.

```text
valid policy: customer_support_v1
version: 1
tools: 5
sources: 3
sinks: 3
rules: 14
exceptions: 1
```

```text
py -3.12 -m agentlint validate examples\traces\policy_tool_valid.json --policy examples\policies\policy_checks.yaml
```

Result: passed.

```text
valid policy: policy_checks_v1
valid trace: trace_policy_tool_valid
events: 1
edges: 0
diagnostics: 0
```

```text
py -3.12 -m agentlint validate examples\traces\policy_unknown_tool.json --policy examples\policies\policy_checks.yaml
```

Result: passed as an expected failure path, exited `1`.

```text
error[UNKNOWN_TOOL]: tool call "evt_unknown_tool" uses unknown tool "unknown_tool"
  related events: evt_unknown_tool
  policy reference: policy_checks_v1:unknown_tool
```

```text
py -3.12 -m agentlint validate examples\traces\policy_missing_approval.json --policy examples\policies\policy_checks.yaml
```

Result: passed as an expected failure path, exited `1`.

```text
error[MISSING_APPROVAL]: tool call "evt_send_email" requires prior approval for tool "send_email"
  related events: evt_send_email
  policy reference: policy_checks_v1:missing_approval
```

```text
py -3.12 -m agentlint validate examples\traces\policy_private_to_public_sink.json --policy examples\policies\policy_checks.yaml
```

Result: passed as an expected failure path, exited `1`.

```text
error[PRIVATE_TO_PUBLIC_SINK]: private source "customer_profile" reaches public sink "web_search.query" at event "evt_web_search"
  related events: evt_customer_profile, evt_web_search
  policy reference: policy_checks_v1:private_to_public_sink
```

```text
py -3.12 -m agentlint validate examples\traces\policy_sensitive_final_answer.json --policy examples\policies\policy_checks.yaml
```

Result: passed with a warning-only diagnostic, exited `0`.

```text
warning[SENSITIVE_FINAL_ANSWER]: sensitive source "customer_profile" reaches final answer "evt_final"
  related events: evt_customer_profile, evt_final
  policy reference: policy_checks_v1:sensitive_final_answer
```

```text
py -3.12 -m agentlint validate examples\traces\policy_unsupported_claim.json --policy examples\policies\research.yaml
```

Result: passed as an expected failure path, exited `1`.

```text
error[UNSUPPORTED_CLAIM]: claim "claim_status" in final answer "evt_final" has no evidence
  related events: evt_final
  policy reference: research_v1:unsupported_claim
```

```text
py -3.12 -m agentlint validate examples\traces\policy_evidence_after_claim.json --policy examples\policies\policy_checks_warning_only.yaml
```

Result: passed with a warning-only diagnostic, exited `0`.

```text
warning[EVIDENCE_AFTER_CLAIM]: claim "claim_status" uses evidence "evt_evidence" that occurs after final answer "evt_final"
  related events: evt_final, evt_evidence
  policy reference: policy_checks_warning_only_v1:evidence_after_claim
```

```text
py -3.12 -m pytest
```

Result: passed, `121 passed`.

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

The `policy_unsupported_claim.json` fixture exits `0` under `policy_checks.yaml` because that policy configures `unsupported_claim` as a warning. The same fixture exits `1` under `research.yaml`, which configures the rule as an error.
