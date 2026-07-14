# Milestone 8 Build Report: Capture Completeness Reporting

Status: implemented.

## Outcome

Milestone 8 makes the evidence boundary of every checked trace visible. AgentLint now reports what execution behavior was captured, partially captured, unavailable, or unknown without conflating capture quality with policy violations.

## Implemented

1. Added strict `agentlint.capture.v1` models with a fixed nine-capability vocabulary.
2. Added `captured`, `partial`, `unavailable`, and `unknown` states.
3. Added conservative overall-state derivation with unknown taking precedence.
4. Added bounded, single-line reasons and notes to reduce report leakage risk.
5. Added optional typed capture metadata to native AgentLint IR v1.
6. Made undeclared native traces report all capabilities as unknown.
7. Made invalid inputs report unknown capture with a sanitized explanation.
8. Required `AdapterResult.capture` to match the profile attached to its normalized trace.
9. Added a conservative all-partial profile to generic OpenTelemetry imports.
10. Persisted OpenTelemetry completeness through the import-to-native-file workflow.
11. Recorded import incident codes as deterministic sanitized capture notes.
12. Added per-trace capture profiles and aggregate status counts to reports.
13. Bumped machine-readable reports to `agentlint.report.v2`.
14. Added per-capability text output and the limited-verification statement for passing incomplete traces.
15. Preserved existing diagnostic thresholds: capture incompleteness does not fail checks in M8.
16. Updated deterministic report goldens and the generated OpenTelemetry examples.

## Current OpenTelemetry Profile

Generic OpenTelemetry reports every capability as partial because explicit AgentLint attributes can represent semantics but generic spans cannot prove exhaustive capture.

| Capability | State |
| --- | --- |
| Agent runs | Partial |
| Model calls | Partial |
| Tool calls | Partial |
| Tool arguments | Partial |
| Tool results | Partial |
| Approvals | Partial |
| Data flow | Partial |
| Provenance | Partial |
| Final answers | Partial |

Import warnings remain concrete incident records. Capture completeness remains the broader evidence contract.

## Compatibility

1. Existing native IR v1 files remain valid because `capture` is optional.
2. Native traces without capture metadata no longer imply completeness; reports synthesize an unknown profile.
3. JSON report consumers must migrate from `agentlint.report.v1` to `agentlint.report.v2`.
4. Existing structural checks, policy checks, diagnostic codes, and `--fail-on` behavior are unchanged.

## Verification

The implementation is covered by tests for:

1. Strict models and unknown capability rejection.
2. All aggregate-state precedence cases.
3. Native backward compatibility.
4. Invalid input behavior.
5. OpenTelemetry persistence and conservative coverage.
6. Adapter/trace profile consistency.
7. Mixed-status report aggregation.
8. Text limited-verification wording.
9. JSON report v2 goldens and determinism.
10. Bounded single-line explanations and payload-free OpenTelemetry notes.

Final verification commands:

```powershell
py -3.12 -m pytest
py -3.12 -m ruff check .
py -3.12 -m ruff format --check .
git diff --check
```

## Deferred

1. Policy-specific mandatory coverage.
2. Rule-to-capability dependency mapping.
3. Coverage-based CI failure behavior.
4. OpenAI Agents framework guarantees and version compatibility.
5. Runtime partial-trace completeness.
6. Value-level completeness and numeric scoring.
