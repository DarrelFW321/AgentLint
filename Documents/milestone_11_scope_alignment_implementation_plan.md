# Milestone 11 Implementation Plan: Scope Alignment and Developer Workflow

## Status

Implemented. See `Documents/milestone_11_build_report.md`.

This milestone is a consolidation milestone. It does not add runtime enforcement, automatic taint tracking, semantic claim evaluation, or another framework adapter. It aligns the implemented product with the narrower promise now recorded in the README, product idea, architecture, requirements specification, roadmap, glossary, and instrumentation guidance.

## Product Contract

AgentLint answers one bounded question:

> Did this recorded agent run violate a developer-defined policy that can be verified from the captured evidence?

The initial product is an offline deterministic linter for completed agent traces. It consumes explicit framework, adapter, and application evidence; normalizes that evidence; checks trace-conformance policies; and produces compiler-style diagnostics and CI outcomes.

The milestone must preserve four distinct trace outcomes:

1. `invalid`: the trace could not be loaded or is structurally incoherent.
2. `failed`: represented evidence demonstrates a policy violation.
3. `not_verifiable`: no represented violation was found, but policy-required evidence is insufficient.
4. `passed`: required evidence is sufficient and no enabled check found a violation.

## User Outcome

The primary supported workflow is:

```powershell
pytest --agentlint --agentlint-policy agentlint.yaml
```

The supported in-process alternative is:

```python
from agentlint.integrations.openai_agents import instrument

session = instrument()
# Run ordinary OpenAI Agents scenarios.
session.close()
```

followed by import and checking where the application does not use the pytest plugin.

A developer should be able to:

1. Capture an existing agent test with one explicit activation point.
2. Write a focused policy without disabling unrelated checks.
3. Receive a pass, failure, invalid, or not-verifiable result that has one clear meaning.
4. Follow each violation through the relevant events and edges without inspecting an entire raw trace.
5. Understand which conclusions AgentLint could not reach because evidence was unavailable.

## Scope

### Included

1. Codifying the offline deterministic product contract in tests and public APIs.
2. Making policy rule activation intentional and focused.
3. Ensuring evidence requirements correspond only to checks the user actually selected.
4. Improving compiler-style diagnostic paths over explicit trace relationships.
5. Improving the ergonomics of explicit approval, data-flow, and final-output evidence without pretending those semantics are automatic.
6. Hardening the OpenAI Agents pytest and one-line capture workflows.
7. Adding realistic, deterministic regression scenarios and consumer documentation.
8. Measuring false failures, false passes, and not-verifiable outcomes against those scenarios.

### Excluded

1. Runtime allow, deny, block, warn, or escalation decisions.
2. Approval user interfaces, approval collection, identity, roles, grants, expiry, or token management.
3. Contextual enterprise authorization or attribute-based access control.
4. Arbitrary Python, model-context, subprocess, or cross-service taint tracking.
5. Natural-language inference of sources, sinks, flows, claims, or evidence relevance.
6. Semantic fact-checking or general LLM-as-judge evaluation.
7. Trace hosting, graphical dashboards, compliance management, or security operations.
8. Agent-version diffing.
9. OPA/Rego.
10. LangGraph or another new framework adapter.
11. Generic child-process injection.

Any excluded feature requires a later product decision and its own milestone. It must not enter M11 as an implementation convenience.

## Current Alignment Gaps

### 1. Rule Activation Is Too Broad

Unspecified policy rules currently behave as enabled at their default severity. Evidence inference uses that behavior, so a policy focused on function tools and approvals can require final-answer or provenance evidence unless unrelated rules are explicitly set to `off`.

This is poor consumer ergonomics and weakens the meaning of `not_verifiable`. A result should be not verifiable because a selected check lacked evidence, not because an unrelated implicit check became active.

### 2. Policy Vocabulary Can Be Misread as Authorization

`permission: allowed|denied` is currently a deterministic trace-conformance setting, but the name can imply that AgentLint is the application's authorization authority. Documentation now limits the claim, but report and explanation language must consistently describe policy conformance rather than production authorization.

No schema rename is required in M11 unless compatibility analysis shows a safe migration path. The initial correction is semantic clarity and consistent diagnostics.

### 3. Explicit Semantic Helpers Expose Trace Plumbing

OpenAI semantic helpers require callers to supply trace and subject identifiers. These are useful low-level primitives, but normal consumers should not need to understand generated snapshot IDs for evidence associated with the current trace or tool span.

