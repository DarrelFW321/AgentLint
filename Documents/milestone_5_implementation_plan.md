# Milestone 5 Implementation Plan

Status: finalized for implementation.

Milestone 5 turns the existing validation and policy checks into a usable local-development and CI reporting surface. Milestone 4 proved that AgentLint can emit meaningful diagnostics over native traces; Milestone 5 should make those diagnostics consumable by humans and automation without changing the core checks.

## Objective

Implement reports and CI behavior for native trace checking.

Milestone 5 is complete when:

1. `agentlint check` can evaluate one or more explicit trace files.
2. `agentlint check` can run structural checks with or without a policy.
3. `agentlint check --policy POLICY.yaml` runs structural checks first, then policy checks when structural checks have no error diagnostics.
4. `agentlint check --format text` emits a readable terminal report with a summary and diagnostics.
5. `agentlint check --format json` emits a stable JSON report.
6. `agentlint check --fail-on` controls the process exit threshold.
7. Reports avoid raw private or secret trace values by default.
8. `agentlint explain CODE` explains supported diagnostic codes.
9. `agentlint validate` remains a validation-oriented compatibility path.
10. Tests cover report models, renderers, CLI behavior, exit thresholds, redaction boundaries, and explain output.

## Current Baseline

Milestone 4 implemented:

1. Native trace loading and schema validation.
2. Structural validation diagnostics.
3. YAML policy loading and validation.
4. Offline policy evaluation.
5. `agentlint validate TRACE.json --policy POLICY.yaml` policy enforcement.
6. Human formatting for individual diagnostics.
7. B4 fixtures for all policy diagnostic codes.

Current gaps:

1. `src/agentlint/reports` is only a placeholder package.
2. There is no report schema.
3. There is no JSON report.
4. There is no `agentlint check` command.
5. There is no `--format` option.
6. There is no `--fail-on` threshold.
7. There is no multi-trace command path.
8. There is no explicit redaction contract for reports.
9. There is no `agentlint explain` command.

## Finalized Scope

Milestone 5 should implement:

1. Shared trace-check execution helper.
2. Report data models under `agentlint.reports`.
3. Text report renderer.
4. JSON report renderer.
5. Summary counts by severity.
6. `agentlint check`.
7. `--format text|json`.
8. `--fail-on error|warning|info|never`.
9. Explicit multi-trace checking for file paths listed on the command line.
10. Default report redaction by omission of raw trace payloads.
11. `agentlint explain CODE`.
12. Focused expected-report fixtures.
13. README and architecture updates.
14. Milestone 5 build report after implementation.

Milestone 5 should not implement:

1. Directory traversal or glob expansion.
2. SARIF.
3. GitHub Actions workflow command annotations.
4. HTML reports.
5. Pull request annotations.
6. Report uploads.
7. Runtime gating.
8. External trace adapters.
9. Full value graph modeling.
10. Semantic claim verification.
11. Raw trace excerpts in reports.
12. `--output` or report file writing.

## Reevaluated Decisions

### D5.1 Report Command Boundary

Decision:

Add `agentlint check` as the report and CI command. Keep `agentlint validate` as a validation-oriented command.

Reasoning:

`validate` currently has stable behavior and is useful for schema/structural checks. CI needs a richer command surface with multiple trace files, report formats, and configurable exit thresholds. Adding those options to `validate` would blur validation and policy-reporting concerns.

Implementation consequence:

1. `validate` may internally reuse the same execution helper.
2. `validate` should not gain `--format` or `--fail-on` in Milestone 5.
3. `check` owns report rendering and threshold behavior.

### D5.2 Shared Check Execution Layer

Decision:

Add a small execution layer that returns structured check results before rendering.

Proposed file:

```text
src/agentlint/checking.py
```

Proposed API:

```python
def check_trace(trace: Trace, policy: Policy | None = None) -> TraceCheckResult:
    ...
```

For CLI file handling:

```python
def check_trace_file(path: Path, policy: Policy | None = None) -> TraceCheckResult:
    ...
```

Reasoning:

Report renderers should not know how to load traces, run structural validation, gate policy evaluation, or count diagnostics. The CLI should not duplicate the same check flow in `validate` and `check`.

Implementation consequence:

1. Structural validation still gates policy evaluation.
2. Trace schema/load errors are represented as input errors in `check` reports.
3. Policy load errors remain command-level input errors because a bad policy applies to the whole run.

### D5.3 Trace Check Result Model

Decision:

Represent each checked file as a structured result.

Proposed model fields:

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

Reasoning:

Multiple trace checks need per-trace status. Invalid input files should appear in JSON/text reports rather than aborting the first time one trace fails to load.

Implementation consequence:

1. `status: invalid` is reserved for trace file, JSON, or schema loading failures.
2. Invalid trace input errors always cause `check` to exit `1`.
3. Policy file, YAML, and schema errors still print to stderr and exit `1` before report generation.

