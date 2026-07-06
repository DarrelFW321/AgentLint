# Milestone 5 Architecture Decisions

Decision date: 2026-07-01

Status: finalized for Milestone 5 implementation.

This document records the resolved D5 decisions for Milestone 5. It should be treated as the implementation baseline for reports and CI behavior.

## Current State Evaluation

The repository is at the Milestone 4 boundary:

1. Native AgentLint IR v1 traces load and schema-validate.
2. Structural validation emits deterministic diagnostics.
3. YAML Policy DSL V1 policies load and validate.
4. Policy evaluation emits tool, approval, data-flow, and provenance diagnostics.
5. `agentlint validate TRACE.json --policy POLICY.yaml` runs policy checks after structural validation succeeds.
6. Warning-only policy diagnostics exit `0` through `validate`.
7. `Diagnostic` already has code, severity, message, related events, related edges, policy reference, and remediation fields.
8. `src/agentlint/reports` exists only as a placeholder package.

Milestone 4 deliberately deferred:

1. `agentlint check`.
2. Human summary reports.
3. JSON reports.
4. CI threshold flags such as `--fail-on`.
5. Multiple trace checking.
6. Report redaction policy.
7. Diagnostic explanations.
8. SARIF and platform-specific annotations.

Milestone 5 should therefore add reporting and CI behavior without changing the semantics of structural or policy analysis.

## Research Basis

Local sources reviewed:

1. `Documents/requirements_specification.md`
2. `Documents/milestones.md`
3. `Documents/architecture.md`
4. `Documents/research_note.md`
5. `Documents/milestone_4_architecture_decisions.md`
6. `Documents/milestone_4_build_report.md`
7. `Documents/milestone_5_implementation_plan.md`
8. `src/agentlint/cli.py`
9. `src/agentlint/diagnostics/models.py`
10. `src/agentlint/diagnostics/formatting.py`
11. `src/agentlint/passes/policy.py`
12. `src/agentlint/reports/__init__.py`
13. `tests/test_cli.py`
14. `tests/test_diagnostics.py`

External references reviewed:

1. GitHub Actions exit codes: https://docs.github.com/en/actions/how-tos/create-and-publish-actions/set-exit-codes
2. GitHub Actions workflow commands and annotations: https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-commands
3. Typer enum choice options: https://typer.tiangolo.com/tutorial/parameter-types/enum/
4. Pydantic JSON serialization: https://docs.pydantic.dev/latest/concepts/serialization/
5. SARIF 2.1.0 specification: https://docs.oasis-open.org/sarif/sarif/v2.1.0/sarif-v2.1.0.html

Relevant research implications:

1. CI systems use process exit codes as the main pass/fail signal. AgentLint should make threshold-driven exit behavior explicit.
2. Platform annotations are useful but need file/line/source-location semantics. AgentLint should defer GitHub workflow commands and SARIF until source references are stronger.
3. Typer enum choices are a good fit for `--format` and `--fail-on` because invalid CLI values should be rejected before report generation.
4. Pydantic JSON serialization is a good fit for a stable versioned JSON report model.
5. Report redaction must be designed into the report model, not bolted onto terminal rendering only.

## Final Decision Summary

1. Milestone 5 implements reports and CI behavior, not new analysis rules.
2. `agentlint check` is the report and CI command.
3. `agentlint validate` remains compatible with Milestone 4 behavior.
4. A shared check execution layer produces per-trace results before rendering.
5. Reports use a versioned `agentlint.report.v1` schema.
6. `check --format text` emits a human report to stdout.
7. `check --format json` emits only JSON to stdout.
8. `check --fail-on error|warning|info|never` controls diagnostic threshold exits.
9. Invalid trace inputs are represented in check reports and always fail.
10. Policy load/schema errors remain command-level failures before report generation.
11. Reports omit raw trace payloads by default.
12. `agentlint explain CODE` explains current diagnostic codes.
13. Multiple trace support is explicit file paths only.
14. SARIF, GitHub annotations, HTML, PR annotations, directory traversal, and `--output` are deferred.

## ADR-001: Milestone 5 Scope Boundary

Decision:

Milestone 5 implements report contracts and CI behavior for existing checks.

In scope:

