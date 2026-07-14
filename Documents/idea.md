# AgentLint

**AgentLint is an offline, deterministic CI linter for recorded AI agent traces.**

AgentLint imports execution logs from OpenAI Agents, LangSmith, OpenTelemetry, and custom JSON, normalizes them into a checkable intermediate representation, and detects unsafe tool calls, private data leaks, and unsupported claims against developer-defined policies.

Its bounded product question is:

> Did this recorded agent run violate a developer-defined policy that can be verified from the captured evidence?

## Why AgentLint?

As AI agents gain access to tools like email, databases, browsers, APIs, and file systems, failures are no longer limited to bad answers. Agents can leak private data, call tools without approval, act on untrusted inputs, or make claims unsupported by the evidence they observed.

Existing observability tools help developers inspect what an agent did. AgentLint focuses on a narrower question:

> Did this agent execution satisfy the policies we care about?

## What AgentLint Checks

AgentLint analyzes agent traces for issues such as:

- Unsafe tool calls
- Private data flowing into public tools
- Untrusted content influencing privileged actions
- Irreversible actions without approval
- Final-answer claims with missing or invalid provenance
- Tool results that do not correspond to valid prior tool calls

## How It Works

AgentLint follows a simple pipeline:

```text
OpenAI Agents trace     ┐
LangSmith trace         │
OpenTelemetry spans     ├── adapters ──> AgentLint IR ──> policy checks ──> CI report
Custom JSON logs        │
MCP tool logs           ┘
```

Under the hood, AgentLint performs policy checking, data-flow analysis, and provenance validation over tool-using agent executions.

In the initial product, those terms have deliberately narrow meanings:

- Tool checking validates explicit tool contracts, arguments, and call/result relationships.
- Approval checking verifies recorded approval or denial evidence linked to an action.
- Data-flow checking follows explicit source, sink, and flow relationships; it is not universal taint tracking.
- Provenance checking validates explicit claim-to-evidence relationships; it is not semantic fact-checking.

If the selected policy requires evidence the trace did not capture, AgentLint reports `not_verifiable` rather than treating missing telemetry as safe behavior.

## Example

```bash
AgentLint validate traces/ --policy AgentLint.yaml
```

Example output:

```text
error[PRIVATE_TO_PUBLIC_SINK]: private Gmail content flowed into web_search.query
error[UNAPPROVED_ACTION]: send_email was called without user approval
warning[UNSUPPORTED_CLAIM]: final answer contains a claim with no supporting evidence
```

## Project Goal

AgentLint does not try to prove that an AI agent is universally safe or correct. Instead, it verifies specific, developer-defined properties over recorded agent executions.

The goal is to make agent safety checks feel like familiar developer tooling:

- ESLint for code quality
- Semgrep for security patterns
- mypy for type errors
- AgentLint for agent traces

## Research Framing

AgentLint explores deterministic offline analysis for tool-using AI agents by translating heterogeneous execution traces into a policy-checkable intermediate representation.

The long-term goal is to make AI agent executions easier to audit, test, and secure before they reach production.

## The simplest explanation

AgentLint is used like this:

> Developers run their agents, collect traces, and let AgentLint lint those traces for policy violations before the agent ships.

AgentLint analyzes recorded AI agent executions. It does not attempt to prove that an agent is universally safe. Instead, it verifies that specific runs satisfy developer-defined policies around tool use, explicit data flow, approvals, and explicit provenance.

## Scope Boundary

AgentLint is a developer test and CI tool. It consumes traces from frameworks and observability systems rather than replacing them.

The initial product does not provide runtime action authorization, action blocking, approval interfaces, identity or role management, trace hosting, compliance dashboards, automatic arbitrary-language taint tracking, or general LLM evaluation. Those concerns may integrate with AgentLint later, but they are not required to establish the trace-linting product.
