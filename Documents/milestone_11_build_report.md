# Milestone 11 Build Report: Scope Alignment and Developer Workflow

## Outcome

Milestone 11 aligns the implementation with AgentLint's bounded product contract:

> Did this recorded agent run violate a developer-defined policy that can be verified from the captured evidence?

The implementation remains an offline deterministic trace linter. It does not add runtime enforcement, automatic taint tracking, semantic claim judgment, approval collection, or another framework adapter.

## Implemented

1. Added a compiled policy plan shared by policy evaluation and evidence assessment.
2. Centralized default severities, construct-driven rule activation, explicit severity overrides, explicit `off` precedence, and rule-to-evidence requirements.
3. Changed focused policies so they no longer activate unrelated provenance or final-answer checks by default.
4. Made provenance rules explicitly activated unless selected by a future documented construct.
5. Made `agentlint policy validate` print active checks and inferred minimum evidence requirements.
6. Added focused starter policies for tool inventory, approvals, explicit data flow, and explicit provenance.
7. Added sanitized structured diagnostic paths composed only of represented IR events and edges.
8. Bumped machine-readable reports to `agentlint.report.v4`.
9. Added compact text rendering for exact explicit paths.
10. Preserved metadata-only reporting: path labels contain event types, tool names, event IDs, edge IDs, and edge types, not raw payloads.
11. Added context-aware OpenAI helpers for current-trace sources, current-function approvals, and current-function sinks.
12. Kept existing explicit trace-ID/session methods as low-level primitives.
13. Added clear errors when current-context helpers are called outside a supported SDK trace or span.
14. Added an accepted architecture decision for the offline deterministic product boundary.
15. Added compiled-plan, focused-policy, path, redaction, helper-context, CLI-summary, fixture, and report-v4 coverage.
16. Renamed active tool-conformance language from `unauthorized_tool_call` / `UNAUTHORIZED_TOOL_CALL` to `denied_tool_call` / `DENIED_TOOL_CALL`.
17. Preserved legacy policy input and diagnostic explanation lookup as migration aliases while emitting only the new terminology.

## Rule Activation Contract

Rules are active when explicitly configured or implied by a documented policy construct. Explicit `off` always wins.

Current construct-driven activation is:

| Construct | Checks |
|---|---|
| Non-empty tool inventory | unknown and trace-policy-denied tool calls |
| Tool argument constraints | disallowed tool arguments |
| Approval-required tool | missing, late, denied, or mismatched approval evidence |
| Compatible source and sink classifications | the applicable explicit data-flow check |
| Sources plus `final_answer` sink | sensitive final-answer flow |
| Explicit provenance rule | explicit claim/provenance integrity |

Policy evaluation and evidence assessment receive the same compiled plan during `check_trace()`. Therefore a rule cannot require evidence unless that rule is active.

## Diagnostic Path Contract

Report v4 adds an optional path containing:

1. Sanitized event IDs and labels.
2. Existing IR edge IDs and edge types.
3. Deterministic ordering.

The path builder performs deterministic traversal over represented edges. When no explicit path exists, the diagnostic omits the path instead of inferring a missing relationship.

## OpenAI Semantic Ergonomics

The capture session now supports:

```python
session.record_current_approval(decision="approved")
source_id = session.record_current_source(
    name="customer_profile",
    sensitivity="private",
)
session.record_current_sink(
    name="web_search.query",
    source_events=[source_id],
    visibility="public",
)
```

These helpers use public SDK tracing context. They record explicit declarations and retain partial coverage; they do not imply exhaustive application-wide capture or affect whether the tool executes.

## Consumer Workflow Verification

The focused pytest workflow completed with one passing trace and exit zero:

```powershell
py -3.12 -m pytest -q tests\test_openai_pytest_plugin_sample.py `
  --agentlint `
  --agentlint-policy examples\policies\openai_function_tools.yaml
```

The same represented behavior checked against the broad policy produced one `not_verifiable` trace and exit one because approvals, data flow, provenance, and final-answer evidence were unavailable. It produced no fabricated behavioral diagnostic.

## Compatibility

1. Native trace IR remains `agentlint.ir.v1`.
2. Capture remains `agentlint.capture.v1`.
3. Policy remains version 1.
4. Existing explicitly configured policy rules retain their configured severity.
5. Consumers of machine-readable reports must migrate from report v3 to report v4.
6. Policies that relied on every unspecified rule being implicitly enabled should explicitly list those rules. This is an intentional scope and usability correction.

## Deferred

1. Runtime action enforcement.
2. Approval collection, identity, roles, grants, or authorization tokens.
3. Contextual enterprise authorization.
4. Arbitrary runtime taint tracking.
5. Natural-language flow or provenance inference.
6. Semantic fact-checking and general LLM evaluation.
7. Graphical trace exploration.
8. Agent-version diffing.
9. OPA/Rego.
10. Another framework adapter.

## Verification

Verified with Python 3.12:

```text
280 passed, 1 skipped
```

The skipped default test is the explicitly activated pytest-plugin sample. The sample was also run separately in passing and not-verifiable configurations. Ruff linting, Ruff formatting, fixture-corpus goldens, metadata redaction assertions, and `git diff --check` pass.