1. Shared check execution helper.
2. Per-trace check result model.
3. Versioned report model.
4. Human text report.
5. JSON report.
6. Severity summary counts.
7. `agentlint check`.
8. `--format text|json`.
9. `--fail-on error|warning|info|never`.
10. Explicit multi-file trace checking.
11. Metadata-only redaction boundary.
12. `agentlint explain CODE`.
13. Expected report fixtures and tests.

Out of scope:

1. New policy rules.
2. Directory traversal.
3. Glob expansion beyond what the invoking shell provides.
4. `--output` or report file writing.
5. SARIF.
6. GitHub Actions annotations.
7. HTML reports.
8. Pull request annotations.
9. Report uploads.
10. External trace adapters.
11. Runtime gating.
12. Full value graph modeling.
13. Semantic claim verification.

Reasoning:

Milestone 4 already established useful diagnostics. Milestone 5 should make those diagnostics useful in local development and CI before adding more analysis or platform integrations.

Consequences:

1. Reports are stdout-only in Milestone 5.
2. Any future SARIF or annotation emitter should consume the Milestone 5 report model.
3. Directory traversal remains Milestone 6 or later work.

## ADR-002: Command Boundary

Decision:

Add:

```text
agentlint check
```

Keep:

```text
agentlint validate
```

Reasoning:

`validate` currently answers whether one trace is structurally valid and, optionally, policy-clean under the Milestone 4 behavior. `check` should own reports, multiple trace files, output formats, and CI threshold behavior.

Consequences:

1. `validate` should not gain `--format`.
2. `validate` should not gain `--fail-on`.
3. `validate --policy` should keep the Milestone 4 stdout/stderr behavior.
4. `check` becomes the recommended CI command.

## ADR-003: Shared Check Execution Layer

Decision:

Add:

```text
src/agentlint/checking.py
```

Public APIs:

```python
def check_trace(trace: Trace, policy: Policy | None = None) -> TraceCheckResult:
    ...

def check_trace_file(path: Path, policy: Policy | None = None) -> TraceCheckResult:
    ...
```

Reasoning:

Analysis execution should not live inside report renderers. The CLI should orchestrate loading, checking, reporting, and exit behavior without duplicating analysis flow.

Consequences:

1. `check_trace` runs structural validation first.
2. Policy evaluation runs only if structural validation emits no error diagnostics.
3. `check_trace_file` converts trace file, JSON, and schema failures into input errors.
4. Policy loading remains outside `check_trace_file`.

## ADR-004: Per-Trace Result Model

Decision:

Represent every explicit trace path as one result.

Result fields:

```text
trace_path: str
trace_id: str | None
policy_id: str | None
status: passed | failed | invalid
events: int
edges: int
diagnostics: list[Diagnostic]
input_error: InputError | None
```

Input error fields:

```text
kind: file | json | schema
message: str
details: list[str]
```

Reasoning:

Multi-trace CI should report all bad trace files in one run instead of stopping at the first invalid file.

Consequences:

1. `status: passed` means no diagnostics and no input error.
2. `status: failed` means at least one diagnostic exists.
3. `status: invalid` means the trace could not be loaded or schema-validated.
4. Input error messages must not include raw trace payloads.

## ADR-005: Policy Error Boundary

Decision:

Policy load, YAML, and schema errors are command-level failures, not per-trace report entries.

Reasoning:

One policy applies to the whole `check` invocation. If it cannot load or validate, no trace can be checked meaningfully under that command.

Consequences:

1. Invalid policy errors print to stderr.
2. Invalid policy errors exit `1`.
3. `check --format json` does not print partial JSON when policy loading fails.

## ADR-006: Report Model

Decision:

Create a versioned Pydantic report schema under `agentlint.reports`.

Files:

```text
src/agentlint/reports/models.py
src/agentlint/reports/renderers.py
```

Top-level report fields:

```text
schema_version: agentlint.report.v1
agentlint_version: str
summary: ReportSummary
runs: list[TraceCheckResult]
redaction: RedactionInfo
```

Reasoning:

JSON reports need a stable machine-readable contract. Versioning the schema now reduces future migration ambiguity.

Consequences:

1. Use `REPORT_SCHEMA_VERSION = "agentlint.report.v1"`.
2. Use Pydantic `model_dump_json(indent=2)` for JSON rendering.
3. Do not include timestamps in Milestone 5 reports.
4. Preserve diagnostic ordering from the analysis passes.

## ADR-007: Summary Counts

Decision:

Every report includes summary counts.

Summary fields:

```text
trace_count: int
passed: int
failed: int
invalid: int
diagnostics: SeverityCounts
fail_on: error | warning | info | never
failed_threshold: bool
```

Severity counts:

```text
error: int
warning: int
info: int
```

Reasoning:

Humans and CI systems both need an immediate view of whether a run passed and why.

Consequences:

1. Invalid traces count in `invalid`, not in diagnostic severity counts.
2. Diagnostics from all trace results contribute to severity counts.
3. `failed_threshold` reflects diagnostic threshold failure, not invalid input failure.

## ADR-008: Text Report

Decision:

`check --format text` prints a human-readable report to stdout.

Text report sections:

1. Header.
2. Trace status summary.
3. Diagnostic severity summary.
4. Fail threshold.
5. Per-trace sections in command-line order.
6. Formatted diagnostics or input error details.

Reasoning:

Local development and CI logs should be readable without requiring a JSON parser.

Consequences:

1. Reuse existing `format_diagnostic` for individual diagnostics.
2. Do not duplicate diagnostics to stderr.
3. Command-level errors still print to stderr.

## ADR-009: JSON Report

Decision:

`check --format json` prints only JSON to stdout when report generation succeeds.

Reasoning:

Automated consumers need stdout to be parseable as JSON without stripping human text.

Consequences:

1. Tests must parse JSON stdout.
2. JSON rendering should be deterministic.
3. Expected JSON report fixtures should live under `examples/expected_reports/`.
4. Command-level policy errors may print to stderr and no JSON report is emitted.

## ADR-010: Fail Threshold

Decision:

Add:

```text
--fail-on error|warning|info|never
```

Default:

```text
error
```

Threshold semantics:

1. `error`: fail on any error diagnostic.
2. `warning`: fail on any warning or error diagnostic.
3. `info`: fail on any info, warning, or error diagnostic.
4. `never`: do not fail on diagnostics.
5. Any invalid trace input fails regardless of `--fail-on`.
6. Any policy load/schema error fails before report generation.

Reasoning:

This matches CI adoption needs: teams can start with warning-only or report-only behavior and later tighten thresholds.

Consequences:

1. Define a `FailOn` string enum.
2. Exit `1` when the threshold fails.
3. Exit `1` when any trace result is invalid.
4. Exit `0` when diagnostics do not meet the threshold and all traces loaded.

## ADR-011: CLI Choice Validation

Decision:

Use enum-backed Typer options for:

```text
--format text|json
--fail-on error|warning|info|never
```

Reasoning:

Invalid choice values should be rejected by the CLI parser with clear help text before any trace loading or report generation.

Consequences:

1. Define `ReportFormat` and `FailOn` as string enums.
2. Keep values lowercase.
3. Add CLI tests for invalid choices.

## ADR-012: Multiple Trace Inputs

Decision:

`agentlint check` accepts one or more explicit trace file paths.

Reasoning:

CI jobs often check several generated trace files. Explicit paths provide this capability without introducing directory traversal, recursive ignore rules, or platform-specific glob behavior.

Consequences:

1. Result order follows command-line path order.
2. Directory paths are invalid trace inputs in Milestone 5.
3. Directory traversal is deferred.
4. Shell-expanded globs are treated as ordinary explicit path arguments.

## ADR-013: Redaction Boundary

Decision:

Milestone 5 reports use metadata-only redaction by omission.

Reports may include:

1. Trace path.
2. Trace ID.
3. Policy ID.
4. Event and edge counts.
5. Diagnostic fields.
6. Sanitized input error messages.

Reports must not include:

1. User message content.
2. Developer instruction content.
3. Model inputs.
4. Model outputs.
5. Tool arguments.
6. Tool results.
7. Final answer content.
8. Policy metadata values.

Reasoning:

Current diagnostics already avoid raw trace payload values. The safest Milestone 5 redaction boundary is to keep raw values out of the report model entirely.

Consequences:

1. Add `RedactionInfo(mode="metadata_only", raw_values_included=False)`.
2. Do not add `--show-values`.
3. Do not add `--redaction none`.
4. Add tests that sensitive fixture strings are absent from text and JSON reports.

## ADR-014: Diagnostic Explain Command

Decision:

Add:

```text
agentlint explain CODE
```

Behavior:

1. Accept current diagnostic code values.
2. Normalize input to uppercase for convenience.
3. Print code, category, type, meaning, and usual remediation.
4. Exit `1` for unknown codes.

Reasoning:

Stable diagnostic codes are useful only if developers can quickly understand them from the CLI.

Consequences:

1. Add `src/agentlint/diagnostics/explanations.py`.
2. Cover all existing structural and policy diagnostic codes.
3. Keep explain output text-only in Milestone 5.

## ADR-015: Stdout And Stderr Contract

Decision:

Use stdout for successful report output and stderr for command-level errors.

Rules:

1. `check --format text` writes the text report to stdout.
2. `check --format json` writes only JSON to stdout.
3. Policy load/schema errors write to stderr.
4. Typer argument errors write to stderr.
5. Per-trace invalid input errors are represented in reports, not duplicated to stderr.

Reasoning:

This keeps JSON output machine-readable and keeps command failures visible in CI logs.

Consequences:

1. CLI tests should assert stdout/stderr separately.
2. JSON tests should parse stdout directly.

## ADR-016: Validate Compatibility

Decision:

Keep `agentlint validate` compatible with Milestone 4.

Reasoning:

Milestone 5 should add a richer command rather than break existing validation behavior.

Consequences:

1. Existing validate tests should continue passing.
2. `validate --policy` still exits `1` on error diagnostics.
3. `validate --policy` still exits `0` on warning-only diagnostics.
4. Internal refactoring is allowed only if user-visible behavior is preserved.

## ADR-017: Deferred Report Formats

Decision:

Defer SARIF, GitHub Actions workflow commands, HTML, pull request annotations, and report file output.

Reasoning:

SARIF and platform annotations require stronger file, line, column, and source-reference semantics. Report file output introduces overwrite and path-handling choices that are unnecessary for the first report milestone.

Consequences:

1. No SARIF emitter in Milestone 5.
2. No GitHub annotation emitter in Milestone 5.
3. No `--output` flag in Milestone 5.
4. Future emitters should consume `AgentLintReport`.

## ADR-018: Fixture Strategy

Decision:

Add focused report fixtures under:

```text
examples/expected_reports/
```

Required fixtures:

1. One passing text report or text-report assertion.
2. One failing JSON report.
3. One multi-trace report.
4. One invalid-trace report.

Reasoning:

Milestone 6 will broaden fixture corpus discipline. Milestone 5 needs enough report fixtures to stabilize the report contract without overcommitting to large golden snapshots.

Consequences:

1. JSON fixtures should be exact where practical.
2. Text reports can be asserted by key lines to avoid brittle whitespace tests.
3. Report fixture values must avoid raw sensitive payloads.

## ADR-019: Test Strategy

Decision:

Add focused tests for checking, reports, CLI thresholds, redaction, and explanations.

Files:

```text
tests/test_checking.py
tests/test_reports.py
tests/test_cli.py
tests/test_diagnostics.py
```

Required coverage:

1. Shared check execution with and without policy.
2. Structural gating of policy checks.
3. Per-trace invalid input results.
4. Summary counts.
5. All `--fail-on` thresholds.
6. Text report rendering.
7. JSON report rendering.
8. Multi-trace ordering.
9. Redaction regressions.
10. `explain` success and failure.
11. `validate` compatibility.

Reasoning:

M5 introduces public output contracts. Tests should guard behavior that downstream automation may depend on.

## Implementation Checklist Impact

The Milestone 5 implementation plan should align to these decisions:

1. Keep `check` as the only report and CI command.
2. Keep `validate` compatible with Milestone 4.
3. Add a shared check execution layer.
4. Add a versioned `agentlint.report.v1` schema.
5. Emit stdout-only reports.
6. Do not add `--output`.
7. Do not add SARIF or GitHub annotations.
8. Treat trace input errors as report entries.
9. Treat policy load/schema errors as command-level failures.
10. Omit raw trace payloads from report models.
11. Add `explain` for all current diagnostic codes.
