# AgentLint

AgentLint is a CI-oriented policy checker for AI agent execution traces.

It will import traces from agent frameworks and observability systems, normalize them into an AgentLint intermediate representation, and detect policy violations involving tool use, data flow, approvals, and final-answer provenance.

## Status

AgentLint is at Milestone 2. The repository currently contains the project skeleton, native AgentLint IR v1 models, a native JSON trace loader, schema validation, structural validation diagnostics, smoke tests, example traces, and design documentation.

Policy checks, reports, and external trace adapters begin in later milestones.

## Development

Preferred workflow:

```bash
uv run agentlint --help
uv run agentlint version
uv run agentlint doctor
uv run agentlint validate examples/traces/structural_valid_tool_flow.json
uv run pytest
```

Fallback workflow after installing the project in a Python environment:

```bash
python -m agentlint --help
python -m agentlint validate examples/traces/structural_valid_tool_flow.json
python -m pytest
```

On Windows, if the default `python` is not Python 3.12 or newer, use the launcher:

```bash
py -3.12 -m agentlint --help
py -3.12 -m agentlint validate examples/traces/structural_valid_tool_flow.json
py -3.12 -m pytest
```

AgentLint targets Python 3.12 or newer.

## Current CLI

```bash
agentlint --help
agentlint version
agentlint doctor
agentlint validate examples/traces/structural_valid_tool_flow.json
```

`agentlint validate` currently validates native AgentLint IR v1 JSON traces, then runs structural validation and prints stable diagnostic codes for structural failures.

Future milestones will add policy checking, reports, and external trace adapters.
