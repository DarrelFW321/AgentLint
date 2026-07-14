# Zero-Configuration and Adoption Requirements

## Product principle

AgentLint must minimize the work required to capture agent executions.

Users should be expected to define their organization’s policies, but they should not be expected to build tracing infrastructure before AgentLint becomes useful.

For supported frameworks, AgentLint must automatically capture the agent behavior already exposed by the framework.

The product target is:

**Zero-configuration capture where technically possible, one-line setup where necessary, and explicit annotations only for application-specific policy meaning.**

This adoption goal does not expand the product scope. Instrumentation captures evidence for offline deterministic trace linting. It does not initially authorize actions, block tool calls, collect approvals, infer arbitrary program data flow, or judge the semantic truth of final answers. When automatic capture cannot establish policy-required semantics, the integration must report incomplete coverage rather than infer them.

---

## Required initial experience

For a supported framework, the preferred workflow is either explicit pytest activation:

```bash
pip install "agentlint[openai-agents]"

pytest --agentlint --agentlint-policy agentlint.yaml
```

or one-line in-process capture:

```python
from agentlint.integrations.openai_agents import instrument

session = instrument()
# Run ordinary agent scenarios.
session.close()
```

AgentLint should automatically:

1. Detect the supported agent framework.
2. Register the appropriate framework-native processor when explicitly activated.
3. Capture agent runs during the test or application process.
4. Associate traces with the relevant tests.
5. Convert the captured events into AgentLint IR.
6. Apply the configured policy.
7. Produce diagnostics and a CI exit code.
8. Flush and shut down the activated capture components.

The user should not need to:

- Configure an OpenTelemetry Collector
- Configure an OTLP exporter
- Export trace files manually
- Add AgentLint-specific span attributes
- Construct AgentLint IR
- Wrap every function tool
- Change every test case
- Manage a separate trace-storage service

---

## Acceptable setup levels

AgentLint should support three clearly defined setup levels.

### Level 1: Automatic framework capture

For officially supported frameworks, AgentLint captures the framework’s native execution events automatically.

Expected automatic information includes:

- Agent runs
- Model calls
- Tool calls
- Tool names
- Tool arguments when available
- Tool results when available
- Errors
- Retries
- Parent-child execution structure
- Final output
- Framework-native guardrail events

The user should only need to install the framework adapter and run AgentLint around their existing test command.

Target experience:

```bash
agentlint check --framework openai --command "pytest"
```

Framework detection may make the explicit `--framework` option unnecessary.

---

### Level 2: One-line bootstrap

Some frameworks or application structures may prevent automatic activation.

In those cases, AgentLint may require one initialization line in a central application or test setup file:

```python
from agentlint_openai import instrument

instrument()
```

This initialization must:

- Register the framework trace processor
- Capture supported agent events
- Require no manual span creation
- Require no OpenTelemetry configuration
- Apply globally to agent runs in the process

The user should add this once, not to every agent, tool, or test.

---

### Level 3: Optional semantic annotations

Annotations are permitted only for information that cannot be derived safely from framework events or policy configuration.

Examples include:

- A data source contains private information
- A retrieved source is untrusted
- A particular value belongs to a customer tenant
- An approval authorizes a specific action
- A final claim relies on a specific piece of evidence

Example:

```python
with agentlint.source(
    "customer_profile",
    sensitivity="private",
):
    customer = load_customer()
```

These annotations must be optional for basic AgentLint functionality.

A user who does not add semantic annotations should still receive useful checks covering:

- Unknown tools
- Prohibited tools
- Missing tool arguments
- Tool argument constraints
- Duplicate actions
- Tool failures
- Unsafe retries
- Structural trace errors
- Framework-native approvals, when available

AgentLint must clearly identify checks that are unavailable because semantic metadata is missing.

---

## Policy configuration versus instrumentation

AgentLint must distinguish between policy setup and trace instrumentation.

Users are reasonably expected to define rules such as:

```yaml
tools:
  issue_refund:
    approval: required
    risk: critical
```

Users should not also need to instrument every invocation of `issue_refund` manually when the framework already exposes that function-tool call.

The adapter should combine:

- Tool execution observed from the framework
- Safety requirements declared in the policy
- Explicit semantic metadata only where unavoidable

---

## Framework adapter responsibilities

An official adapter must do more than import an exported trace file.

It should provide an end-to-end capture experience for the supported framework.

An adapter is responsible for:

- Detecting or initializing native tracing
- Registering trace processors or callbacks
- Capturing traces in memory or temporary local storage
- Mapping native events into AgentLint IR
- Associating events with the correct run and test
- Redacting sensitive data
- Reporting unsupported semantics
- Cleaning up after the command finishes

The adapter must document a capability matrix:

| Capability           |           Automatic | Requires policy | Requires annotation | Unsupported |
| -------------------- | ------------------: | --------------: | ------------------: | ----------: |
| Tool name            |                 Yes |              No |                  No |          No |
| Tool arguments       |             Usually |              No |                  No |   Sometimes |
| Tool permission      |                  No |             Yes |                  No |          No |
| Approval requirement |                  No |             Yes |                  No |          No |
| Approval event       | Framework-dependent |              No |           Sometimes |   Sometimes |
| Sensitive source     |                  No |       Sometimes |             Usually |          No |
| Parent relationships |             Usually |              No |                  No |   Sometimes |
| Arbitrary data flow  |                  No |              No |                 Yes |   Sometimes |
| Claim provenance     |                  No |              No |                 Yes |   Sometimes |