Ergonomic improvements must use existing framework context and explicit declarations. They must not introduce hidden monkey-patching or claim exhaustive capture.

### 4. Diagnostics Identify Events but Do Not Yet Present a First-Class Path

Diagnostics contain related event and edge identifiers, but the developer-facing value proposition calls for a concise path such as:

```text
customer_db.lookup.result
  -> model-visible transformation declared by the trace
  -> web_search.query
```

Paths must be derived only from explicit IR edges. AgentLint must never fill missing path segments with a natural-language guess.

### 5. The Primary Workflow Needs Consumer-Level Contract Tests

The repository has strong unit and fixture coverage, but the supported product promise needs end-to-end tests that begin with realistic framework trace objects or a pytest run and end with the expected CI outcome and diagnostic explanation.

## Design Decisions

### 1. Make Rule Activation Explicit and Construct-Driven

Define one central rule activation function used by both policy evaluation and evidence compilation.

A rule is active when either:

1. The policy explicitly configures its severity to `error`, `warning`, or `info`; or
2. A documented policy construct necessarily selects that check.

Proposed construct-driven activation:

| Policy construct | Activated checks |
|---|---|
| Non-empty `tools` | `unknown_tool`, `denied_tool_call` |
| Tool argument constraints | `disallowed_tool_argument` |
| Any tool with `approval: required` | approval checks |
| Sources and sinks plus represented flow policy | selected data-flow checks |
| Explicit final-answer sensitivity configuration | `sensitive_final_answer` |
| Explicit provenance rule configuration | provenance checks |

Provenance checks must not activate merely because a policy file exists. Data-flow checks must not activate when the policy has no source/sink vocabulary. Explicit `off` always wins.

Before implementation, add a compact decision table covering every `RuleId`, its activation construct, required capture capabilities, and default severity. That table becomes the single normative mapping for policy evaluation and evidence assessment.

### 2. Preserve Policy Version 1 if Compatibility Allows

Prefer a behavioral correction within policy version 1 if existing policies that explicitly configure rules remain stable. If changing implicit activation would silently weaken existing policies, add a compatibility diagnostic or a policy-loading mode rather than silently changing conclusions.

The implementation plan must include fixture migration analysis before choosing the compatibility mechanism.

### 3. Treat Tool Permission as Trace Conformance

M11 does not add conditional authorization expressions.

The checker may conclude:

```text
This recorded call used a tool denied by this trace policy.
```

It must not claim:

```text
This user was not legally or operationally authorized to perform this action.
```

Contextual authorization systems can emit an approval or decision event that AgentLint verifies later. They remain separate systems.

### 4. Keep Evidence Explicit

Data-flow and provenance paths are built from IR relationships already represented by the adapter or application:

1. `data_flow`
2. `approval_for`
3. `provenance`
4. `parent` when needed only for execution context

No new check may infer a semantic edge from event proximity, matching text, identical values, span names, or model-generated reasoning.

### 5. Add Structured Diagnostic Paths

Extend diagnostics with an optional sanitized path model:

```text
DiagnosticPath
  nodes[]: event ID plus safe event label
  edges[]: edge ID plus edge type
```

Requirements:

1. Paths reference existing IR events and edges only.
2. Paths contain no raw prompts, arguments, results, approval reasons, or final-answer content.
3. Ordering is deterministic.
4. Text reports render a compact arrow path.
5. JSON reports preserve the structured path.
6. Diagnostics without a meaningful multi-event path may omit it.
7. Report schema compatibility is explicitly decided before implementation; add report v4 only if the serialized contract changes.

### 6. Add Context-Aware Convenience Helpers, Not Automatic Semantics

Keep the existing explicit session methods as stable low-level primitives. Add convenience APIs only where the OpenAI Agents SDK exposes a reliable active trace or span context.

Candidate shapes to validate with a small spike:

```python
session.record_current_approval(decision="approved")
session.record_current_source(name="customer_profile", sensitivity="private")
session.record_current_sink(
    name="web_search.query",
    source_events=[source_event],
    visibility="public",
)
```

Acceptance conditions:

1. The helper fails clearly outside a supported active context.
2. It resolves IDs through public SDK context APIs.
3. It records the same explicit snapshot semantics as the low-level method.
4. It does not wrap or block the tool call.
5. It does not claim `captured` coverage when only declared instances are represented.

