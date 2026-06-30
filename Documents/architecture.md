# AgentLint Architecture

AgentLint uses a compiler-inspired pipeline for AI agent execution traces.

```text
raw traces
  -> adapters
  -> schema validation
  -> AgentLint IR
  -> enrichment passes
  -> analysis passes
  -> policy evaluation
  -> diagnostics and reports
```

The product goal is simple: import traces, check policies, and report actionable violations. The implementation uses compiler-style boundaries so input adapters, trace normalization, analysis, and reporting can evolve independently.

## Package Boundaries

```text
src/agentlint/
  cli.py          command-line interface
  version.py      package version metadata
  adapters/       external trace importers
  ir/             AgentLint intermediate representation
  passes/         validation and analysis passes
  policy/         policy loading and evaluation
  diagnostics/    diagnostic models and formatting helpers
  reports/        report emitters
```

Milestone 0 creates these boundaries without implementing trace analysis. The first real IR models arrive in Milestone 1.

## Intermediate Representation Direction

The AgentLint IR should be graph-shaped rather than only sequential. Event order, data dependencies, approval links, and provenance links are distinct relationships over the same execution trace.

This distinction matters because different checks ask different questions:

1. Event order answers what happened when.
2. Data-flow edges answer what influenced what.
3. Approval links answer whether an action was authorized before execution.
4. Provenance links answer whether a final-answer claim is supported by observed evidence.

## Policy Direction

V1 should use a purpose-built YAML policy configuration and built-in AgentLint checks.

OPA/Rego is deferred until after the IR and diagnostics are stable. If added, it should operate over exported AgentLint facts as an optional advanced backend rather than replacing the built-in analysis engine.

## Milestone 0 Non-Goals

Milestone 0 does not implement:

1. Native trace validation.
2. Policy loading.
3. Data-flow analysis.
4. Provenance checking.
5. Report generation.
6. External trace adapters.

Those pieces begin in later milestones.
