# Milestone 6 Implementation Plan

Status: finalized for implementation.

Milestone 6 turns the current examples and report behavior into a disciplined fixture corpus. Milestones 1 through 5 already created native traces, structural diagnostics, policy diagnostics, reports, and CLI behavior. This milestone should make those behaviors hard to regress and easy to extend.

## Objective

Build the evidence base for engineering confidence and later research evaluation.

Milestone 6 is complete when:

1. A curated fixture manifest identifies the supported trace cases, categories, policy inputs, expected status, and expected diagnostic codes.
2. Every current `DiagnosticCode` has at least one stable fixture.
3. Representative JSON reports have checked-in golden files.
4. Text reports have stable key-line assertions without making terminal formatting brittle.
5. Parametrized pytest coverage runs over the fixture manifest.
6. Redaction behavior is tested across sensitive fixtures and report formats.
7. Report output is deterministic across repeated runs.
8. A lightweight performance smoke test checks multiple traces together.
9. The contributor workflow makes it clear that new checks require new fixtures.

## Current Baseline

The repository already has the main ingredients for Milestone 6:

1. `examples/traces/` contains passing traces, malformed traces, structural violation traces, and policy violation traces.
2. `examples/policies/` contains customer-support, research, coding, valid policy-check, warning-only, exception, and invalid policy examples.
3. `examples/expected_reports/` exists, but currently contains only one JSON expected report.
4. `tests/test_structural_pass.py` and `tests/test_policy_pass.py` already cover many violation fixtures directly.
5. `tests/test_reports.py`, `tests/test_checking.py`, and `tests/test_cli.py` cover report and command behavior.
6. `DiagnosticCode` is the authoritative list of supported violation codes.

Current gaps:

1. There is no fixture manifest that explains which examples are canonical.
2. Fixture categories and expected outcomes are spread across test code.
3. Golden report coverage is too narrow for report determinism claims.
4. There is no single test that proves every diagnostic code has fixture coverage.
5. There is no corpus-level deterministic report test.
6. There is no corpus-level redaction test over sensitive traces.
7. There is no performance smoke test over multiple traces.
8. There is no documented fixture update workflow.

## Finalized Scope

Milestone 6 should implement:

1. `examples/fixtures/manifest.yaml` as the canonical fixture corpus index.
2. A small pytest fixture-manifest loader under `tests/`.
3. Parametrized tests that run structural and policy checks from the manifest.
4. A guard test that compares manifest diagnostic coverage to `DiagnosticCode`.
5. Representative JSON golden reports under `examples/expected_reports/`.
6. Determinism tests that render equivalent reports twice and compare normalized output.
7. Text report key-line tests for representative passing, failing, warning-only, invalid, and multi-trace cases.
8. Redaction tests that assert configured forbidden strings do not appear in text or JSON reports.
9. A lightweight performance smoke test over a representative multi-trace subset.
10. README and research-note updates describing the fixture corpus and update discipline.
11. A Milestone 6 build report after implementation.

Milestone 6 should not implement:

1. New structural or policy diagnostics.
2. New trace adapters.
3. Directory traversal for `agentlint check`.
4. SARIF, GitHub annotations, HTML, or report file output.
5. A full benchmark framework dependency.
6. Snapshot-test or golden-file third-party plugins.
7. Raw-value report excerpts.
8. Semantic claim verification beyond current explicit provenance checks.
9. Full value graph modeling.

## Reevaluated Decisions

### D6.1 Manifest As Source Of Truth

Decision:

Add a fixture manifest and make corpus tests consume it.

Proposed file:

```text
examples/fixtures/manifest.yaml
```

Reasoning:

The existing examples are useful, but test intent is encoded in scattered parametrization lists. A manifest makes the corpus auditable, supports research evaluation later, and creates a single place to add coverage metadata when a new diagnostic is introduced.

Implementation consequence:

1. Existing trace and policy files stay in their current directories.
2. Tests resolve manifest paths relative to the repository root.
3. New fixtures are added by editing the manifest and adding the trace or golden file.

### D6.2 Keep Current Example Layout

Decision:

Do not reorganize `examples/traces/`, `examples/policies/`, or `examples/expected_reports/` in Milestone 6.

