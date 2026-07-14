# AgentLint

[![CI](https://github.com/DarrelFW321/AgentLint/actions/workflows/ci.yml/badge.svg)](https://github.com/DarrelFW321/AgentLint/actions/workflows/ci.yml)
[![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-blue.svg)](https://www.python.org/downloads/)
[![PyPI](https://img.shields.io/pypi/v/agentlint-trace.svg)](https://pypi.org/project/agentlint-trace/)

AgentLint checks recorded agent runs for unsafe tool use, missing approvals,
sensitive-data flows, and unsupported claims.

## Integrations

| Integration | Workflow |
| --- | --- |
| OpenAI Agents SDK | Automatic pytest capture or `instrument()` in any Python runner |
| OpenTelemetry | Import existing OTLP-style JSON |

## Install

```bash
python -m pip install "agentlint-trace[openai-agents]==0.1.0a1"
```

AgentLint requires Python 3.12 or newer.

## Define a policy

Create `agentlint.yaml`:

```yaml
version: 1
policy_id: customer_support

tools:
  lookup_status:
    permission: allowed
    approval: not_required

  issue_refund:
    permission: allowed
    approval: required

rules:
  unknown_tool: error
  denied_tool_call: error
  missing_approval: error
```

## Run

Pytest is optional. Choose the workflow that fits the project.

### Pytest

```bash
pytest --agentlint --agentlint-policy agentlint.yaml
```

The command runs the tests, captures their agent traces, and checks the saved run.
Artifacts are written to `.agentlint/runs/`.

```bash
agentlint check-run .agentlint/runs/latest.json
```

Use a [test marker or routing file](Documents/user-guide.md#policy-selection) when
tests require different policies.

### Any Python runner

```python
from agentlint.integrations.openai_agents import instrument

session = instrument(".agentlint/openai-agents")

# Run the agent.

snapshot_paths = session.close()
```

Check the capture directory:

```bash
agentlint check-capture .agentlint/openai-agents --policy agentlint.yaml
```

`check-capture` also accepts one JSON file and detects OpenAI Agents, OpenTelemetry,
and native AgentLint formats.

## Sample output

```text
AgentLint Report
traces: 0 passed, 1 failed, 0 not verifiable, 0 invalid
diagnostics: 1 error, 0 warning, 0 info

error[DENIED_TOOL_CALL]: tool call "evt_delete_account" uses tool
"delete_account" denied by trace policy
  related events: evt_delete_account
  remediation: Remove the call or update the trace policy when this tool
  should be permitted.
```

## Documentation

- [User guide](Documents/user-guide.md)
- [Examples](examples/)
- [OpenTelemetry compatibility](Documents/user-guide.md#opentelemetry-compatibility)

## License

[MIT](LICENSE)
