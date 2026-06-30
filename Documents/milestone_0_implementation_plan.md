# Milestone 0 Implementation Plan

Milestone 0 establishes the project baseline for AgentLint: a runnable Python package, a CLI entry point, a test harness, example directories, and the initial research/design documents needed before building the trace IR and checks.

## Objective

Create a minimal but real AgentLint project skeleton that can be used as the foundation for Milestone 1.

Milestone 0 is complete when:

1. `agentlint --help` runs locally.
2. `pytest` runs locally with at least one smoke test.
3. The repository has clear directories for source code, tests, examples, policies, traces, and expected reports.
4. The architecture note explains the compiler-style pipeline.
5. The glossary defines the core terms used throughout the project.
6. The research note records the first design decisions and known limitations.

## Working Assumptions

1. AgentLint will start as a Python project.
2. V1 will use a purpose-built YAML policy DSL, not OPA/Rego as the core engine.
3. The first implementation should avoid external services and network calls during analysis.
4. The initial package should be small and boring; deep analysis logic starts in later milestones.
5. The repository is currently documentation-only, so Milestone 0 includes the first code scaffolding.

## Research Track

The research work in this milestone should answer practical implementation questions, not produce a literature survey yet.

### R0.1 Packaging And Dependency Management

Questions:

1. Should the project use `uv` as the primary development workflow?
2. What should the initial `pyproject.toml` contain?
3. What Python version should be required?
4. How should the console script expose `agentlint`?

Expected decision:

1. Use Python 3.12 or newer.
2. Use `uv` for development commands.
3. Define a console script named `agentlint`.
4. Keep dependencies minimal: `typer`, `rich`, `pydantic`, and `pyyaml`.
5. Defer strict type-checker selection until Milestone 1 or Milestone 2.

Output:

1. Documented setup commands.
2. Initial `pyproject.toml`.

### R0.2 CLI Shape

Questions:

1. What commands should exist before real analysis exists?
2. What should `agentlint --help` promise?
3. How do we avoid exposing commands that are not implemented yet?

Expected decision:

Milestone 0 should expose only safe placeholder commands:

```text
agentlint --help
agentlint version
agentlint doctor
```

Milestone 1 can add:

```text
agentlint validate
```

Milestone 5 can add:

```text
agentlint check
agentlint explain
```

Output:

1. Minimal Typer CLI.
2. Smoke tests for help/version behavior.

### R0.3 Testing Strategy

Questions:

1. What should tests cover before the IR exists?
2. How should CLI tests run?
3. Where should fixture traces live?

Expected decision:

1. Use `pytest`.
2. Use Typer's CLI test runner for command-level smoke tests.
3. Put future trace fixtures under `examples/traces/`.
4. Put expected reports under `examples/expected_reports/`.

Output:

1. Initial `tests/` directory.
2. CLI smoke test.
3. Placeholder fixture directories.

### R0.4 Architecture Baseline

Questions:

1. What are the stable module boundaries?
2. Which pieces are in scope for Milestone 0 versus Milestone 1?
3. How do we describe the compiler-style pipeline without overcommitting to internals?

Expected decision:

Initial module layout:

```text
src/agentlint/
  __init__.py
  __main__.py
  cli.py
  version.py
  adapters/
  diagnostics/
  ir/
  policy/
  reports/
  passes/
```

Most packages will contain placeholders in Milestone 0. Real models and passes begin in Milestone 1 and Milestone 2.

Output:

1. `Documents/architecture.md`.
2. Package directories with lightweight `__init__.py` files.

### R0.5 Glossary And Research Baseline

Questions:

1. What terms must be defined before implementation starts?
2. Which design decisions should be recorded for paper-quality traceability?
3. Which limitations should be acknowledged from the start?

Expected glossary terms:

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

Output:

1. `Documents/glossary.md`.
2. Updated `Documents/research_note.md`.

## Build Track

### B0.1 Create Project Skeleton

Files and directories:

```text
pyproject.toml
README.md
src/agentlint/
src/agentlint/__init__.py
src/agentlint/__main__.py
src/agentlint/cli.py
src/agentlint/version.py
src/agentlint/adapters/__init__.py
src/agentlint/diagnostics/__init__.py
src/agentlint/ir/__init__.py
src/agentlint/passes/__init__.py
src/agentlint/policy/__init__.py
src/agentlint/reports/__init__.py
tests/
tests/test_cli.py
examples/
examples/traces/
examples/policies/
examples/expected_reports/
```

Implementation notes:

1. Keep source under `src/` to avoid accidental import success from the repo root.
2. Keep package imports explicit.
3. Do not implement IR models yet unless needed for a smoke test.

### B0.2 Implement Minimal CLI

Commands:

```text
agentlint --help
agentlint version
agentlint doctor
```

Expected behavior:

1. `agentlint --help` prints available commands.
2. `agentlint version` prints the package version.
3. `agentlint doctor` checks basic runtime information:
   - Python version.
   - AgentLint version.
   - Current working directory.

Non-goals:

1. No trace validation yet.
2. No policy loading yet.
3. No report generation yet.

### B0.3 Add Tests

Initial tests:

1. CLI help exits successfully.
2. `agentlint version` exits successfully and includes the version string.
3. `agentlint doctor` exits successfully and includes Python/runtime information.

Commands:

```bash
uv run pytest
```

Fallback if `uv` is not installed:

```bash
python -m pytest
```

### B0.4 Add Documentation

Documents to create or update:

1. `README.md`
   - Short project description.
   - Current status.
   - Development setup.
   - Basic commands.
2. `Documents/architecture.md`
   - Compiler-style pipeline.
   - Initial package boundaries.
   - V1 policy decision.
   - What Milestone 0 does not implement.
3. `Documents/glossary.md`
   - Core vocabulary.
4. `Documents/research_note.md`
   - Add dated Milestone 0 entry.

## Suggested Work Order

1. Create `pyproject.toml` and package skeleton.
2. Add the minimal CLI.
3. Add the smoke tests.
4. Add example directories.
5. Add `README.md`.
6. Add `Documents/architecture.md`.
7. Add `Documents/glossary.md`.
8. Update `Documents/research_note.md`.
9. Run `agentlint --help`.
10. Run `pytest`.
11. Record any environment or dependency limitations.

## Verification Plan

Required commands:

```bash
uv run agentlint --help
uv run agentlint version
uv run agentlint doctor
uv run pytest
```

If `uv` is unavailable:

```bash
python -m agentlint --help
python -m pytest
```

Milestone 0 should not be considered complete until both CLI and tests pass in at least one supported workflow.

## Risks And Mitigations

### Risk: Overbuilding Too Early

Mitigation: keep Milestone 0 limited to skeleton, docs, and smoke tests. Defer IR schemas to Milestone 1.

### Risk: CLI Promises Too Much

Mitigation: expose only implemented commands. Mention upcoming commands in docs, not in CLI output.

### Risk: Tooling Friction

Mitigation: support `uv` as the preferred workflow but keep a plain Python fallback where practical.

### Risk: Research Notes Drift From Implementation

Mitigation: update `Documents/research_note.md` at the end of each milestone with concrete decisions, limitations, and observed tradeoffs.

## Completion Checklist

- [x] `pyproject.toml` exists.
- [x] `README.md` exists.
- [x] `src/agentlint/` package exists.
- [x] `src/agentlint/__main__.py` exists.
- [x] `agentlint --help` equivalent runs through `py -3.12 -m agentlint --help`.
- [x] `agentlint version` equivalent runs through `py -3.12 -m agentlint version`.
- [x] `agentlint doctor` equivalent runs through `py -3.12 -m agentlint doctor`.
- [x] `tests/test_cli.py` exists.
- [x] `pytest` passes on Python 3.12.
- [x] `examples/traces/` exists.
- [x] `examples/policies/` exists.
- [x] `examples/expected_reports/` exists.
- [x] `Documents/architecture.md` exists.
- [x] `Documents/glossary.md` exists.
- [x] `Documents/research_note.md` has a Milestone 0 entry.

See `Documents/milestone_0_build_report.md` for verification details and local environment caveats.
