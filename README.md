# AgentLint

AgentLint is a CI-oriented policy checker for AI agent execution traces.

It will import traces from agent frameworks and observability systems, normalize them into an AgentLint intermediate representation, and detect policy violations involving tool use, data flow, approvals, and final-answer provenance.

## Status

AgentLint is at Milestone 0. The repository currently contains the project skeleton, minimal CLI, smoke tests, example directories, and design documentation. Trace validation and policy checks begin in later milestones.

## Development

Preferred workflow:

```bash
uv run agentlint --help
uv run agentlint version
uv run agentlint doctor
uv run pytest
```

Fallback workflow after installing the project in a Python environment:

```bash
python -m agentlint --help
python -m pytest
```

On Windows, if the default `python` is not Python 3.12 or newer, use the launcher:

```bash
py -3.12 -m agentlint --help
py -3.12 -m pytest
```

AgentLint targets Python 3.12 or newer.

## Current CLI

```bash
agentlint --help
agentlint version
agentlint doctor
```

Future milestones will add trace validation, policy checking, reports, and external trace adapters.
