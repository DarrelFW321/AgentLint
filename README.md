# AgentLint

[![CI](https://github.com/DarrelFW321/AgentLint/actions/workflows/ci.yml/badge.svg)](https://github.com/DarrelFW321/AgentLint/actions/workflows/ci.yml)
[![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-blue.svg)](https://www.python.org/downloads/)

AgentLint checks recorded agent runs against project policies. Use it in tests and CI
to catch unsafe tool use, missing approvals, sensitive-data flows, and unsupported
claims.

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

## Documentation

- [User guide](Documents/user-guide.md) — setup, integrations, policies, results, and
  CI behavior.
- [Examples](examples/) — policies, traces, expected reports, and runnable integrations.

## License

[MIT](LICENSE)
