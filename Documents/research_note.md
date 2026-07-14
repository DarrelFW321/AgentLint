# AgentLint Research Note

This document records research findings, design decisions, limitations, open questions, and experimental results for AgentLint. The working assumption is that this project may later become an arXiv note or research paper, so entries should preserve enough context to support a clear technical narrative.

## Working Title

AgentLint: Policy Checking for Tool-Using AI Agent Execution Traces

## Research Framing

AgentLint studies how recorded AI agent executions can be normalized into a common intermediate representation and checked against developer-defined policies for tool use, data flow, approval requirements, and final-answer provenance.

The project is not framed as proving general agent safety. It is framed as verifying concrete, policy-relevant properties over specific recorded or in-progress executions.

## Core Hypothesis

Tool-using AI agent executions can be treated as analyzable traces. By translating heterogeneous trace formats into a common intermediate representation, we can apply compiler-inspired validation, data-flow analysis, provenance checking, and policy evaluation to detect meaningful safety and correctness violations before deployment.

## Proposed Contribution

1. A trace-oriented intermediate representation for tool-using AI agent executions.
2. A compiler-style analysis pipeline for importing, normalizing, enriching, and checking traces.
3. A policy model for expressing tool permissions, data-handling constraints, approval requirements, and provenance requirements.
4. A set of concrete violation categories relevant to agent safety engineering.
5. An implementation that produces CI-compatible diagnostics over realistic traces.
6. Case studies or examples showing detected failures in representative agent workflows.

## Current Design Direction

AgentLint should use a compiler-inspired pipeline:

```text
raw traces
  -> adapters
  -> schema validation
  -> AgentLint intermediate representation
  -> enrichment passes
  -> analysis passes
  -> policy evaluation
  -> diagnostics and reports
```

The intermediate representation should be graph-shaped rather than only sequential. Event order, data dependencies, approval links, and provenance links are distinct relationships and should be represented explicitly.

## Candidate Analyses

### Structural Validation

- Duplicate event identifiers.
- Missing references.
- Tool results without matching tool calls.
- Tool calls with missing arguments.
- Invalid event ordering.
- Final answers referencing nonexistent evidence.

### Tool Policy Checking

- Unauthorized tool calls.
- Unknown tools not covered by policy.
- High-risk tools called without required approval.
- Tool calls made after explicit denial.
- Tool arguments violating configured constraints.

### Data-Flow Checking

- Private data flowing into public tools.
- Secret data entering model-visible context.
- Untrusted content influencing privileged actions.
- Sensitive data appearing in final answers when disallowed.
- Missing sensitivity labels for policy-relevant values.

### Provenance Checking

- Final-answer claims without supporting evidence.
- Claims pointing to nonexistent evidence.
- Evidence occurring after the claim.
- Evidence that is structurally incompatible with the claim.
- Contradictions between final answers and tool results where detectable.

## Known Limitations

These limitations should be tracked honestly and refined as the implementation develops.

1. AgentLint checks concrete executions, not all possible future executions.
2. The quality of analysis depends on the completeness and fidelity of the trace.
3. Data-flow precision may be limited when traces contain only natural-language strings rather than structured value references.
4. Provenance checking is difficult without explicit claim-to-evidence annotations.
5. Semantic contradiction detection may require model-assisted or domain-specific methods, which should not be assumed trustworthy by default.
6. Trace adapters may lose information when source frameworks expose incomplete or inconsistent metadata.
7. Policy results are only as strong as the policies developers define.
8. Runtime gating introduces latency, partial-information, and reliability constraints not present in offline analysis.

## Open Questions

1. What is the minimal intermediate representation that supports useful V1 checks without overfitting to one tracing framework?
2. Should the policy language remain a purpose-built YAML DSL, or should AgentLint support a logic language such as Rego or Datalog?
3. How should AgentLint represent uncertain or inferred data-flow edges?
4. What diagnostics make trace policy violations most actionable for developers?
5. Which external adapter should be implemented first for the strongest demonstration?
6. How should sensitive values be redacted while preserving useful debugging context?
7. What benchmark traces or case studies would best demonstrate practical value?

## Evaluation Ideas

Possible evaluation dimensions:

1. Ability to import realistic traces from at least one external system.
2. Number and clarity of detected policy violations across curated failure scenarios.
3. False positive and false negative behavior on hand-labeled traces.
4. Runtime overhead for offline CI analysis.
5. Diagnostic usefulness in developer review.
6. Extensibility of the IR and policy system when adding a new adapter or rule.

