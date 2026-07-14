# AgentLint Requirements Specification

## 1. Overview

AgentLint is an offline, deterministic CI-oriented policy checker for recorded AI agent execution traces.

It analyzes completed agent runs and checks whether the represented behavior satisfies developer-defined policies around tool use, explicit data flow, recorded approvals, and explicit final-answer provenance.

AgentLint does not attempt to prove that an agent is universally safe or correct. Instead, it verifies specific properties over concrete agent executions.

## 2. Product Positioning

**Main tagline:**

> AgentLint is a CI linter for AI agent traces.

**One-sentence description:**

> AgentLint imports execution logs from agent frameworks and observability systems, normalizes them into a checkable intermediate representation, and detects unsafe tool calls, private data leaks, and unsupported claims against developer-defined policies.

**Technical description:**

> AgentLint performs policy checking, data-flow analysis, and provenance validation over tool-using AI agent executions.

## 3. Goals

AgentLint should:

1. Analyze AI agent execution traces.
2. Normalize heterogeneous trace formats into a common internal representation.
3. Allow developers to define safety and correctness policies.
4. Detect violations involving tool calls, data flow, approvals, and provenance.
5. Produce clear, actionable reports suitable for local development and CI workflows.
6. Refuse to report a pass when evidence required by the selected policy was not captured.

## 4. Non-Goals

AgentLint is not intended to:

1. Prove that an agent is safe for all possible future executions.
2. Replace agent observability platforms.
3. Replace human review for high-risk decisions.
4. Judge overall answer quality in a subjective way.
5. Act as a general-purpose LLM evaluation platform.
6. Require all agent frameworks to adopt a new trace standard.
7. Authorize or block production actions in the initial product.
8. Provide approval user interfaces, identity management, or role management.
9. Replace trace storage, observability, or security-operation platforms.
10. Infer arbitrary data flow through Python, model reasoning, subprocesses, or external systems.
11. Semantically prove that natural-language claims are true or supported.
12. Serve as an enterprise compliance or policy-administration suite.

## 4.1 Scope Contract

AgentLint answers:

> Did this recorded agent run violate a developer-defined policy that can be verified from the captured evidence?

The initial product operates over explicit trace evidence. It may use framework-native relationships, adapter-provided semantics, or focused application annotations. Missing evidence is represented through capture completeness and `not_verifiable`; it is never silently interpreted as safe behavior.

Authorization systems may emit decisions that AgentLint later verifies. Approval systems may emit grants or denials that AgentLint correlates with actions. AgentLint does not need to become either system to lint whether a completed trace respected their evidence.

## 5. Target Users

AgentLint is designed for:

1. AI agent developers.
2. AI platform and infrastructure teams.
3. Security engineers reviewing agent behavior.
4. Teams deploying internal enterprise agents.
5. Teams building customer-support, operations, research, coding, or automation agents.
6. Researchers studying agent safety, provenance, and tool-use behavior.

## 6. Primary Use Cases

### 6.1 Local Development

A developer runs an agent on test scenarios, saves the resulting execution traces, and uses AgentLint to identify policy violations before committing changes.

Example failures:

- Private data flows into a public tool.
- A sensitive tool is called without approval.
- A final answer contains a claim with no supporting evidence.
- A tool result references an invalid or missing tool call.

### 6.2 Continuous Integration

A team includes AgentLint in its CI workflow. When a pull request changes prompts, tools, orchestration logic, policies, or agent code, test traces are generated and checked automatically.

The CI job should fail when AgentLint finds policy violations above the configured severity threshold.

### 6.3 Security Review

A security engineer reviews AgentLint reports to understand whether an agent execution violated data-handling, tool-use, or approval policies.

Reports should make it clear:

- What happened.
- Which policy was violated.
- Which trace events were involved.
- Why the behavior was unsafe.
- How the developer might fix it.

### 6.4 Runtime Gating (Deferred Product Layer)

Runtime gating is not part of the initial trace-linting product. A later, separately scoped product layer may analyze partial traces and block, allow, warn, or escalate risky tool calls before they execute. It should reuse normalized policy facts without changing the offline linter's evidence claims.

Example runtime decisions:

- Block sending an email if the body depends on untrusted content.
- Require approval before issuing a refund.
- Prevent private data from being sent to a public API.

## 7. Inputs

AgentLint should accept execution traces from multiple sources.

Supported or planned input categories include:

1. Native AgentLint trace format.
2. OpenTelemetry-style spans.
3. Agent framework traces.
4. Observability platform exports.
5. Custom JSON logs.
6. MCP-style tool call logs, where available.

AgentLint should not assume a universal external trace standard. Instead, it should use adapters to translate different input formats into a common internal representation.

## 8. Intermediate Representation

AgentLint should normalize imported traces into a policy-checkable intermediate representation.

The intermediate representation should represent:

1. User messages.
2. System or developer instructions.
3. Model calls.
4. Tool calls.
5. Tool results.
6. Human approvals or denials.
7. Final answers.
8. Data dependencies between events.
9. Provenance links between claims and supporting observations.
10. Sensitivity labels for data values where available.
11. Trust labels for inputs, such as trusted, private, secret, public, or untrusted.