### D5.4 Report Model

Decision:

Create a versioned report schema.

Proposed files:

```text
src/agentlint/reports/models.py
src/agentlint/reports/renderers.py
```

Report shape:

```text
schema_version: agentlint.report.v1
agentlint_version: str
summary: ReportSummary
runs: list[TraceCheckResult]
redaction: RedactionInfo
```

Summary shape:

```text
trace_count: int
passed: int
failed: int
invalid: int
diagnostics: SeverityCounts
fail_on: error | warning | info | never
failed_threshold: bool
```

Reasoning:

JSON reports need a stable top-level contract. A versioned schema lets later milestones add fields without making current automation guess at compatibility.

Implementation consequence:

1. Use Pydantic models for report serialization.
2. Use `model_dump_json(indent=2)` for stable JSON output.
3. Do not include volatile timestamps in Milestone 5 reports.
4. Preserve diagnostic order as emitted by structural and policy passes.

### D5.5 Human Text Report

Decision:

`--format text` should print a concise terminal report to stdout.

Proposed text structure:

```text
AgentLint Report
traces: 2 passed, 1 failed, 0 invalid
diagnostics: 2 error, 1 warning, 0 info
fail-on: error

trace: examples/traces/policy_unknown_tool.json
trace id: trace_policy_unknown_tool
status: failed
events: 1
edges: 0

error[UNKNOWN_TOOL]: ...
  related events: evt_unknown_tool
  policy reference: policy_checks_v1:unknown_tool
  remediation: ...
```

Reasoning:

Human reports should be readable in local terminals and CI logs without requiring a JSON parser.

Implementation consequence:

1. Report output goes to stdout.
2. Command-level input errors go to stderr.
3. Diagnostics in `check` reports should not be duplicated to stderr.

### D5.6 JSON Report

Decision:

`--format json` prints only JSON to stdout when report generation succeeds.

Reasoning:

Automated consumers need stdout to contain parseable JSON. Diagnostics, summaries, and run details belong in the JSON body. Command-level policy errors can still use stderr because no valid report exists.

Implementation consequence:

1. `check --format json` must not print Typer progress or human text to stdout.
2. Tests should parse stdout as JSON.
3. JSON report fixtures should live under `examples/expected_reports/`.

### D5.7 Fail Threshold

Decision:

Add `--fail-on` with these values:

```text
error
warning
info
never
```

Default:

```text
error
```

Semantics:

1. `error`: fail if any error diagnostic is present.
2. `warning`: fail if any warning or error diagnostic is present.
3. `info`: fail if any info, warning, or error diagnostic is present.
4. `never`: do not fail on diagnostics.
5. Invalid trace input errors always fail.
6. Policy load/schema errors always fail.

Reasoning:

This supports gradual adoption while preserving hard failure for malformed inputs. `never` is useful for report-only CI jobs.

Implementation consequence:

1. Define a `FailOn` enum for CLI and report models.
2. Use Typer enum choices for validation.
3. Add tests for all four thresholds.

### D5.8 Redaction Boundary

Decision:

Milestone 5 reports should avoid raw trace payloads by default by excluding event content, tool arguments, tool results, model inputs/outputs, and policy metadata from report models.

Report records may include:

1. Trace path.
2. Trace ID.
3. Policy ID.
4. Event and edge counts.
5. Diagnostic codes, severities, messages, related event IDs, related edge IDs, policy references, and remediations.
6. Input error categories and sanitized validation messages.

Report records must not include:

1. User message content.
2. Developer instruction content.
3. Model inputs or outputs.
4. Tool arguments.
5. Tool results.
6. Final-answer content.
7. Policy metadata values.

Reasoning:

Current diagnostics already avoid raw trace values. Keeping reports metadata-only is the smallest reliable redaction implementation and matches AgentLint's security requirement to avoid leaking private or secret values by default.

Implementation consequence:

1. Add `RedactionInfo(mode="metadata_only", raw_values_included=False)` to reports.
2. Do not add `--show-values` or `--redaction none` in Milestone 5.
3. Add regression tests proving obvious sensitive fixture strings do not appear in text or JSON reports.

### D5.9 Explain Command

Decision:

Add:

```text
agentlint explain CODE
```

The command should explain a diagnostic code, including:

1. Code.
2. Category.
3. Meaning.
4. Usual remediation.
5. Whether the code is structural or policy-related.

Reasoning:

M5 introduces reports for humans and CI. Developers need a way to understand stable diagnostic codes without opening source code.

Implementation consequence:

1. Add a diagnostic explanation registry under `agentlint.diagnostics`.
2. Support all current structural and policy diagnostic codes.
3. Unknown codes should exit `1` with a clear stderr message.
4. JSON explain output is deferred unless needed during implementation.

