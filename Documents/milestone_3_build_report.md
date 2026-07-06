# Milestone 3 Build Report

Build date: 2026-07-01

Status: complete.

## Scope

Milestone 3 implemented YAML Policy DSL V1 definition and validation.

Implemented:

1. Strict Pydantic policy models.
2. Policy-specific enums and rule IDs.
3. Safe YAML policy loading.
4. Duplicate YAML mapping-key rejection.
5. Policy file, YAML, and schema error classes.
6. Policy validation error formatting.
7. Example customer-support, research, and coding policies.
8. Invalid policy fixtures for schema, malformed YAML, duplicate keys, empty YAML, and non-mapping YAML.
9. `agentlint policy validate POLICY.yaml`.
10. `agentlint validate TRACE.json --policy POLICY.yaml` policy pre-validation.
11. Model, loader, and CLI tests.

Deferred:

1. Policy enforcement over traces.
2. Tool authorization checks.
3. Approval checks.
4. Data-flow checks.
5. Provenance checks.
6. Report output and CI thresholds.
7. Policy preset packaging.
8. Full value graph modeling.

## Implementation Summary

New modules:

1. `src/agentlint/policy/models.py`
2. `src/agentlint/policy/loaders.py`

Updated modules:

1. `src/agentlint/policy/__init__.py`
2. `src/agentlint/cli.py`

Key behavior:

1. `load_policy(path)` reads YAML policies and validates them as `Policy` objects.
2. The policy loader rejects duplicate YAML mapping keys before schema validation.
3. Policy errors remain input errors, not AgentLint diagnostics.
4. Policy rule IDs are defined for Milestone 4 but no policy checks run in Milestone 3.
5. `agentlint validate --policy` validates the policy first, then runs existing trace validation.

## Verification

Commands run on Python 3.12.10:

```text
py -3.12 -m agentlint --help
```

Result: passed. Help lists `policy`.

```text
py -3.12 -m agentlint policy validate examples\policies\customer_support.yaml
```

Result: passed.

```text
valid policy: customer_support_v1
version: 1
tools: 5
sources: 3
sinks: 3
rules: 14
exceptions: 1
```

```text
py -3.12 -m agentlint policy validate examples\policies\research.yaml
```

Result: passed.

```text
valid policy: research_v1
version: 1
tools: 3
sources: 3
sinks: 3
rules: 14
exceptions: 0
```

```text
py -3.12 -m agentlint policy validate examples\policies\coding.yaml
```

Result: passed.

```text
valid policy: coding_v1
version: 1
tools: 4
sources: 3
sinks: 3
rules: 14
exceptions: 0
```

```text
py -3.12 -m agentlint policy validate examples\policies\invalid_schema.yaml
```

Result: passed as an expected failure path, exited `1`.

```text
error: policy schema validation failed
  - version: Input should be 1 [literal_error]
  - tools.web_search.permission: Input should be 'allowed' or 'denied' [enum]
  - rules.unknown_tool: Input should be 'off', 'info', 'warning' or 'error' [enum]
```

```text
py -3.12 -m agentlint validate examples\traces\structural_valid_tool_flow.json --policy examples\policies\customer_support.yaml
```

Result: passed.

```text
valid policy: customer_support_v1
valid trace: trace_structural_valid_tool_flow
events: 5
edges: 5
diagnostics: 0
```

```text
py -3.12 -m pytest
```

Result: passed, `88 passed`.

```text
py -3.12 -m ruff check .
```

Result: passed. Ruff emitted cache-write warnings for the existing local `.ruff_cache`, but exited `0`.

```text
py -3.12 -m ruff format --check .
```

Result: passed. Ruff emitted the same cache-write warnings, but exited `0`.

```text
git diff --check
```

Result: passed.

## Notes

The Ruff cache warning appears local to the workspace cache directory permissions and did not affect lint or format results.