Reasoning:

The current filenames are already descriptive and are referenced by existing tests and documentation. A physical reorganization would create churn without improving the analysis pipeline.

Implementation consequence:

1. `examples/fixtures/` contains corpus metadata only.
2. Existing trace filenames remain stable.
3. Corpus categories live in manifest entries rather than directory names.

### D6.3 Manifest Schema

Decision:

Use a small YAML schema that is strict enough for tests but simple enough to maintain by hand.

Proposed shape:

```yaml
version: 1
fixtures:
  - id: policy_unknown_tool
    trace: examples/traces/policy_unknown_tool.json
    policy: examples/policies/policy_checks.yaml
    categories:
      - policy
      - tool
    expected_status: failed
    expected_diagnostics:
      - UNKNOWN_TOOL
    expected_report: examples/expected_reports/policy_unknown_tool.json
    report_cases:
      - json
      - text
    redaction_forbidden_strings: []
```

Supported fields:

1. `id`: stable fixture identifier.
2. `trace`: trace path.
3. `policy`: policy path or omitted for structural/schema cases.
4. `categories`: one or more labels, such as `passing`, `malformed`, `structural`, `policy`, `redaction`, `report`, or `performance`.
5. `expected_status`: `passed`, `failed`, or `invalid`.
6. `expected_diagnostics`: ordered diagnostic code list.
7. `expected_report`: optional JSON golden report path.
8. `report_cases`: optional list of report formats covered by the fixture.
9. `redaction_forbidden_strings`: optional list of literal values that must not appear in reports.
10. `performance`: optional boolean for the performance smoke subset.

Implementation consequence:

1. Manifest validation should fail fast in tests if required fields are missing.
2. Diagnostic codes in the manifest should be parsed through `DiagnosticCode`.
3. Duplicate fixture IDs should fail tests.

### D6.4 Diagnostic Coverage Guard

Decision:

Add a test that proves all current `DiagnosticCode` values appear in at least one manifest entry.

Reasoning:

Milestone 6 exit criteria require every supported violation to have a stable example. The enum is the best local authority because the CLI, reports, explanations, structural pass, and policy pass all use it.

Implementation consequence:

1. Adding a diagnostic enum member without adding a fixture fails tests.
2. Removing a diagnostic requires removing or updating its fixture coverage.
3. The guard should ignore malformed input errors because they are report input errors, not `DiagnosticCode` values.

### D6.5 Exact JSON Goldens, Targeted Text Assertions

Decision:

Use exact golden comparison for JSON reports and key-line assertions for text reports.

Reasoning:

JSON is the automation contract and should be stable. Text output is for humans, so exact full-text snapshots would make harmless spacing changes expensive.

Implementation consequence:

1. Golden JSON files live in `examples/expected_reports/`.
2. JSON comparisons normalize platform-sensitive path separators before comparison.
3. Text tests assert summary lines, trace identifiers, statuses, diagnostic codes, and threshold lines.
4. Text tests should not assert every blank line or decorative detail.

### D6.6 Deterministic Reports

Decision:

Add tests that render the same report twice and compare normalized output.

Reasoning:

Milestone 5 intentionally avoided timestamps and other volatile fields. Milestone 6 should lock that behavior so JSON reports can be used in CI and research artifacts.

Implementation consequence:

1. Determinism tests should cover at least one passing run, one failing policy run, one invalid input run, and one multi-trace run.
2. Report ordering follows manifest order or command-line input order.
3. JSON output should be compared after parsing, then re-serializing with stable settings or normalizing path separators.

### D6.7 Redaction Corpus Coverage

Decision:

Use manifest-level `redaction_forbidden_strings` to drive redaction tests.

Reasoning:

Redaction tests should be explicit about the values that must not leak. Keeping those strings in the manifest makes the security expectation visible next to the fixture.

Implementation consequence:

1. Redaction tests render both text and JSON reports for matching fixtures.
2. Forbidden strings must be absent from rendered output.
3. Report metadata such as event IDs, diagnostic codes, and policy references may still appear.

### D6.8 Lightweight Performance Smoke Test

Decision:

Add a pytest performance smoke test without adding `pytest-benchmark`.

