# AgentLint

[![CI](https://github.com/DarrelFW321/AgentLint/actions/workflows/ci.yml/badge.svg)](https://github.com/DarrelFW321/AgentLint/actions/workflows/ci.yml)
[![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-blue.svg)](https://www.python.org/downloads/)

AgentLint catches unsafe agent behavior before it reaches production.

It records agent test runs and checks them against your policy for:

- unauthorized or unknown tool calls;
- destructive actions without approval;
- private data flowing to public destinations;
- untrusted data influencing privileged actions; and
- final-answer claims without recorded evidence.

AgentLint is deterministic and runs locally. It evaluates the evidence in a completed
trace; it does not send traces to a model or external analysis service.

## Quick start

AgentLint's supported workflow is:

```text
define a policy -> install the framework integration -> run your existing tests
```

### 1. Install

AgentLint currently requires Python 3.12 or newer. Install the project and the OpenAI
Agents integration from source:

```bash
git clone https://github.com/DarrelFW321/AgentLint.git
cd AgentLint
python -m pip install -e ".[openai-agents]"
```

### 2. Define a policy

Create `agentlint.yaml`:

```yaml
version: 1
policy_id: customer_support

tools:
  lookup_status:
    permission: allowed
    approval: not_required
    risk: low

  issue_refund:
    permission: allowed
    approval: not_required
    risk: high
    arguments:
      ticket_id:
        required: true
        allowed_types: [string]

rules:
  unknown_tool: error
  denied_tool_call: error
  disallowed_tool_argument: error
```

Only configure the rules that matter to your agent. AgentLint derives the evidence
requirements from the active policy and reports `not_verifiable` when the trace does
not contain enough evidence to reach a trustworthy result.

Validate the policy at any time:

```bash
agentlint policy validate agentlint.yaml
```

### 3. Run your tests

For an OpenAI Agents SDK project using pytest:

```bash
pytest --agentlint --agentlint-policy agentlint.yaml
```

The plugin captures OpenAI Agents traces for the test session, evaluates them locally,
prints diagnostics, and returns a nonzero exit code for violations, invalid traces,
missing capture, or unverifiable policy requirements.

No collector, hosted tracing backend, custom trace format, or per-tool wrapper is
required.

Tool permission and argument checks work from framework capture plus policy alone.
Checks for application concepts the framework cannot observe, such as an approval
decision, need one focused semantic record at that boundary.

## In-process integration

Applications that do not use the pytest plugin can install capture once:

```python
from agentlint.integrations.openai_agents import instrument

session = instrument(".agentlint/openai-agents")

try:
    # Run ordinary OpenAI Agents SDK workflows.
    ...
finally:
    session.close()
```

The default `additive` mode preserves the SDK's existing trace processors. In an
isolated test process, `export_mode="local_only"` replaces them so traces remain
local:

```python
session = instrument(
    ".agentlint/openai-agents",
    export_mode="local_only",
)
```

Use `local_only` deliberately: replacing the SDK processors also disables any
existing hosted OpenAI trace export in that process.

## Policy-declared boundaries

Classify a tool result or argument once in policy instead of annotating every call:

```yaml
tools:
  customer_db.lookup:
    permission: allowed
    result:
      source: customer_profile
      sensitivity: private
      trust: trusted

  web_search:
    permission: allowed
    arguments:
      query:
        sink: public_search
        visibility: public
```

AgentLint applies these labels to captured calls and results. A data-flow rule still
requires an explicit recorded relationship showing that a source influenced a sink.
AgentLint never invents flow from event order or matching text.

Framework tracing cannot always observe authoritative approval decisions or
application-level data flow. For those cases, the OpenAI integration provides focused
semantic helpers such as `record_current_approval`, `record_current_source`, and
`record_current_sink`. They record labels and relationships without storing the
sensitive values themselves.

For example, require approval in policy:

```yaml
tools:
  issue_refund:
    permission: allowed
    approval: required
    risk: high

rules:
  missing_approval: error
```

Then record the application's decision inside the active function-tool span:

```python
session.record_current_approval(decision="approved")
```

## Diagnostics

AgentLint produces compiler-style failures with stable codes and evidence paths:

```text
error[PRIVATE_TO_PUBLIC_SINK]

Private data from customer_profile flowed into web_search.query.

Path:
customer_db.lookup.result
-> web_search.query
```

Core checks include:

| Area | Checks |
| --- | --- |
| Tools | `UNKNOWN_TOOL`, `DENIED_TOOL_CALL`, `DISALLOWED_TOOL_ARGUMENT` |
| Approval | `MISSING_APPROVAL`, `APPROVAL_AFTER_ACTION`, `ACTION_AFTER_DENIAL`, `APPROVAL_MISMATCH` |
| Data flow | `PRIVATE_TO_PUBLIC_SINK`, `SECRET_EXPOSURE`, `UNTRUSTED_TO_PRIVILEGED_ACTION`, `SENSITIVE_FINAL_ANSWER` |
| Provenance | `UNSUPPORTED_CLAIM`, `INVALID_PROVENANCE_REFERENCE`, `EVIDENCE_AFTER_CLAIM` |

Run `agentlint explain CODE` for a rule description and remediation guidance.

## Checking recorded traces

The CLI can also evaluate existing native AgentLint traces:

```bash
agentlint check trace.agentlint.json --policy agentlint.yaml
agentlint check traces/*.agentlint.json --policy agentlint.yaml --format json
```

Use `--fail-on error|warning|info|never` to control the diagnostic severity threshold.
Invalid and `not_verifiable` traces fail independently of that threshold.

Reports redact raw payload values by default and include:

- the policy result for each trace;
- capture completeness and unmet evidence requirements;
- stable diagnostic codes;
- related event identifiers and explicit evidence paths; and
- aggregate counts suitable for CI.

## Advanced: OpenTelemetry import

OpenTelemetry support remains available as a compatibility path for systems that
already export OTLP-style JSON:

```bash
agentlint import opentelemetry trace.json --output trace.agentlint.json
agentlint check trace.agentlint.json --policy agentlint.yaml
```

This is not the recommended onboarding path. Generic OpenTelemetry spans do not carry
enough agent-policy meaning on their own, so precise checks require explicit
`agentlint.*` semantic attributes. First-class framework integrations provide a
better consumer experience.

## What AgentLint guarantees

AgentLint answers:

> Did this recorded agent run violate a developer-defined policy that can be verified
> from the captured evidence?

It does not authorize production actions, collect approvals, reconstruct arbitrary
program data flow, judge the semantic truth of natural-language answers, or prove that
an agent is universally safe. Missing evidence is reported explicitly rather than
treated as a pass.

## Development

```bash
python -m pip install -e ".[dev,otel-demo,openai-agents]"
python -m ruff format --check src tests
python -m ruff check src tests
python -m pytest -q
```

The test suite is offline and zero-cost by default. API-backed examples require
`OPENAI_API_KEY` and are excluded from normal test runs.

## License

AgentLint is available under the MIT License.