Candidate case studies:

1. Customer-support agent leaking private account data into a public web search.
2. Email agent sending a message without approval.
3. Research agent making unsupported claims in a final answer.
4. Browser agent taking privileged action based on untrusted web content.
5. Coding agent exposing repository secrets in a model-visible or public context.

## Paper Outline Draft

1. Introduction
2. Background and Motivation
3. Problem Statement
4. Agent Execution Trace Model
5. AgentLint Intermediate Representation
6. Policy Language and Violation Model
7. Analysis Pipeline
8. Implementation
9. Case Studies or Evaluation
10. Limitations
11. Related Work
12. Conclusion

## Findings Log

Use this section to add dated findings as the project develops.

### 2026-06-30

- Initial product framing: AgentLint is a CI linter for AI agent traces.
- Initial technical framing: a compiler-style trace analysis pipeline appears appropriate.
- Important distinction: event order, data flow, approvals, and provenance should be modeled as separate relationships over a shared trace graph.
- Roadmap decision: V1 should use a purpose-built YAML policy DSL and built-in analysis engine. OPA/Rego should be evaluated later as an optional backend over exported AgentLint facts, after the IR and diagnostics are stable.
- Milestone 0 planning decision: start with a minimal Python package, Typer CLI, pytest smoke tests, example directories, architecture note, glossary, and research baseline. Defer IR models and real trace validation to Milestone 1.
- Milestone 0 R0 research decision: use `uv`, `pyproject.toml`, Python 3.12+, `src/` layout, Typer, pytest, Pydantic, PyYAML, Rich, and Ruff. Add `src/agentlint/__main__.py` so `python -m agentlint` works as a fallback. Defer strict type-checker selection until after the first schemas exist.
- Milestone 0 build baseline: created the initial Python package skeleton, minimal CLI, smoke tests, example directories, architecture note, and glossary. Verification passed on Python 3.12.10 via `py -3.12 -m agentlint`, `py -3.12 -m pytest`, and Ruff. Local environment caveat: default `python` is 3.11.4, and the Python 3.12 user scripts directory is not on `PATH`; `uv` is installed and currently works through `py -3.12 -m uv`.
- Milestone 1 R1 research decision: define a native JSON `agentlint.ir.v1` trace with `schema_version`, `trace_id`, `metadata`, `events`, and `edges`; model events as Pydantic discriminated unions keyed by `type`; keep edges event-to-event; preserve small `source_ref` pointers; reject duplicate IDs and missing edge endpoints as IR construction errors; keep stable diagnostics and semantic structural checks for Milestone 2. Detailed findings are recorded in `Documents/milestone_1_research.md`.
- Milestone 1 build decision: implemented `agentlint.ir.v1` Pydantic models, native JSON loading, `agentlint validate TRACE.json`, native trace examples, and focused tests. The implementation resolves R1 open questions by adding a minimal `Claim` model, using a local recursive `JsonValue` alias, keeping loader-owned file errors, testing generated schema behavior without committing schema output, and treating duplicate IDs as validation errors until Milestone 2 diagnostics exist.
- Milestone 2 planning decision: structural validation should move duplicate ID and missing-reference checks out of Pydantic construction and into a structural pass so AgentLint can emit stable diagnostic codes. Milestone 2 should add diagnostic models, structural checks, lightweight terminal formatting, structural fixtures, and `agentlint validate` behavior that runs schema validation followed by structural validation. Detailed planning is recorded in `Documents/milestone_2_implementation_plan.md`.
- Milestone 2 architecture finalization: finalized the schema-versus-structural boundary, IR relaxations, diagnostic model shape, structural pass ownership, diagnostic code scope, deterministic duplicate/reference handling, event ordering semantics, claim evidence representation, CLI validation flow, fixture strategy, and deferred work. The final decision record is `Documents/milestone_2_architecture_decisions.md`.
- Milestone 2 R2 research decision: parallel research confirmed the finalized architecture and added implementation refinements: keep message content and model input schema-required, reject empty optional reference strings at schema level, define diagnostic cardinality explicitly, treat duplicated IDs as ambiguous rather than missing, stage tool-result matching before ordering checks, and assert CLI stdout/stderr separately. Detailed findings are recorded in `Documents/milestone_2_research.md`.

