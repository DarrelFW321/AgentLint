# AgentLint User Guide

This guide covers installation, framework integration, policy configuration, results,
and advanced trace import.

## Requirements

- Python 3.12 or newer
- pytest, only when using the pytest workflow
- OpenAI Agents SDK 0.18.x for the supported framework integration

Install AgentLint with the OpenAI Agents integration:

```bash
python -m pip install "agentlint-trace[openai-agents]==0.1.0a2"
```

The distribution is named `agentlint-trace`; the command and Python package remain
`agentlint`.

## OpenAI Agents integration

Choose either workflow:

| Workflow | Capture | Check |
| --- | --- | --- |
| Pytest | Automatic during tests | Automatic after the test session |
| Python runner | `instrument()` | `agentlint check-capture` |

### Pytest workflow

Run existing tests with AgentLint enabled:

```bash
pytest --agentlint --agentlint-policy agentlint.yaml
```

This command runs the selected tests, captures their agent traces, checks each trace
with its selected policy, and prints the report in the pytest summary.

Specify pytest test paths as usual:

```bash
pytest tests/test_refunds.py --agentlint --agentlint-policy policies/refunds.yaml
```

### Run artifacts

Every pytest run creates a separate directory:

```text
.agentlint/runs/
  latest.json
  <run-id>/
    manifest.json
    traces/
      <trace-id>.openai-agents.json
    policies/
      <policy-id>-<hash>.yaml
```

The manifest records the pytest node ID, captured trace, and selected policy for each
agent run. Policies are copied into the run directory so the run can be checked later
with the same policy version.

Recheck the latest run:

```bash
agentlint check-run .agentlint/runs/latest.json
```

Or check a specific run:

```bash
agentlint check-run .agentlint/runs/<run-id>/manifest.json
```

Use `--format json` for machine-readable output and `--fail-on` to change the severity
threshold.

### Policy selection

`--agentlint-policy` provides one default policy:

```bash
pytest --agentlint --agentlint-policy policies/default.yaml
```

Select a policy for one test with a marker:

```python
import pytest

@pytest.mark.agentlint(policy="policies/refunds.yaml")
def test_refund_agent():
    ...
```

For a larger suite, create `agentlint.pytest.yaml` in the pytest root:

```yaml
version: 1
default_policy: policies/default.yaml

routes:
  - tests: tests/refunds/**
    policy: policies/refunds.yaml

  - tests:
      - tests/research/**
      - tests/browser/**
    policy: policies/research.yaml
```

AgentLint loads this file automatically. Use `--agentlint-config PATH` to select a
different file.

Policy precedence is:

1. the test's `@pytest.mark.agentlint` policy;
2. the first matching route;
3. `--agentlint-policy`; and
4. `default_policy` from the routing file.

If a captured test has no matching policy, the AgentLint step fails and names the test.

Set a different artifact base directory with:

```bash
pytest --agentlint --agentlint-output build/agentlint-runs
```

### Python runners

Use `instrument()` with a script, custom test runner, or application process:

```python
from agentlint.integrations.openai_agents import instrument

session = instrument(".agentlint/openai-agents")

try:
    # Run ordinary OpenAI Agents SDK workflows.
    ...
finally:
    snapshot_paths = session.close()
```

Snapshots are written to `.agentlint/openai-agents/`. Check all snapshots in the
directory:

```bash
agentlint check-capture .agentlint/openai-agents --policy agentlint.yaml
```

The command accepts a single JSON file or a directory of JSON files. It detects OpenAI
Agents snapshots, OpenTelemetry exports, and native AgentLint traces and returns one
combined report.

#### Inspecting normalized traces

Use the split commands when developing an adapter, inspecting normalized IR, or
keeping the converted trace:

```bash
agentlint import openai-agents \
  .agentlint/openai-agents/<trace-id>.openai-agents.json \
  --output trace.agentlint.json
agentlint check trace.agentlint.json --policy agentlint.yaml
```

The default `export_mode="additive"` preserves the SDK's existing trace processors.
Use local-only capture in an isolated test process when hosted trace export is not
wanted:

```python
session = instrument(
    ".agentlint/openai-agents",
    export_mode="local_only",
)
```

