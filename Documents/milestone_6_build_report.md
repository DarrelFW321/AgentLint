# Milestone 6 Build Report

Status: implemented.

Milestone 6 built the fixture corpus and regression discipline around the existing AgentLint analyzer, policy, report, and CLI behavior. No new analyzer rules, external adapters, report formats, or runtime behavior were added.

## Implemented

1. Added `examples/fixtures/manifest.yaml` as the canonical fixture corpus index.
2. Indexed passing native, passing structural, passing policy, malformed, invalid, structural violation, policy violation, redaction, report, and performance-smoke fixtures.
3. Added manifest-driven tests in `tests/test_fixture_corpus.py`.
4. Added a coverage guard proving every current `DiagnosticCode` has fixture coverage.
5. Added JSON golden reports for representative passing, failing, warning-only, invalid, and multi-trace cases.
6. Added deterministic JSON and text report tests.
7. Added text report key-line tests instead of brittle full-text snapshots.
8. Added manifest-driven redaction tests for sensitive fixtures.
9. Added a lightweight performance smoke test over multiple traces.
10. Registered the `performance` pytest marker.
11. Updated README and the research note with fixture-corpus discipline.

## Corpus Coverage

The manifest covers:

1. Passing native traces.
2. Malformed JSON and schema-invalid traces.
3. Structural diagnostics:
   - `DUPLICATE_EVENT_ID`
   - `DUPLICATE_EDGE_ID`
   - `MISSING_EVENT_REFERENCE`
   - `TOOL_RESULT_WITHOUT_MATCHING_CALL`
   - `TOOL_CALL_MISSING_ARGUMENTS`
   - `INVALID_EVENT_ORDER`
   - `INVALID_EVIDENCE_REFERENCE`
4. Policy diagnostics:
   - `UNKNOWN_TOOL`
   - `UNAUTHORIZED_TOOL_CALL`
   - `DISALLOWED_TOOL_ARGUMENT`
   - `MISSING_APPROVAL`
   - `APPROVAL_AFTER_ACTION`
   - `ACTION_AFTER_DENIAL`
   - `APPROVAL_MISMATCH`
   - `PRIVATE_TO_PUBLIC_SINK`
   - `SECRET_EXPOSURE`
   - `UNTRUSTED_TO_PRIVILEGED_ACTION`
   - `SENSITIVE_FINAL_ANSWER`
   - `UNSUPPORTED_CLAIM`
   - `INVALID_PROVENANCE_REFERENCE`
   - `EVIDENCE_AFTER_CLAIM`

## Key Decisions

1. The manifest is the source of truth for corpus intent.
2. Existing example directories were kept stable to avoid churn.
3. JSON reports are compared exactly after normalizing platform-sensitive trace paths.
4. Text reports are asserted by stable content lines rather than full snapshots.
5. New diagnostic codes now require manifest fixture coverage.
6. The performance check remains a smoke test, not a benchmark suite.
7. Full value graph modeling, external adapters, SARIF, HTML reports, report file output, and semantic claim verification remain deferred.

## Verification

Commands run during implementation:

```text
py -3.12 -m pytest tests\test_fixture_corpus.py
py -3.12 -m pytest
py -3.12 -m ruff check .
py -3.12 -m ruff format --check .
git diff --check
git diff --cached --check
```

Results:

```text
tests\test_fixture_corpus.py: 55 passed
full pytest suite: 209 passed
ruff check: passed
ruff format --check: passed
git diff --check: passed
git diff --cached --check: passed
```

## Deferred

1. Directory traversal and glob-first CLI behavior.
2. SARIF, GitHub annotations, HTML reports, and report file output.
3. External adapter fixture corpora.
4. Benchmark-history tooling.
5. Full value graph modeling.
6. Semantic unsupported-claim verification.
7. Snapshot update automation.
