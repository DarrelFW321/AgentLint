# Milestone 10 Build Report

## Outcome

Milestone 10 implements semantic capture and policy-specific verifiability. AgentLint no longer reports a clean policy pass when evidence required by that policy is unavailable, unknown, or below the configured minimum.

## Implemented

1. Added additive policy v1 `capture.require` entries with `partial` and `captured` minimums.
2. Added deterministic inference of evidence requirements from tool inventories, argument constraints, approval requirements, data-flow policy, final-answer checks, and provenance checks.
3. Added explicit-over-inferred merging using the stricter requirement.
4. Added evidence assessments with required level, observed status, origin, and sanitized capture reason.
5. Added `not_verifiable` as a fourth trace outcome.
6. Preserved known behavioral diagnostics even when unrelated evidence is incomplete.
7. Bumped machine-readable reports to `agentlint.report.v3`.
8. Added per-run unmet evidence output and aggregate unmet-capability counts.
9. Made invalid and not-verifiable traces fail CLI and pytest independently of `--fail-on`.
10. Made pytest load its policy during configuration and retain explicit activation.
11. Extended the OpenAI capture session with symbolic source and sink records.
12. Resolved approval subjects from SDK function-span IDs to normalized tool-call IDs.
13. Normalized declared source-to-sink relationships into existing IR `data_flow` edges.
14. Preserved existing explicit authoritative final-output recording.
15. Added a focused OpenAI function-tool starter policy.
16. Added a zero-cost customer-support example built from real OpenAI Agents SDK trace objects.
17. Added a permanent not-verifiable fixture and report v3 goldens.

## Outcome Precedence

```text
invalid input or structure -> invalid
known behavioral diagnostics -> failed
unmet evidence requirements -> not_verifiable
otherwise -> passed
```

A failed trace can also list unmet evidence. Missing evidence never fabricates a behavioral diagnostic.

## Semantic Boundary

OpenAI tracing automatically captures ordinary agent, model, function-tool, handoff, and guardrail activity. M10 helpers record only semantics the SDK does not authoritatively expose:

1. Approval or denial linked to a captured action.
2. Symbolic source labels and classifications.
3. Symbolic sink labels and declared source-to-target flow.
4. Authoritative `RunResult.final_output`.

Source and sink helpers persist labels, classifications, and event relationships, not source values or sink payloads. Partial coverage validates represented declarations and does not prove application-wide absence of unannotated flows.

## Demonstration

Run:

```powershell
py -3.12 examples\openai_agents\customer_support\demo.py
```

The offline workflow uses real SDK trace objects and makes no API request. It produces one passed approved-refund trace, one failed missing-approval trace, and one not-verifiable trace with unavailable approval evidence.

## Compatibility

1. Native IR remains `agentlint.ir.v1`.
2. Capture remains `agentlint.capture.v1`.
3. Policy remains version 1 with an additive optional field.
4. Report consumers must migrate from v2 to v3.
5. Existing policies still load, but previously clean traces can become not verifiable when they lack required evidence declarations.

## Deferred

1. Implicit Python taint or value tracking.
2. Automatic sensitivity, trust, approval, or provenance inference.
3. Generic child-process command wrapping.
4. Automatic `Runner` result wrapping without reliable trace identity.
5. Exhaustive hosted-tool capture guarantees.
6. LangGraph and other framework adapters.
7. OPA/Rego integration.
8. Runtime action gating.

## Verification

Verified on Python 3.12.10 with OpenAI Agents SDK 0.18.2:

```text
253 passed, 1 skipped
```

The skipped default test is the explicitly activated pytest-plugin sample. Running it with the focused OpenAI function-tool policy produced one passing AgentLint report and exited zero. Running the same captured behavior with the broad policy produced one `not_verifiable` report and exited one because approval, data-flow, provenance, and final-answer evidence was unavailable.

The zero-cost customer-support demo produced one passed, one failed, and one not-verifiable trace. Ruff linting, Ruff formatting, and `git diff --check` pass.