Reasoning:

The milestone asks for an initial performance smoke test, not a measurement suite. Adding a benchmark dependency now would increase maintenance before the corpus and adapters are stable.

Implementation consequence:

1. Add a `performance` pytest marker to `pyproject.toml`.
2. Select a representative subset through manifest metadata.
3. Use `time.perf_counter()` with a generous threshold and assert the multi-trace check completes.
4. Keep this as a regression smoke test, not a published benchmark number.
5. Defer benchmark history, percentiles, and comparison tooling to the research-evaluation milestone.

### D6.9 No New Runtime Behavior

Decision:

Do not change analyzer semantics or CLI user-facing behavior unless a testability defect is found.

Reasoning:

Milestone 6 is about confidence in existing behavior. New analyzer logic would make it harder to separate fixture discipline from behavior changes.

Implementation consequence:

1. Any unexpected behavior discovered during corpus tests should be fixed only if it contradicts current milestone decisions.
2. Larger semantic gaps should be documented in the build report or deferred list.
3. Full value graph modeling remains deferred.

### D6.10 No Third-Party Snapshot Plugin

Decision:

Use plain pytest assertions and checked-in JSON files for golden tests.

Reasoning:

The project currently has a small dependency set. Plain pytest is enough for deterministic report assertions, and avoiding snapshot plugins keeps fixture updates transparent.

Implementation consequence:

1. Golden report updates are ordinary file edits.
2. Tests should produce clear diffs by comparing parsed JSON structures.
3. There is no hidden snapshot update command in Milestone 6.

## Build Track

### B6.1 Add Fixture Manifest

Files:

```text
examples/fixtures/manifest.yaml
```

Implement:

1. Add manifest entries for existing passing native traces.
2. Add manifest entries for malformed and invalid schema traces.
3. Add manifest entries for every structural diagnostic fixture.
4. Add manifest entries for every policy diagnostic fixture.
5. Mark representative report, redaction, and performance cases.

### B6.2 Add Manifest Test Helpers

Files:

```text
tests/test_fixture_corpus.py
```

Implement:

1. Load the YAML manifest with `yaml.safe_load`.
2. Resolve paths relative to the repository root.
3. Validate required fields.
4. Validate unique fixture IDs.
5. Validate that referenced traces, policies, and expected reports exist.
6. Convert expected diagnostic strings to `DiagnosticCode`.

### B6.3 Add Corpus Diagnostic Tests

Files:

```text
tests/test_fixture_corpus.py
```

Implement:

1. Parametrize over manifest entries.
2. Run `check_trace_file` for each fixture.
3. Assert expected status.
4. Assert ordered diagnostic codes.
5. Assert policy checks are skipped for invalid structural inputs.
6. Keep existing targeted structural and policy unit tests.

### B6.4 Add Diagnostic Coverage Guard

Files:

```text
tests/test_fixture_corpus.py
```

Implement:

1. Collect all manifest diagnostic codes.
2. Compare them with `set(DiagnosticCode)`.
3. Fail with a clear message listing missing fixture coverage.

### B6.5 Expand JSON Golden Reports

Files:

```text
examples/expected_reports/*.json
tests/test_fixture_corpus.py
```

Add representative goldens for:

1. Passing structural trace.
2. Passing policy trace.
3. Failing structural trace.
4. Failing policy trace.
5. Warning-only policy trace.
6. Invalid trace input.
7. Multi-trace report.

### B6.6 Add Report Determinism Tests

Files:

```text
tests/test_fixture_corpus.py
```

Implement:

1. Render selected JSON reports twice.
2. Render selected text reports twice.
3. Normalize platform-sensitive path separators.
4. Assert repeated output matches.
5. Assert JSON goldens match selected fixtures.

### B6.7 Add Text Report Key-Line Tests

Files:

```text
tests/test_fixture_corpus.py
```

Implement:

1. Assert summary counts.
2. Assert `fail-on` line.
3. Assert trace path or trace ID line.
4. Assert status line.
5. Assert diagnostic code lines.
6. Avoid exact full-text snapshots.

### B6.8 Add Redaction Corpus Tests

Files:

```text
tests/test_fixture_corpus.py
```