If reliable context cannot be established, do not ship the convenience helper. Improve documentation around the low-level API instead.

## Work Plan

### Phase 1: Freeze the Scope Contract

1. Add a short architecture decision record for offline deterministic scope.
2. Add a contributor checklist for proposed rules and integrations.
3. Add terminology tests or documentation assertions where practical:
   - represented evidence;
   - trace conformance;
   - not verifiable;
   - no runtime enforcement claim.
4. Identify public surfaces that still imply automatic authorization, exhaustive capture, or semantic truth.

Deliverable:

```text
Documents/architecture_decision_offline_trace_linter.md
```

### Phase 2: Centralize Rule Activation and Evidence Requirements

1. Introduce a `PolicyRulePlan` or equivalent internal compiled-policy model.
2. Compile active rules, effective severities, activation origins, and evidence requirements once.
3. Make `evaluate_policy()` consume the compiled plan.
4. Make `assess_evidence()` consume the same compiled plan.
5. Remove duplicated default-rule reasoning from the evaluator and evidence module.
6. Add unit tests for every rule and construct combination.
7. Add migration tests for all existing example policies.

Required invariant:

> A rule cannot require evidence unless that same compiled rule is active for policy evaluation.

### Phase 3: Focused Policy UX

1. Create minimal starter policies for:
   - tool inventory only;
   - tool arguments;
   - approval-required action;
   - explicit source-to-sink flow;
   - explicit final-answer provenance.
2. Ensure each starter policy activates only relevant checks.
3. Add `agentlint policy explain POLICY.yaml` or an equivalent dry-run summary only if it can be implemented without widening the CLI substantially.
4. At minimum, make `policy validate` report:
   - active checks;
   - inferred evidence requirements;
   - explicitly strengthened requirements.
5. Update policy documentation around trace conformance versus authorization.

Example desired summary:

```text
policy: support-refunds
active checks: unknown_tool, denied_tool_call, missing_approval
required evidence: tool_calls>=partial, approvals>=partial
```

### Phase 4: Diagnostic Paths

1. Define the sanitized diagnostic-path model.
2. Add deterministic path construction over explicit IR edges.
3. Attach paths to approval, data-flow, and provenance diagnostics where applicable.
4. Render paths in text and JSON reports.
5. Add golden fixtures for representative paths.
6. Confirm reports contain no raw sensitive values.

Do not add a graph UI in this phase.

### Phase 5: Semantic Helper Ergonomics

1. Spike public OpenAI SDK context resolution for active trace and function span IDs.
2. Implement only helpers supported reliably by public APIs.
3. Preserve low-level explicit methods.
4. Add misuse errors for calls outside active capture contexts.
5. Document coverage as `partial` for declaration-based semantics.
6. Add zero-network tests using real SDK trace objects.

### Phase 6: Consumer Workflow Hardening

1. Test `pytest --agentlint --agentlint-policy ...` from process startup to CI exit.
2. Verify a requested capture with zero traces fails clearly.
3. Verify unsupported SDK versions fail before the test run produces a misleading pass.
4. Verify additive and `local_only` processor behavior remains explicit.
5. Test synchronous and asynchronous agent scenarios where supported.
6. Document process-global instrumentation and repeated-call behavior.
7. Ensure captured files and reports use predictable local directories and do not require hosted trace export.

### Phase 7: Realistic Regression Corpus

Add deterministic scenarios representing the initial product wedge:

1. Unknown tool introduced by a prompt or routing change.
2. Denied tool call represented in a completed trace.
3. Required tool argument missing or invalid.
4. Sensitive action without recorded approval.
5. Approval recorded after the action.
6. Explicit private-to-public flow.
7. Explicit untrusted-to-privileged flow.
8. Explicit claim with a missing evidence reference.
9. Clean focused policy with sufficient evidence.
10. Clean behavior with insufficient evidence producing `not_verifiable`.

Each scenario must declare its realism tier:

1. Handwritten native fixture.
2. Real framework trace objects without an API call.
3. Optional live agent run, excluded from default tests.

### Phase 8: Documentation and Release Readiness

1. Build one five-minute quickstart around a focused tool-and-approval policy.
2. Build one explicit data-flow example that explains the annotation boundary.
3. Explain all four outcomes with examples.
4. Document what AgentLint did and did not verify in every example.
5. Remove or clearly label future runtime-gating language from user-facing onboarding.
6. Add a release checklist covering schema versions, golden reports, redaction, and compatibility.

