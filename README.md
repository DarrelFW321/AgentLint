# AgentLint

[![CI](https://github.com/DarrelFW321/AgentLint/actions/workflows/ci.yml/badge.svg)](https://github.com/DarrelFW321/AgentLint/actions/workflows/ci.yml)
[![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-blue.svg)](https://www.python.org/downloads/)

AgentLint checks recorded agent runs against project policies. Use it in tests and CI
to catch unsafe tool use, missing approvals, sensitive-data flows, and unsupported
claims.

## Integrations

| Integration | Setup | Use case |
| --- | --- | --- |
| OpenAI Agents SDK | pytest plugin or one-line `instrument()` call | Recommended |
| OpenTelemetry | Import OTLP-style JSON | Existing tracing pipelines |

### OpenAI Agents SDK

The pytest integration captures existing tests without code changes. The quick start
below shows the complete command.

For scripts or another test runner, add capture once at process startup:

```python
from agentlint.integrations.openai_agents import instrument

session = instrument(".agentlint/openai-agents")

# Run the agent.

session.close()
```

No per-tool wrappers or tracing backend are required. See the
[integration guide](Documents/user-guide.md#openai-agents-integration) for local-only
capture and approval or data-flow helpers.

### OpenTelemetry

Projects with an existing OpenTelemetry pipeline can import OTLP-style JSON. See
[OpenTelemetry compatibility](Documents/user-guide.md#opentelemetry-compatibility).

## Quick start

### 1. Install

AgentLint currently supports Python 3.12+ and the OpenAI Agents SDK:

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
    approval: required
    risk: high

rules:
  unknown_tool: error
  denied_tool_call: error
  missing_approval: error
```

### 3. Run your tests

```bash
pytest --agentlint --agentlint-policy agentlint.yaml
```

AgentLint captures supported agent runs, evaluates the policy, prints diagnostics, and
returns a nonzero exit code for policy violations or incomplete traces.

## Sample output

A policy violation produces a stable diagnostic code and a suggested fix:

```text
AgentLint Report
traces: 0 passed, 1 failed, 0 not verifiable, 0 invalid
diagnostics: 1 error, 0 warning, 0 info

status: failed

error[DENIED_TOOL_CALL]: tool call "evt_delete_account" uses tool
"delete_account" denied by trace policy
  related events: evt_delete_account
  remediation: Remove the call or update the trace policy when this tool
  should be permitted.
```

## Documentation

- [User guide](Documents/user-guide.md) — setup, integrations, policies, results, and
  CI behavior.
- [Examples](examples/) — policies, traces, expected reports, and runnable integrations.

## License

[MIT](LICENSE)
