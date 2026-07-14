# Architecture Decision: Offline Deterministic Trace Linter

## Status

Accepted for the initial AgentLint product, July 2026.

## Decision

AgentLint is an offline deterministic linter for completed AI agent execution traces.

It answers:

> Did this recorded agent run violate a developer-defined policy that can be verified from the captured evidence?

AgentLint consumes explicit facts and relationships captured by a supported framework, adapter, or focused application annotation. It emits structural and policy diagnostics, capture limitations, and CI outcomes.

## Consequences

1. Missing policy-required evidence produces `not_verifiable`, not a pass or fabricated violation.
2. Tool policies describe trace conformance; AgentLint is not the production authorization authority.
3. Approval checks verify recorded decisions; AgentLint does not initially collect or enforce approvals.
4. Data-flow checks traverse explicit IR edges; they do not infer arbitrary runtime taint.
5. Provenance checks validate explicit claim-to-evidence relationships; they do not judge semantic truth.
6. Diagnostic paths must reference represented event and edge IDs.
7. Runtime gates and probabilistic evaluators, if explored later, remain separate product layers.

## Feature Admission Test

A proposed initial-product feature belongs when it materially improves deterministic policy-regression detection over recorded agent tests.

The proposal must state:

1. Which explicit trace facts it consumes.
2. Which deterministic conclusion it produces.
3. Which capture capability it requires.
4. How insufficient evidence is represented.
5. Whether reports can remain free of raw sensitive values.

Features that authorize actions, collect approvals, infer missing semantic relationships, judge natural-language truth, host traces, or administer compliance are outside this decision.