### D5.10 CLI Format Choices

Decision:

Use enum-backed Typer options for `--format` and `--fail-on`.

Reasoning:

The current CLI already uses Typer. Enum-backed options make help text show valid choices and reject invalid values before command logic runs.

Implementation consequence:

1. Define `ReportFormat` and `FailOn` as string enums.
2. Keep option values lowercase.
3. Tests should cover invalid `--format` and invalid `--fail-on` behavior through Typer.

### D5.11 Multiple Trace Inputs

Decision:

`agentlint check` accepts one or more explicit trace file paths.

Example:

```text
agentlint check examples/traces/a.json examples/traces/b.json --policy examples/policies/customer_support.yaml
```

Reasoning:

CI often checks a set of generated traces. Supporting explicit multiple paths is enough for Milestone 5 and avoids platform-specific path globbing or recursive traversal semantics.

Implementation consequence:

1. Directory traversal is deferred.
2. Shell glob expansion, when available, is treated as ordinary expanded file arguments.
3. Report order follows command-line path order.

### D5.12 Validate Compatibility

Decision:

Keep `agentlint validate` behavior compatible with Milestone 4.

Reasoning:

Existing tests and users can continue to rely on `validate` for direct trace validation. `check` becomes the richer report/CI path.

Implementation consequence:

1. Existing validate tests should continue passing.
2. `validate --policy` can reuse `check_trace` internally but should keep its current stdout/stderr shape.
3. `validate` still exits `1` on error diagnostics and `0` on warning-only policy diagnostics.

### D5.13 Deferred Report Formats

Decision:

Defer SARIF, GitHub Actions workflow annotations, HTML, and PR annotations.

Reasoning:

M5 should first stabilize AgentLint's own report schema and command behavior. SARIF and platform annotations require location mapping and source-reference semantics that are not mature yet.

Implementation consequence:

1. No SARIF schema or emitter in Milestone 5.
2. No GitHub workflow-command emitter in Milestone 5.
3. Future SARIF work should consume the M5 report model rather than rerunning checks.

## Build Track

### B5.1 Add Check Result Models

Files:

```text
src/agentlint/checking.py
tests/test_checking.py
```

Implement:

1. `TraceCheckStatus`.
2. `InputErrorKind`.
3. `InputError`.
4. `TraceCheckResult`.
5. `check_trace`.
6. `check_trace_file`.

### B5.2 Add Report Models

Files:

```text
src/agentlint/reports/models.py
src/agentlint/reports/__init__.py
tests/test_reports.py
```

Implement:

1. `REPORT_SCHEMA_VERSION = "agentlint.report.v1"`.
2. `FailOn`.
3. `ReportFormat`.
4. `SeverityCounts`.
5. `ReportSummary`.
6. `RedactionInfo`.
7. `AgentLintReport`.

### B5.3 Add Threshold Logic

Files:

```text
src/agentlint/reports/models.py
tests/test_reports.py
```

Implement:

1. Severity counting.
2. Threshold evaluation for `error`, `warning`, `info`, and `never`.
3. Invalid input always failing.
4. Report summary construction from trace results.

### B5.4 Add Text Renderer

Files:

```text
src/agentlint/reports/renderers.py
tests/test_reports.py
```

Implement:

1. `render_text_report(report: AgentLintReport) -> str`.
2. Summary section.
3. Per-trace sections.
4. Reuse existing `format_diagnostic`.
5. Input error formatting.

### B5.5 Add JSON Renderer

Files:

```text
src/agentlint/reports/renderers.py
tests/test_reports.py
examples/expected_reports/
```

Implement:

1. `render_json_report(report: AgentLintReport) -> str`.
2. Stable enum serialization.
3. JSON parsing tests.
4. At least one expected JSON report fixture.

### B5.6 Add `agentlint check`

Files:

```text
src/agentlint/cli.py
tests/test_cli.py
```

Implement:

1. One-or-more trace path argument.
2. Optional `--policy POLICY.yaml`.
3. `--format text|json`, default `text`.
4. `--fail-on error|warning|info|never`, default `error`.
5. Stdout-only report output.
6. Exit code behavior from report summary.

Decision:

Use stdout-only reports in Milestone 5. This avoids file-overwrite and path-handling questions in the first report milestone.

### B5.7 Add `agentlint explain`

Files:

```text
src/agentlint/diagnostics/explanations.py
src/agentlint/diagnostics/__init__.py
src/agentlint/cli.py
tests/test_diagnostics.py
tests/test_cli.py
```

Implement:

1. Explanation records for every current diagnostic code.
2. Text output for one code.
3. Clear failure for unknown code.

### B5.8 Update Validate To Share Execution Carefully

Files:

```text
src/agentlint/cli.py
tests/test_cli.py
```

Implementation options:

1. Keep existing `validate` code unchanged if reuse would add churn.
2. Or use `check_trace` internally while preserving existing stdout/stderr and exit behavior.

Decision:

Prefer minimal churn. Only refactor `validate` if it removes duplication without changing behavior.

### B5.9 Add Redaction Regression Tests

Files:

```text
tests/test_reports.py
```

Test that text and JSON reports do not include:

1. User message content from fixtures.
2. Tool argument values.
3. Tool result values.
4. Final-answer content.

### B5.10 Update Documentation

Files:

```text
README.md
Documents/architecture.md
Documents/research_note.md
Documents/milestone_5_build_report.md
```

Update:

1. Current status to Milestone 5 after build.
2. `agentlint check` examples.
3. JSON report contract.
4. `--fail-on` behavior.
5. Redaction boundary.
6. Build report after verification.

## Verification Plan

Required commands:

```text
py -3.12 -m agentlint --help
py -3.12 -m agentlint check examples\traces\policy_tool_valid.json --policy examples\policies\policy_checks.yaml
py -3.12 -m agentlint check examples\traces\policy_unknown_tool.json --policy examples\policies\policy_checks.yaml
py -3.12 -m agentlint check examples\traces\policy_unknown_tool.json --policy examples\policies\policy_checks.yaml --format json
py -3.12 -m agentlint check examples\traces\policy_sensitive_final_answer.json --policy examples\policies\policy_checks.yaml --fail-on warning
py -3.12 -m agentlint check examples\traces\policy_sensitive_final_answer.json --policy examples\policies\policy_checks.yaml --fail-on error
py -3.12 -m agentlint check examples\traces\policy_unknown_tool.json examples\traces\policy_missing_approval.json --policy examples\policies\policy_checks.yaml
py -3.12 -m agentlint explain UNKNOWN_TOOL
py -3.12 -m agentlint validate examples\traces\structural_valid_tool_flow.json --policy examples\policies\customer_support.yaml
py -3.12 -m pytest
py -3.12 -m ruff check .
py -3.12 -m ruff format --check .
git diff --check
```

Expected behavior:

1. Passing check reports exit `0`.
2. Error diagnostics exit `1` with default `--fail-on error`.
3. Warning-only diagnostics exit `0` with `--fail-on error`.
4. Warning-only diagnostics exit `1` with `--fail-on warning`.
5. `--fail-on never` exits `0` for diagnostics but not for invalid input files.
6. JSON report stdout parses as JSON.
7. Text and JSON reports omit raw trace payload values.
8. Multiple trace reports preserve command-line order.
9. `validate` remains compatible with M4 behavior.
10. Tests, Ruff, format check, and whitespace check pass.

## Risks And Mitigations

### Risk: Report Schema Churn

Mitigation:

Version the report schema as `agentlint.report.v1`, keep fields minimal, and defer SARIF/platform annotations until event source locations are stronger.

### Risk: Reports Leak Sensitive Trace Data

Mitigation:

Do not include raw trace payloads in report models. Add explicit redaction metadata and regression tests that scan rendered output for fixture-sensitive strings.

### Risk: CLI Responsibilities Become Duplicated

Mitigation:

Use a shared check execution helper. Keep rendering in `agentlint.reports` and keep policy/structural analysis in `agentlint.passes`.

### Risk: Multi-Trace Error Handling Gets Ambiguous

Mitigation:

Represent per-trace input errors in `check` reports and treat policy loading errors as command-level failures before report generation.

### Risk: `validate` Behavior Regresses

Mitigation:

Keep validate tests unchanged and add explicit compatibility checks after introducing `check`.

## Completion Checklist

- [x] Shared check execution helper exists.
- [x] Per-trace check result model exists.
- [x] Versioned report model exists.
- [x] Severity summary counts exist.
- [x] Threshold evaluation exists.
- [x] Text report renderer exists.
- [x] JSON report renderer exists.
- [x] `agentlint check` exists.
- [x] `--format text|json` works.
- [x] `--fail-on error|warning|info|never` works.
- [x] Reports are stdout-only.
- [x] Explicit multi-trace check works.
- [x] Invalid trace input appears in check reports.
- [x] Policy load errors remain command-level failures.
- [x] Reports omit raw trace payloads by default.
- [x] Redaction metadata appears in reports.
- [x] `agentlint explain CODE` exists.
- [x] Explanations exist for every current diagnostic code.
- [x] Existing `validate` behavior remains compatible.
- [x] Expected report fixtures exist.
- [x] CLI tests cover check/report/fail-on behavior.
- [x] Report tests cover text and JSON renderers.
- [x] README is updated.
- [x] Architecture note is updated.
- [x] Research note records Milestone 5 decisions after build.
- [x] Verification commands pass on Python 3.12.
- [x] Milestone 5 build report is written.