`local_only` replaces the SDK's existing processors in that process.

## Policies

Policies are versioned YAML files. Validate one before using it:

```bash
agentlint policy validate agentlint.yaml
```

### Tool permissions

```yaml
version: 1
policy_id: support_agent

tools:
  lookup_status:
    permission: allowed
    approval: not_required
    risk: low

  issue_refund:
    permission: allowed
    approval: required
    risk: high
    arguments:
      ticket_id:
        required: true
        allowed_types: [string]

rules:
  unknown_tool: error
  denied_tool_call: error
  disallowed_tool_argument: error
  missing_approval: error
```

Only enable rules that matter to the agent.

### Approval decisions

Record application approval inside the active function-tool span:

```python
session.record_current_approval(decision="approved")
```

Valid decisions are `approved` and `denied`.

### Policy-declared data boundaries

Classify tool results and arguments once in policy:

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

rules:
  private_to_public_sink: error
```

Boundary declarations label captured tool results and arguments. Flow checks also
need a recorded relationship between the source and destination.

Record application-level flow with the integration helpers:

```python
source_event = session.record_current_source(
    name="customer_profile",
    sensitivity="private",
    trust="trusted",
)

# Inside the destination function-tool span:
session.record_current_sink(
    name="public_search",
    source_events=[source_event],
    visibility="public",
)
```

### Capture requirements

Policies may require minimum evidence coverage:

```yaml
capture:
  require:
    tool_calls: partial
    tool_arguments: partial
    approvals: partial
```

AgentLint also derives requirements from active rules. Missing required evidence
produces a `not_verifiable` result.

## Results

A checked trace has one of four outcomes:

| Outcome | Meaning |
| --- | --- |
| `passed` | No active policy violation was found and required evidence was available. |
| `failed` | One or more active policy rules were violated. |
| `invalid` | The trace or policy failed structural validation. |
| `not_verifiable` | The trace lacked evidence required by the active policy. |

`invalid` and `not_verifiable` return nonzero exit codes independently of the
diagnostic severity threshold.

### Diagnostic areas

| Area | Checks |
| --- | --- |
| Tools | `UNKNOWN_TOOL`, `DENIED_TOOL_CALL`, `DISALLOWED_TOOL_ARGUMENT` |
| Approval | `MISSING_APPROVAL`, `APPROVAL_AFTER_ACTION`, `ACTION_AFTER_DENIAL`, `APPROVAL_MISMATCH` |
| Data flow | `PRIVATE_TO_PUBLIC_SINK`, `SECRET_EXPOSURE`, `UNTRUSTED_TO_PRIVILEGED_ACTION`, `SENSITIVE_FINAL_ANSWER` |
| Provenance | `UNSUPPORTED_CLAIM`, `INVALID_PROVENANCE_REFERENCE`, `EVIDENCE_AFTER_CLAIM` |

Explain any diagnostic:

```bash
agentlint explain PRIVATE_TO_PUBLIC_SINK
```

Reports exclude raw trace payload values. Diagnostics identify relevant events and
show recorded relationships between them.

## Checking recorded traces

Check native AgentLint traces directly:

```bash
agentlint check trace.agentlint.json --policy agentlint.yaml
agentlint check traces/*.agentlint.json --policy agentlint.yaml --format json
```

Control the diagnostic severity threshold:

```bash
agentlint check trace.agentlint.json \
  --policy agentlint.yaml \
  --fail-on warning
```

Supported thresholds are `error`, `warning`, `info`, and `never`.

## OpenTelemetry compatibility

OpenTelemetry import is an advanced fallback for systems that already export
OTLP-style JSON:

```bash
agentlint check-capture traces/ --policy agentlint.yaml
```

To inspect the normalized trace, use the split commands:

```bash
agentlint import opentelemetry trace.json --output trace.agentlint.json
agentlint check trace.agentlint.json --policy agentlint.yaml
```

For most projects, use a supported AgentLint integration. OpenTelemetry import is for
existing tracing pipelines and may require additional AgentLint metadata.

## CI

The pytest command can run directly in an existing CI job:

```bash
pytest --agentlint --agentlint-policy agentlint.yaml
```