The representation should allow AgentLint to reason about the order of events, dependencies between events, and policy-relevant metadata.

## 9. Policy System

AgentLint should allow developers to define policies for their specific agent.

Policies should support:

1. Data sensitivity labels.
2. Trusted and untrusted sources.
3. Public and private sinks.
4. Tool permission rules.
5. Approval requirements.
6. Provenance requirements.
7. Severity levels for violations.
8. Project-specific exceptions.
9. Preset policy templates for common agent types.

AgentLint should define the policy language and built-in checks. Developers should define the project-specific policies.

## 10. Core Functional Requirements

### 10.1 Trace Import

AgentLint must be able to import supported trace formats.

It should:

1. Parse trace inputs.
2. Validate that required fields are present.
3. Preserve relevant event ordering.
4. Preserve tool names, arguments, results, and metadata.
5. Preserve references between calls and results where available.
6. Report unsupported or ambiguous input fields clearly.
7. Record which policy-relevant capabilities were captured, partially captured, unavailable, or unknown.

### 10.2 Trace Normalization

AgentLint must convert imported traces into its internal representation.

It should:

1. Assign stable identifiers to trace events.
2. Normalize event types.
3. Normalize tool call and tool result relationships.
4. Normalize timestamps or event ordering.
5. Normalize data dependency information where available.
6. Preserve raw references for debugging.

Policy-declared tool-result sources and tool-argument sinks may enrich observed events with symbolic labels. Normalization must not infer a data-flow relationship merely because a source and sink boundary were both observed.

### 10.3 Structural Validation

AgentLint must validate basic trace correctness.

It should detect:

1. Duplicate event identifiers.
2. Missing event references.
3. Tool results without matching tool calls.
4. Tool calls with missing arguments.
5. Invalid event ordering.
6. Final answers that reference nonexistent evidence.
7. Malformed or incomplete traces.

### 10.4 Tool Policy Checking

AgentLint must check whether tool calls satisfy developer-defined policies.

It should detect:

1. Tool calls denied by the trace policy.
2. High-risk tools called without approval.
3. Tool calls using disallowed input types.
4. Tool calls made after explicit denial.
5. Tool calls that violate configured constraints.
6. Unknown tools not covered by policy.

### 10.5 Data-Flow Checking

AgentLint must check whether data flows violate policy.

It should detect:

1. Private data flowing into public tools.
2. Secret data entering model-visible context.
3. Untrusted content influencing privileged actions.
4. Sensitive data appearing in final answers when disallowed.
5. Data from denied or unsafe sources influencing later actions.
6. Missing sensitivity labels for policy-relevant data.

### 10.6 Provenance Checking

AgentLint must check whether final answers and important claims are supported by prior observations.

It should detect:

1. Claims with no supporting evidence.
2. Claims supported by nonexistent trace events.
3. Claims supported by irrelevant or incompatible evidence.
4. Citations or provenance links that point to invalid events.
5. Final answers that contradict tool results where this can be determined.

For the initial version, provenance checking relies on explicit provenance annotations or structured claim-to-evidence mappings. AgentLint validates existence, order, and declared relationships; it does not determine whether evidence semantically proves a natural-language claim. Any future probabilistic or domain-specific evaluator must be presented as a separate capability.

### 10.7 Approval Checking

AgentLint must check approval requirements for sensitive actions.

It should detect:

1. Actions requiring approval that were executed without approval.
2. Actions executed after approval was denied.
3. Approvals that do not match the action taken.
4. Approvals that occurred after the action rather than before it.
5. Approvals missing required metadata.

### 10.8 Reporting

AgentLint must produce clear reports.

Reports should include:

1. A summary of passed, failed, and warning checks.
2. A list of violations.
3. Violation severity.
4. Violation code.
5. Human-readable explanation.
6. Relevant trace events.
7. Relevant policy rule.
8. Suggested remediation where possible.
9. Per-trace capture completeness for policy-relevant evidence.
10. A clear limitation statement when checks pass over incomplete capture.

Reports should be usable by both humans and automated systems.

Capture completeness must remain separate from policy violations. It describes what the trace source observed and preserved, not whether the represented behavior was safe. Missing declarations must be reported as unknown rather than assumed complete.

### 10.9 CI Integration

AgentLint should support CI workflows.

It should:

1. Return a pass/fail result based on configured severity thresholds.
2. Produce machine-readable reports.
3. Produce human-readable summaries.
4. Support checking multiple traces in one run.
5. Allow teams to treat warnings and errors differently.
6. Make failures actionable enough for pull request review.

### 10.10 Policy Presets

AgentLint should provide policy presets for common agent categories.

Potential presets include:

1. Customer-support agents.
2. Research agents.
3. Coding agents.
4. Enterprise internal assistants.
5. Data-analysis agents.
6. Browser-automation agents.

Presets should be customizable and should not prevent teams from defining their own policies.

## 11. Example Policy Concepts

