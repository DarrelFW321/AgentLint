# Milestone 5 Build Report

Build date: 2026-07-01

Status: complete.

## Scope

Milestone 5 implemented reports and CI behavior over the existing native trace, structural validation, and policy evaluation pipeline.

Implemented:

1. Shared check execution helper.
2. Per-trace check results.
3. Versioned report model.
4. Text report renderer.
5. JSON report renderer.
6. Severity summary counts.
7. Threshold-based CI exit behavior.
8. `agentlint check`.
9. `--format text|json`.
10. `--fail-on error|warning|info|never`.
11. Explicit multi-trace checking.
12. Invalid trace input reporting.
13. Metadata-only report redaction.
14. `agentlint explain CODE`.
15. Expected JSON report fixture.
16. README, architecture note, research note, and implementation-plan updates.

Deferred:

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
11. Semantic provenance checking.

## Implementation Summary

New modules:

1. `src/agentlint/checking.py`
2. `src/agentlint/reports/models.py`
3. `src/agentlint/reports/renderers.py`
4. `src/agentlint/diagnostics/explanations.py`

Updated modules:

1. `src/agentlint/cli.py`
2. `src/agentlint/reports/__init__.py`
3. `src/agentlint/diagnostics/__init__.py`

New tests:

1. `tests/test_checking.py`
2. `tests/test_reports.py`

Updated tests:

1. `tests/test_cli.py`
2. `tests/test_diagnostics.py`

New fixture:

1. `examples/expected_reports/policy_unknown_tool.json`

Key behavior:

1. `check_trace_file(path, policy)` returns a structured result for pass, fail, or invalid trace input.
2. Structural errors still gate policy evaluation.
3. Policy load/schema errors remain command-level failures.
4. `agentlint check` emits a report to stdout.
5. JSON report output is parseable directly from stdout.
6. Invalid trace inputs are included in reports and always exit `1`.
7. Diagnostic thresholds control exit behavior for valid traces.
8. Reports omit raw trace payload values by default.
9. `agentlint explain CODE` covers every current diagnostic code.
10. `agentlint validate` remains compatible with Milestone 4 behavior.

## Verification

Commands run on Python 3.12.10:

```text
py -3.12 -m agentlint --help
```

Result: passed. Help lists `check` and `explain`.

```text
py -3.12 -m agentlint check examples\traces\policy_tool_valid.json --policy examples\policies\policy_checks.yaml
```

Result: passed, exited `0`.

```text
AgentLint Report
traces: 1 passed, 0 failed, 0 invalid
diagnostics: 0 error, 0 warning, 0 info
fail-on: error
redaction: metadata_only, raw values included: false
```

```text
py -3.12 -m agentlint check examples\traces\policy_unknown_tool.json --policy examples\policies\policy_checks.yaml
```

Result: passed as an expected failure path, exited `1`.

```text
error[UNKNOWN_TOOL]: tool call "evt_unknown_tool" uses unknown tool "unknown_tool"
  related events: evt_unknown_tool
  policy reference: policy_checks_v1:unknown_tool
```

```text
py -3.12 -m agentlint check examples\traces\policy_unknown_tool.json --policy examples\policies\policy_checks.yaml --format json
```

Result: passed as an expected failure path, exited `1`. Stdout parsed as JSON in tests and included `schema_version: agentlint.report.v1`.

```text
py -3.12 -m agentlint check examples\traces\policy_sensitive_final_answer.json --policy examples\policies\policy_checks.yaml --fail-on warning
```

Result: passed as an expected failure path, exited `1`.

```text
py -3.12 -m agentlint check examples\traces\policy_sensitive_final_answer.json --policy examples\policies\policy_checks.yaml --fail-on error
```

Result: passed, exited `0` with a warning-only report.

```text
py -3.12 -m agentlint check examples\traces\policy_unknown_tool.json examples\traces\policy_missing_approval.json --policy examples\policies\policy_checks.yaml
```

Result: passed as an expected failure path, exited `1`. Report preserved command-line trace order.

```text
py -3.12 -m agentlint explain UNKNOWN_TOOL
```

Result: passed.

```text
code: UNKNOWN_TOOL
category: policy
type: tool policy
meaning: A tool call uses a tool that is not declared in the active policy.
remediation: Add the tool to the policy or remove the tool call.
```

```text
py -3.12 -m agentlint validate examples\traces\structural_valid_tool_flow.json --policy examples\policies\customer_support.yaml
```

Result: passed. Existing validate behavior is compatible.

```text
py -3.12 -m pytest
```

Result: passed, `154 passed`.

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

Report status and exit status are intentionally separate:

1. A trace with warning-only diagnostics has `status: failed` because diagnostics exist.
2. A warning-only run exits `0` with `--fail-on error`.
3. The same warning-only run exits `1` with `--fail-on warning`.

Reports are stdout-only in Milestone 5. File output, SARIF, and CI platform annotations are deferred.
