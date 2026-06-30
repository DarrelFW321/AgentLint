# Milestone 0 Build Report

Build date: 2026-06-30

Milestone 0 created the initial AgentLint project skeleton and verified it on Python 3.12.

## Built Artifacts

1. `pyproject.toml`
2. `README.md`
3. `.gitignore`
4. `src/agentlint/`
5. `tests/test_cli.py`
6. `examples/traces/`
7. `examples/policies/`
8. `examples/expected_reports/`
9. `Documents/architecture.md`
10. `Documents/glossary.md`

## Implemented CLI

Milestone 0 implements:

```bash
agentlint --help
agentlint version
agentlint doctor
```

In this local shell, the Python 3.12 user script directory is not on `PATH`, so verification used:

```bash
py -3.12 -m agentlint --help
py -3.12 -m agentlint version
py -3.12 -m agentlint doctor
```

## Verification Results

Verified successfully:

```bash
py -3.12 -m agentlint --help
py -3.12 -m agentlint version
py -3.12 -m agentlint doctor
py -3.12 -m pytest
py -3.12 -m ruff check .
py -3.12 -m ruff format --check .
```

Results:

1. CLI help exited successfully.
2. `version` printed `0.0.0`.
3. `doctor` reported Python 3.12.10 and `Python >=3.12: yes`.
4. pytest passed: 3 tests passed.
5. Ruff lint passed.
6. Ruff format check passed.

## Environment Notes

1. The default `python` command resolves to Python 3.11.4.
2. Python 3.12.10 is available through `py -3.12`.
3. `uv` is installed in the Python 3.12 user environment and verifies as `py -3.12 -m uv --version`.
4. The package was installed editable into the Python 3.12 user environment for verification.
5. The generated `agentlint.exe` and `uv.exe` scripts are not on `PATH` in this shell; `py -3.12 -m agentlint` and `py -3.12 -m uv` are the reliable local fallbacks.

## Remaining Milestone 0 Caveat

The Milestone 0 skeleton is built and verified. The only local environment caveat is that the Python 3.12 user scripts directory is not on `PATH`, so bare `agentlint` and `uv` commands may not resolve in this shell.
