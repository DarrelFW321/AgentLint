# AgentLint

AgentLint is a CI-oriented policy checker for AI agent execution traces.

It will import traces from agent frameworks and observability systems, normalize them into an AgentLint intermediate representation, and detect policy violations involving tool use, data flow, approvals, and final-answer provenance.

## Status

AgentLint is at Milestone 5. The repository currently contains the project skeleton, native AgentLint IR v1 models, a native JSON trace loader, schema validation, structural validation diagnostics, YAML policy loading and validation, offline policy checks, text and JSON reports, CI threshold behavior, smoke tests, example traces, example policies, and design documentation.

External trace adapters begin in later milestones.

## Development

Preferred workflow:

```bash
uv run agentlint --help
uv run agentlint version
uv run agentlint doctor
uv run agentlint validate examples/traces/structural_valid_tool_flow.json
uv run agentlint policy validate examples/policies/customer_support.yaml
uv run agentlint validate examples/traces/structural_valid_tool_flow.json --policy examples/policies/customer_support.yaml
uv run agentlint check examples/traces/policy_unknown_tool.json --policy examples/policies/policy_checks.yaml
uv run agentlint check examples/traces/policy_unknown_tool.json --policy examples/policies/policy_checks.yaml --format json
uv run agentlint explain UNKNOWN_TOOL
uv run pytest
```

Fallback workflow after installing the project in a Python environment:

```bash
python -m agentlint --help
python -m agentlint validate examples/traces/structural_valid_tool_flow.json
python -m agentlint policy validate examples/policies/customer_support.yaml
python -m agentlint check examples/traces/policy_tool_valid.json --policy examples/policies/policy_checks.yaml
python -m pytest
```

On Windows, if the default `python` is not Python 3.12 or newer, use the launcher:

```bash
py -3.12 -m agentlint --help
py -3.12 -m agentlint validate examples/traces/structural_valid_tool_flow.json
py -3.12 -m agentlint policy validate examples/policies/customer_support.yaml
py -3.12 -m agentlint check examples/traces/policy_tool_valid.json --policy examples/policies/policy_checks.yaml
py -3.12 -m pytest
```

AgentLint targets Python 3.12 or newer.

## Current CLI

```bash
agentlint --help
agentlint version
agentlint doctor
agentlint validate examples/traces/structural_valid_tool_flow.json
agentlint policy validate examples/policies/customer_support.yaml
agentlint validate examples/traces/structural_valid_tool_flow.json --policy examples/policies/customer_support.yaml
agentlint check examples/traces/policy_tool_valid.json --policy examples/policies/policy_checks.yaml
agentlint check examples/traces/policy_unknown_tool.json --policy examples/policies/policy_checks.yaml --format json
agentlint check examples/traces/policy_sensitive_final_answer.json --policy examples/policies/policy_checks.yaml --fail-on warning
agentlint explain UNKNOWN_TOOL
```

`agentlint validate` currently validates native AgentLint IR v1 JSON traces, then runs structural validation and prints stable diagnostic codes for structural failures.

`agentlint policy validate` validates YAML policy files. `agentlint validate TRACE.json --policy POLICY.yaml` validates the policy, validates the trace structurally, then runs offline policy checks for tool use, approvals, explicit data flow, and final-answer provenance.

`agentlint check` emits text or JSON reports for one or more explicit trace files. Use `--fail-on error|warning|info|never` to control CI exit behavior. Reports omit raw trace payload values by default and include redaction metadata.

Future milestones will add broader fixture corpus discipline, external trace adapters, and additional report integrations.