AgentLint policies should be able to express rules such as:

1. Private data must not flow into public tools.
2. Secret data must never appear in final answers.
3. Web content is untrusted by default.
4. Untrusted content must not directly influence privileged tool calls.
5. Email sending requires approval.
6. Refund creation requires approval.
7. Database deletion requires approval.
8. Final customer-facing claims require supporting evidence.
9. Unknown tools are denied by default.
10. Tool results must correspond to valid prior tool calls.

## 12. Example Violation Categories

AgentLint should classify violations into categories such as:

1. Structural trace error.
2. Trace-policy-denied tool call.
3. Missing approval.
4. Private-to-public data flow.
5. Secret exposure.
6. Untrusted-to-privileged influence.
7. Unsupported claim.
8. Invalid provenance reference.
9. Unknown tool.
10. Missing policy coverage.
11. Policy result not verifiable because required evidence was unavailable or incomplete.

## 13. Output Requirements

AgentLint should support multiple output formats.

At minimum, it should support:

1. Human-readable terminal or text output.
2. Structured machine-readable output.
3. Summary output for CI systems.

Future versions may support:

1. HTML reports.
2. Pull request annotations.
3. Security report formats.
4. Visual trace graphs.

## 14. Runtime Requirements (Deferred)

The initial version is limited to offline analysis of recorded traces. The following items are deferred and are not initial product requirements.

Future runtime support should allow AgentLint to:

1. Analyze partial traces.
2. Evaluate pending tool calls.
3. Return allow, block, warn, or require-approval decisions.
4. Explain why an action was blocked.
5. Preserve decision logs for later auditing.

## 15. Extensibility Requirements

AgentLint should be designed to support:

1. New trace adapters.
2. New policy rules.
3. New violation types.
4. New report formats.
5. New data labels.
6. Project-specific checks.
7. Integration with different agent frameworks.

The design should avoid coupling the checker to a single agent framework or observability platform.

## 16. Security and Privacy Requirements

AgentLint should handle sensitive trace data carefully.

It should:

1. Avoid unnecessarily exposing raw private data in reports.
2. Redact sensitive values where appropriate.
3. Allow reports to reference sensitive values symbolically.
4. Avoid sending trace data to external services by default.
5. Make any optional external analysis explicit.
6. Preserve enough metadata for debugging without leaking secrets.

## 17. Usability Requirements

AgentLint should be easy for developers to adopt.

It should:

1. Provide clear onboarding.
2. Include example traces.
3. Include example policies.
4. Provide useful defaults.
5. Explain violations clearly.
6. Avoid requiring users to define every rule from scratch.
7. Allow gradual adoption with warnings before strict enforcement.

## 18. Performance Requirements

AgentLint should be efficient enough for local and CI usage.

It should:

1. Analyze typical test trace sets quickly enough for pull request workflows.
2. Scale to multiple traces in one analysis session.
3. Avoid excessive memory use on large traces.
4. Provide useful error messages even when traces are large or partially malformed.

## 19. Version 1 Scope

The first version should include:

1. A native trace format.
2. At least one external trace adapter.
3. A common intermediate representation.
4. Structural trace validation.
5. Basic tool policy checking.
6. Basic data-flow checking.
7. Basic approval checking.
8. Basic provenance checking using explicit annotations.
9. Human-readable reports.
10. Machine-readable reports.
11. CI-compatible pass/fail behavior.
12. Example policies and example traces.
13. Capture-completeness reporting and a `not_verifiable` result when policy-required evidence is insufficient.

Version 1 data-flow and provenance checks operate only on explicit represented relationships. Version 1 approval checks verify recorded decisions; they do not collect or enforce approvals. Version 1 tool permissions are trace conformance rules, not a complete contextual authorization system.

## 20. Future Scope

Future versions may include:

1. More trace adapters.
2. Runtime policy gating.
3. Advanced semantic provenance checking.
4. Visual trace exploration.
5. Trace diffing across agent versions.
6. Policy recommendation tools.
7. Automatic policy coverage analysis.
8. Integration with observability platforms.
9. Pull request annotations.
10. Benchmark suites for common agent failure modes.

Future items are candidates, not commitments. Runtime enforcement, semantic evaluation, dashboards, and compliance workflows must remain separable from the deterministic offline linter and should be added only in response to validated user demand.

## 21. Success Criteria

AgentLint should be considered successful if it can:

1. Import realistic agent traces.
2. Normalize them into a consistent internal representation.
3. Detect meaningful policy violations.
4. Produce actionable reports.
5. Run in a CI workflow.
6. Demonstrate value on realistic agent failure scenarios.
7. Clearly communicate its limitations.
8. Support extension to additional frameworks and policies.
9. Clearly distinguish a clean policy result from complete execution capture.
10. Refuse to report a policy pass when evidence required by that policy is below its configured minimum.

## 22. Core Principle

AgentLint should make agent safety checks feel like familiar developer tooling.

It should not promise universal agent correctness. It should help teams catch concrete, policy-relevant failures in real agent executions before those failures reach production.