## Test Strategy

### Unit Tests

1. Compiled rule activation for every `RuleId`.
2. Shared rule-to-evidence mapping.
3. Explicit `off` precedence.
4. Explicit severity activation.
5. Focused policies do not require unrelated capabilities.
6. Deterministic path construction.
7. Path redaction and stable ordering.
8. Context-aware helper success and misuse behavior.

### Fixture and Golden Tests

1. One canonical fixture per active diagnostic.
2. One `not_verifiable` fixture per capability family.
3. Text and JSON golden output for diagnostic paths.
4. No raw sensitive payloads in reports.
5. Existing fixture manifest remains exhaustive for diagnostic codes.

### Integration Tests

1. Native trace -> check -> report -> exit code.
2. OpenTelemetry fixture -> import -> check -> report.
3. OpenAI SDK objects -> snapshot -> adapter -> check -> report.
4. Pytest activation -> capture -> policy -> terminal summary -> exit code.
5. No-capture and unsupported-version failures.

### Optional Live Test

One small API-backed OpenAI Agents scenario may remain opt-in. It validates integration drift, not policy semantics, and must never be required for the default suite.

## Acceptance Criteria

M11 is complete when:

1. All public core documents use the offline deterministic scope contract.
2. A focused policy activates only checks implied or explicitly enabled by that policy.
3. Policy evaluation and evidence assessment use one compiled rule plan.
4. No active check can be paired with a contradictory evidence requirement.
5. A missing required capability produces `not_verifiable`, not a fabricated violation or pass.
6. Tool permission diagnostics are worded as trace-policy conformance, not universal authorization conclusions.
7. Approval, data-flow, and provenance diagnostics can render exact sanitized paths when explicit edges exist.
8. No path renderer invents missing relationships.
9. The primary pytest workflow has end-to-end tests for passed, failed, invalid/no-capture, and not-verifiable outcomes.
10. Semantic convenience helpers, if shipped, use public SDK context and fail clearly outside it.
11. Reports remain metadata-only and do not expose raw prompts, arguments, results, approvals, or answers.
12. The default test suite makes no network calls and passes on Python 3.12.
13. Ruff, formatting, fixture-corpus, golden-report, and `git diff --check` validation pass.
14. Deferred features listed in this plan have not entered the implementation.

## Recommended Implementation Order

```text
scope ADR
  -> compiled rule activation and evidence plan
  -> focused policy UX
  -> structured diagnostic paths
  -> context-aware helper spike
  -> consumer workflow tests
  -> realistic regression corpus
  -> quickstart and release review
```

The compiled rule plan is the critical first implementation. Diagnostic paths or helper ergonomics should not be built on top of the current overly broad rule activation behavior.

## Risks and Mitigations

### Compatibility Risk

Changing implicit rule activation may change results for existing policies.

Mitigation: evaluate every checked-in policy and fixture before selecting a migration mechanism. Prefer explicit warnings or a documented compatibility mode over silent weakening.

### False Confidence Risk

Ergonomic helpers may be mistaken for exhaustive capture.

Mitigation: declaration-based semantics remain `partial`, reports retain capture limitations, and docs state what was not observed.

### Scope Creep Risk

Approval and tool policy work may drift into runtime authorization.

Mitigation: M11 records and verifies completed-trace evidence only. Any proposal that changes whether a tool executes is rejected from this milestone.

### Diagnostic Path Risk

A human-readable path may tempt the implementation to infer missing relationships.

Mitigation: every rendered segment must reference an existing event or edge ID. Incomplete explicit paths are shown as incomplete rather than repaired heuristically.

## Post-Milestone Decision

After M11, evaluate the workflow on additional real OpenAI Agents projects before choosing the next major feature.

The evaluation should measure:

1. Time from installation to first useful CI result.
2. Number of annotations required per scenario.
3. False-positive and false-negative findings identified through manual trace review.
4. Frequency and usefulness of `not_verifiable`.
5. Whether diagnostic paths reduce debugging time.
6. Which missing framework semantics create the most user friction.

Only then choose between improving the existing OpenAI integration, adding a LangGraph adapter, or extending one deterministic policy capability. Runtime enforcement and semantic evaluation remain separate product decisions.