### 2026-07-01

- Milestone 2 build decision: implemented diagnostics, structural validation, structural fixtures, CLI structural validation flow, and test coverage for every Milestone 2 diagnostic code. Relationship checks for duplicate IDs and missing event references now run in `agentlint.passes.structural` rather than Pydantic construction.
- Milestone 2 IR boundary update: `ToolCallEvent.arguments` is optional so missing arguments can become `TOOL_CALL_MISSING_ARGUMENTS`; `Claim.evidence` records event-level evidence references; optional reference strings remain non-empty when present.
- Type-checker decision: defer Pyright or mypy again. The current Pydantic discriminated-union surface is still small, and adding a type checker in Milestone 2 would mostly tune configuration rather than reduce meaningful structural-validation risk. Reevaluate when policy and report contracts add broader typed APIs.
- Milestone 3 planning decision: YAML Policy DSL V1 should define the policy input contract without running policy checks yet. Policy validation belongs in `agentlint.policy`; policy enforcement remains Milestone 4. Detailed planning is recorded in `Documents/milestone_3_implementation_plan.md`.
- Milestone 3 architecture finalization: finalized the policy package boundary, safe YAML loading, duplicate-key rejection, strict Pydantic policy schema, policy-specific enums, rule IDs, shallow argument constraints, source/sink names, structured exceptions, and CLI policy validation behavior. The decision record is `Documents/milestone_3_architecture_decisions.md`.
- Milestone 3 build decision: implemented YAML policy models, safe policy loading with duplicate-key rejection, policy examples, policy loader/model tests, `agentlint policy validate`, and `agentlint validate --policy` pre-validation. Policy file errors remain CLI input errors rather than AgentLint diagnostics until policy checks and reports exist.
- Milestone 4 planning decision: core policy enforcement should be an offline pass over structurally valid native traces. The pass should cover tool authorization, approval ordering, explicit data-flow checks, and structural provenance checks while deferring reports, external adapters, runtime gating, full value graphs, semantic contradiction checks, and natural-language data-flow inference. The finalized decision record is `Documents/milestone_4_architecture_decisions.md`.
- Milestone 4 build decision: implemented `agentlint.passes.evaluate_policy(trace, policy)`, added 14 policy diagnostic codes, mapped policy severities to diagnostics, implemented exact-match exception suppression, added B4 fixtures and tests, and changed `agentlint validate --policy` from pre-validation to enforcement after structural validation succeeds.
- Milestone 4 limitation confirmed: data-flow diagnostics are only as complete as explicit `data_flow` edges and source/sink metadata labels. Unknown source/sink labels are ignored in V1, and unannotated natural-language values are not inferred.
- Milestone 4 provenance boundary confirmed: final-answer provenance checks require explicit claim evidence and `provenance` edges, but they do not judge evidence relevance or detect contradictions.
- Milestone 5 architecture finalization: finalized `agentlint check` as the report and CI command, kept `agentlint validate` compatible with Milestone 4, chose a versioned `agentlint.report.v1` report schema, made reports stdout-only, added `--format text|json`, added `--fail-on error|warning|info|never`, and deferred SARIF, GitHub annotations, directory traversal, and report file output. The decision record is `Documents/milestone_5_architecture_decisions.md`.
- Milestone 5 build decision: implemented shared check execution, per-trace results, text and JSON reports, fail-threshold behavior, metadata-only report redaction, multi-trace checking, and `agentlint explain CODE`.
- Milestone 5 privacy boundary confirmed: reports intentionally omit raw user messages, developer instructions, model input/output, tool arguments, tool results, final-answer content, and policy metadata values. The report model includes redaction metadata instead of relying only on terminal formatting discipline.
- Milestone 6 build decision: added a curated fixture manifest as the evidence base for current AgentLint behavior. The corpus now records passing, malformed, structural, policy, redaction, report, and performance-smoke cases, and tests enforce that every current `DiagnosticCode` has at least one stable fixture.
- Milestone 6 report-discipline decision: JSON reports use exact checked-in golden comparisons with path normalization, while text reports use key-line assertions. This preserves a stable automation contract without making human terminal formatting unnecessarily brittle.
- Milestone 6 performance boundary confirmed: the initial performance test is a lightweight pytest smoke test over a representative multi-trace subset with a generous threshold. Benchmark history, percentiles, and comparison tooling remain deferred to the research-evaluation milestone.
- Milestone 7 adapter-order decision: implement OpenTelemetry before OpenAI Agents SDK because it supports zero-cost local demos under the current budget constraint. OpenAI Agents remains the better agent-native follow-on adapter, but live runs should be optional and gated because they use API billing.
- Milestone 7 build decision: implemented `agentlint import opentelemetry INPUT.json --output OUTPUT.json` as a normalization step into native AgentLint IR. Existing structural checks, policy checks, and reports run unchanged after import.
- Milestone 7 semantic boundary confirmed: OpenTelemetry spans require explicit `agentlint.*` attributes for AgentLint-specific concepts such as event type, source/sink labels, data-flow edges, approvals, and claims. Generic spans without those attributes produce adapter warnings rather than inferred diagnostics.
- Milestone 8 planning decision: capture completeness is a per-trace evidence contract, separate from safety diagnostics. Capabilities use `captured`, `partial`, `unavailable`, and `unknown`; undeclared native traces default to unknown, and generic OpenTelemetry makes conservative partial claims rather than treating observed events as proof of exhaustive capture.
- Milestone 8 report decision: completeness must survive normalization in typed trace data and appear in each report run. Adding it changes the machine-readable contract, so implementation will bump JSON reports to `agentlint.report.v2`; policy-aware coverage enforcement remains deferred until rule-to-capability dependencies are defined.
- Milestone 8 build decision: implemented strict capture v1 models, optional typed capture metadata in native IR, conservative OpenTelemetry partial coverage, adapter-result consistency validation, per-run and aggregate report coverage, report schema v2, limited-verification text, updated goldens, and privacy-oriented bounded explanations. Existing policy diagnostics and exit thresholds remain unchanged.
- Milestone 9 planning decision: use the OpenAI Agents SDK's documented tracing processor interface with a versioned local snapshot boundary, then normalize snapshots into existing AgentLint IR. Add explicit IR events for agent runs, handoffs, and guardrails, and split function spans into deterministic call/result events.
- Milestone 9 semantic boundary: native tracing covers agent, generation, function, handoff, and guardrail spans, but it does not provide authoritative general approval decisions, AgentLint provenance/data flow, or `RunResult.final_output`. Report those capabilities conservatively rather than inferring them from successful tools or the last generation.
- Milestone 9 adoption decision: implement one-line in-process capture and an explicitly activated pytest plugin first. Defer generic `sitecustomize` command injection and broad `Runner`/`RunState` monkey-patching until the adapter contract is proven.
- Milestone 9 build decision: implemented snapshot v1, additive agent/handoff/guardrail IR events, deterministic parent-first normalization, function-span call/result splitting, a real SDK processor and capture session, explicit result/approval helpers, CLI import, pytest activation, offline SDK demos, and conservative completeness. Tested against openai-agents 0.18.2.
- Milestone 9 live compatibility finding: OpenAI Agents SDK 0.18.2 Responses runs emitted `response` spans plus framework `custom` containers named `task` and `turn`, rather than only generation spans. The adapter now maps response records to nullable-payload model calls, collapses parent links through task/turn containers, and warns only for unknown custom span names. Reimporting the original live snapshot reduced adapter warnings from seven to zero.
- Milestone 10 planning decision: treat missing policy-required evidence as `not_verifiable`, separate from behavioral diagnostics and invalid input. Compile minimum evidence requirements from configured policy constructs, allow policies to strengthen them with `capture.require`, and fail CLI/pytest for unmet requirements independently of `--fail-on`. Use `partial` as the minimum for represented semantic evidence and reserve `captured` for integrations that can make an exhaustive guarantee.
- Milestone 10 instrumentation boundary: extend the existing OpenAI capture session with explicit approval, source/sink flow, and authoritative final-output records. Do not infer approvals from guardrails or successful tools, and do not attempt implicit Python taint tracking or persist raw source/sink values.
- Milestone 10 build decision: implemented policy capture requirements, deterministic inferred requirements, evidence assessment, `not_verifiable`, report v3, CLI/pytest enforcement, symbolic OpenAI approval/source/sink/final-result records, and a zero-cost SDK customer-support workflow. Passing curated policy fixtures now declare exhaustive fixture capture; undeclared native traces remain unknown and become not verifiable when policy-required evidence is missing.