AgentLint must not imply that unsupported or missing semantics were verified.

---

## Command wrapping

AgentLint should be capable of launching an existing command and activating capture around it.

Example:

```bash
agentlint check --command "pytest tests/agents"
```

The command wrapper should:

1. Create an isolated capture session.
2. Generate a session identifier.
3. Configure the child process for the selected framework adapter.
4. Launch the command without changing its normal behavior.
5. Capture emitted traces.
6. Wait for all traces to flush.
7. Check the traces.
8. Return a combined test and policy result.

Where supported, AgentLint may activate instrumentation through:

- Framework-native trace processors
- Pytest plugins
- Python startup hooks
- Environment variables
- Import hooks
- OpenTelemetry auto-instrumentation
- Controlled monkey patching

Framework-native APIs should be preferred over monkey patching.

---

## Pytest integration

The Python MVP should include a pytest plugin.

The plugin should activate automatically when the relevant AgentLint package is installed, or through one explicit configuration entry.

Preferred experience:

```bash
pytest --agentlint
```

or:

```bash
agentlint check --command "pytest"
```

The plugin should:

- Start trace capture at test-session startup
- Associate traces with pytest node identifiers
- Flush traces after each relevant test
- Attach AgentLint diagnostics to failed tests
- Avoid modifying ordinary tests
- Continue to work with async tests
- Respect test parallelization where possible

A test should not require AgentLint-specific code merely to have its agent execution captured.

---

## OpenTelemetry behavior

OpenTelemetry is an implementation option, not a required user workflow.

When AgentLint uses OpenTelemetry internally, it should hide:

- Collector startup
- OTLP endpoint configuration
- Exporter configuration
- Temporary storage
- Span processing
- Shutdown and flushing

Users who already operate OpenTelemetry should be able to connect their existing telemetry, but new users should not need prior OpenTelemetry knowledge.

The generic OpenTelemetry importer may remain available for advanced and unsupported-framework use cases.

---

## Unsupported frameworks

AgentLint cannot promise automatic capture for arbitrary applications.

For unsupported frameworks, the CLI should provide an explicit result:

```text
AgentLint could not detect a supported agent framework.

Available options:
- Install an official framework adapter
- Import an existing OpenTelemetry trace
- Use the AgentLint tool wrapper
- Emit native AgentLint events
```

It must not silently run and claim that no violations were found when no meaningful trace was captured.

---

## Capture completeness

Every report must include a capture-completeness summary.

Finalized planning decision: capture completeness is a per-trace evidence contract, separate from policy diagnostics. Its states are `captured`, `partial`, `unavailable`, and `unknown`; absence of a trustworthy declaration means unknown, not captured. The implementation contract, report v2 migration, OpenTelemetry baseline, tests, and deferred enforcement behavior are defined in `Documents/milestone_8_capture_completeness_implementation_plan.md`.

Example:

```text
Capture coverage

Agent runs: captured
Model calls: captured
Tool calls: captured
Tool results: captured
Approvals: unavailable
Data flow: partial
Claim provenance: unavailable
```

A passing report with incomplete capture should state:

```text
Policy checks passed for the behavior represented in the trace.
Approval and provenance coverage were not available.
```

---

## Failure behavior

AgentLint should fail clearly when:

- No agent traces were captured
- An expected adapter was not activated
- The framework version is unsupported
- The child process disabled tracing
- Captured traces are incomplete for mandatory policy checks
- Trace flushing failed
- The test process exited before traces could be collected

Milestone 10 compares capture against policy-specific minimum evidence requirements. Missing required evidence is not a behavioral violation and is not represented as one. It produces a `not_verifiable` trace outcome and a nonzero CI result independent of diagnostic severity.

Example policy:

```yaml
capture:
  require:
    tool_calls: partial
    approvals: partial
    provenance: captured
```

Allowed minimums are `partial` and `captured`. Explicit requirements may strengthen requirements inferred from configured policy constructs but may not weaken evidence that a check needs. A partial observation validates represented annotations; it does not prove exhaustive application-wide capture.

---

## MVP framework scope

The first release should support only one framework deeply rather than several frameworks superficially.

Recommended initial scope:

- Python
- OpenAI Agents SDK
- Pytest
- Function tools
- Native trace processor integration
- Automatic capture of agent, model, tool, and final-output events
- One explicit AgentLint helper for approval recording only when the framework does not expose approval decisions

The MVP should not claim generic OpenTelemetry support is equivalent to a first-class framework adapter.

---

## Adoption success criteria

The capture experience is successful when a new user can:

1. Install AgentLint and the supported adapter.
2. Write a policy identifying a sensitive tool.
3. Run their existing agent tests without rewriting them.
4. See AgentLint capture the agent’s tool calls.
5. Receive a policy finding.
6. Add AgentLint to CI in under 15 minutes.

The expected setup should involve:

- Zero changes to ordinary tests
- Zero manual OpenTelemetry configuration
- Zero manually authored AgentLint trace events
- No more than one central initialization change when automatic activation is impossible

---

## Product promise

For supported frameworks:

**Install the adapter, define your policy, and run your existing tests. AgentLint captures and checks the agent execution automatically.**

For advanced semantic checks:

**Annotate only the sensitive boundaries that the framework cannot understand on its own.**
