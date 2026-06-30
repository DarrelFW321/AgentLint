# Milestone 0 R0 Research Findings

Research date: 2026-06-30

This document records the research findings for the Milestone 0 research track. The goal is to make the first implementation choices explicit before creating the project skeleton.

## Summary Decisions

1. Use Python 3.12 or newer.
2. Use `uv` as the preferred project and dependency workflow.
3. Use a `src/` layout.
4. Use `pyproject.toml` as the single source for package metadata, dependencies, console scripts, pytest config, and lint config.
5. Expose the CLI through a console script named `agentlint`.
6. Add `src/agentlint/__main__.py` so `python -m agentlint` also works after installation or in a configured environment.
7. Use Typer for the CLI and Typer's testing utilities for CLI smoke tests.
8. Use pytest as the test runner.
9. Use Pydantic later for schemas, including JSON Schema generation in Milestone 1.
10. Use PyYAML initially for policy YAML parsing, with `safe_load`.
11. Keep Milestone 0 limited to runnable skeleton, smoke tests, architecture documentation, glossary, and example directories.

## R0.1 Packaging And Dependency Management

### Findings

The Python packaging guide documents `pyproject.toml` as the modern place to define project metadata, dependencies, and executable scripts. Console scripts can be declared under `[project.scripts]`, which is the right fit for exposing `agentlint`.

The Python packaging guide also recommends considering `src/` layout because it separates importable package code from repository files. This matters for AgentLint because tests should import the installed package, not accidentally import files from the repo root.

The uv documentation supports project initialization, dependency management, and running commands inside the project environment. That matches the desired development workflow:

```bash
uv run agentlint --help
uv run pytest
```

Python 3.12 is a reasonable lower bound. It is modern, widely available, and still supported according to the Python version lifecycle.

### Decisions

Use this package baseline:

```toml
[project]
name = "agentlint"
version = "0.0.0"
requires-python = ">=3.12"
dependencies = [
  "pydantic",
  "pyyaml",
  "rich",
  "typer",
]

[project.scripts]
agentlint = "agentlint.cli:main"
```

Use dependency groups for development tools:

```toml
[dependency-groups]
dev = [
  "pytest",
  "ruff",
]
```

Defer strict type-checking tool choice until after Milestone 1. Pyright or mypy are both viable, but Milestone 0 only needs enough structure to avoid churn.

### Consequences

1. Milestone 0 should create `pyproject.toml`.
2. The package should live under `src/agentlint/`.
3. The console script should call `agentlint.cli:main`.
4. The project should support `uv run agentlint --help` as the preferred verification command.

## R0.2 CLI Shape

### Findings

Typer is a good fit for a small typed CLI and supports command-based applications. Its testing documentation supports invoking commands through `CliRunner`, which is suitable for smoke tests without shelling out.

Milestone 0 should avoid pretending trace analysis exists. The CLI should expose only commands that are true today.

### Decisions

Milestone 0 CLI commands:

```text
agentlint --help
agentlint version
agentlint doctor
```

`agentlint doctor` should be intentionally modest. It should report:

1. AgentLint version.
2. Python version.
3. Current working directory.
4. Whether the runtime is at least Python 3.12.

Add `src/agentlint/__main__.py` so this also works:

```bash
python -m agentlint --help
```

### Consequences

1. Do not add `validate`, `check`, or `explain` yet.
2. Mention future commands in docs, not CLI output.
3. CLI smoke tests should exercise `--help`, `version`, and `doctor`.

## R0.3 Testing Strategy

### Findings

pytest supports project-level configuration through `pyproject.toml`. Typer's test runner allows CLI command tests in-process.

Milestone 0 tests should validate the existence and basic behavior of the CLI, not deeper analysis semantics.

### Decisions

Initial tests:

1. `agentlint --help` exits with code 0.
2. `agentlint version` exits with code 0 and prints the package version.
3. `agentlint doctor` exits with code 0 and prints runtime information.

Use this initial test layout:

```text
tests/
  test_cli.py
```

Use this future fixture layout:

```text
examples/
  traces/
  policies/
  expected_reports/
```

### Consequences

1. Milestone 0 tests should be cheap and deterministic.
2. Golden-file tests should wait until reports exist.
3. Trace fixtures can be empty directories for now, but they should exist to stabilize repo layout.

## R0.4 Architecture Baseline

### Findings

The compiler-style pipeline remains the right architecture:

```text
raw traces
  -> adapters
  -> schema validation
  -> AgentLint IR
  -> enrichment passes
  -> analysis passes
  -> policy evaluation
  -> diagnostics and reports
```

Milestone 0 should define module boundaries without implementing analysis. This keeps Milestone 1 focused on the native trace format and IR rather than project setup.

### Decisions

Initial package layout:

```text
src/agentlint/
  __init__.py
  __main__.py
  cli.py
  version.py
  adapters/
  diagnostics/
  ir/
  passes/
  policy/
  reports/
```

Each subpackage can start with a minimal `__init__.py`. Real implementation begins later:

1. `ir/` becomes active in Milestone 1.
2. `diagnostics/` and `passes/` become active in Milestone 2.
3. `policy/` becomes active in Milestone 3.
4. `reports/` becomes active in Milestone 5.
5. `adapters/` becomes active in Milestone 7.

### Consequences

1. The code skeleton should communicate the intended architecture.
2. Placeholder modules should avoid fake abstractions.
3. `Documents/architecture.md` should explain what is intentionally not implemented yet.

## R0.5 Glossary And Research Baseline

### Findings

AgentLint needs stable vocabulary before implementation. Terms like "trace", "event", "value", "source", "sink", "claim", and "provenance" will shape the IR and policy design in later milestones.

The research note should record early design choices as dated findings so the project can later support an arXiv-style narrative.

### Decisions

Create `Documents/glossary.md` with definitions for:

1. Trace.
2. Event.
3. Value.
4. Source.
5. Sink.
6. Tool call.
7. Tool result.
8. Approval.
9. Claim.
10. Provenance.
11. Policy.
12. Violation.
13. Diagnostic.
14. Adapter.
15. Intermediate representation.

Create `Documents/architecture.md` with:

1. Pipeline overview.
2. Package boundaries.
3. V1 YAML policy decision.
4. OPA/Rego deferral.
5. Milestone 0 non-goals.

### Consequences

1. Milestone 0 should produce documentation as first-class output.
2. The research note should reference this R0 research document.
3. Later milestone documents should reuse the glossary terms rather than redefine them.

## Dependency Decision Details

### Typer

Use Typer for the CLI because it gives a direct path from typed Python functions to command-line commands and has first-party testing utilities.

### Rich

Include Rich as an early dependency because terminal diagnostics are central to AgentLint. Milestone 0 does not need rich formatting yet, but including it avoids changing dependency posture when the first human-readable output lands.

### Pydantic

Include Pydantic early because Milestone 1 will define schemas for the native trace format and IR. Pydantic's JSON Schema generation is useful for publishing `agentlint.ir.v1`.

### PyYAML

Use PyYAML initially with `safe_load`. AgentLint's V1 policy files should stay simple enough that ruamel.yaml's comment-preserving editing is unnecessary. If AgentLint later needs policy rewriting or comment-preserving formatting, reevaluate ruamel.yaml.

### Ruff

Use Ruff for formatting and linting to keep the project consistent from the first code commit.

### Type Checker

Defer the Pyright versus mypy decision. The codebase will be typed from the start, but strict type-checking gates can wait until the IR and policy schemas exist.

## Recommended Milestone 0 Implementation Changes

Compared with the initial Milestone 0 plan, make these changes:

1. Add `src/agentlint/__main__.py`.
2. Prefer `python -m agentlint --help` over `python -m agentlint.cli --help` as the fallback command.
3. Choose PyYAML for the initial YAML parser rather than leaving the choice open.
4. Defer strict type checker configuration until Milestone 1 or Milestone 2.

## Sources

1. uv project initialization: https://docs.astral.sh/uv/concepts/projects/init/
2. uv dependency management: https://docs.astral.sh/uv/concepts/projects/dependencies/
3. Python packaging guide for `pyproject.toml` and scripts: https://packaging.python.org/en/latest/guides/writing-pyproject-toml/
4. Python packaging discussion of `src/` layout: https://packaging.python.org/en/latest/discussions/src-layout-vs-flat-layout/
5. Python version lifecycle: https://devguide.python.org/versions/
6. Typer commands: https://typer.tiangolo.com/tutorial/commands/
7. Typer testing: https://typer.tiangolo.com/tutorial/testing/
8. pytest configuration: https://docs.pytest.org/en/stable/reference/customize.html
9. Pydantic JSON Schema: https://docs.pydantic.dev/latest/concepts/json_schema/
10. PyYAML documentation: https://pyyaml.org/wiki/PyYAMLDocumentation