Implement:

1. Parametrize over entries with `redaction_forbidden_strings`.
2. Render text and JSON reports.
3. Assert forbidden strings are absent.
4. Assert redaction metadata remains present in JSON reports.

### B6.9 Add Performance Smoke Test

Files:

```text
tests/test_fixture_corpus.py
pyproject.toml
```

Implement:

1. Register a `performance` pytest marker.
2. Select manifest entries marked `performance: true`.
3. Run checks across the selected traces.
4. Assert the run completes within a generous local threshold.
5. Keep the threshold conservative to avoid CI flakiness.

### B6.10 Update Documentation

Files:

```text
README.md
Documents/research_note.md
Documents/milestone_6_build_report.md
```

Update:

1. Fixture corpus location and purpose.
2. How to add a new diagnostic fixture.
3. How expected reports are maintained.
4. Current corpus coverage summary.
5. Remaining deferred points after B6.
6. Milestone 6 build report after verification.

## Verification Plan

Required commands:

```text
py -3.12 -m pytest tests\test_fixture_corpus.py
py -3.12 -m pytest
py -3.12 -m ruff check .
py -3.12 -m ruff format --check .
git diff --check
git diff --cached --check
```

Representative manual checks:

```text
py -3.12 -m agentlint check examples\traces\structural_valid_tool_flow.json --format json
py -3.12 -m agentlint check examples\traces\policy_unknown_tool.json --policy examples\policies\policy_checks.yaml --format json
py -3.12 -m agentlint check examples\traces\policy_sensitive_final_answer.json --policy examples\policies\policy_checks.yaml --format text
```

Expected behavior:

1. Corpus tests pass.
2. Every `DiagnosticCode` has manifest fixture coverage.
3. JSON report goldens match normalized generated reports.
4. Text report key lines remain stable.
5. Redaction forbidden strings are absent from report outputs.
6. Performance smoke test passes with a generous threshold.
7. Existing targeted tests continue to pass.
8. Ruff and whitespace checks pass.

## Risks And Mitigations

### Risk: Golden Reports Become Brittle

Mitigation:

Use exact comparison only for JSON, normalize path separators, and keep text tests focused on meaningful lines.

### Risk: Corpus Metadata Drifts From Tests

Mitigation:

Make tests consume the manifest directly and validate every referenced file, diagnostic code, and fixture ID.

### Risk: Performance Smoke Test Becomes Flaky

Mitigation:

Use a representative subset, a generous threshold, and no benchmark assertions about precise latency.

### Risk: Sensitive Values Leak Through New Goldens

Mitigation:

Keep reports metadata-only and drive redaction assertions from manifest-level forbidden strings.

### Risk: M6 Accidentally Expands Product Scope

Mitigation:

Do not add new checks, adapters, report formats, or value graph modeling. Record semantic gaps for later milestones.

## Deferred After Milestone 6

1. Directory traversal and glob-first CLI behavior.
2. SARIF, GitHub annotations, HTML, and file-output reports.
3. Full value graph modeling.
4. External adapter fixture corpus.
5. Benchmark history and performance comparison tooling.
6. Semantic unsupported-claim verification.
7. Snapshot update automation, if manual golden maintenance becomes painful.

## Completion Checklist

- [ ] Fixture manifest exists.
- [ ] Manifest entries cover passing traces.
- [ ] Manifest entries cover malformed and invalid traces.
- [ ] Manifest entries cover every structural diagnostic.
- [ ] Manifest entries cover every policy diagnostic.
- [ ] Manifest loader tests validate schema, paths, IDs, and diagnostic codes.
- [ ] Corpus tests assert status and diagnostic codes.
- [ ] Coverage guard compares manifest codes with `DiagnosticCode`.
- [ ] JSON golden reports cover representative cases.
- [ ] Text report key-line tests cover representative cases.
- [ ] Determinism tests cover JSON and text reports.
- [ ] Redaction tests run from manifest metadata.
- [ ] Performance smoke test runs over multiple traces.
- [ ] README explains fixture update discipline.
- [ ] Research note records corpus status after implementation.
- [ ] Milestone 6 build report is written.
- [ ] Verification commands pass.
