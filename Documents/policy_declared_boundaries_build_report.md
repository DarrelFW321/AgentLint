# Policy-Declared Boundaries Build Report

## Outcome

AgentLint can apply reusable source and sink classifications to observed tool boundaries from policy YAML. This reduces repeated runtime annotations while preserving the offline deterministic evidence boundary.

## Policy Shape

```yaml
tools:
  customer_db.lookup:
    result:
      source: customer_profile
      sensitivity: private
      trust: trusted
  web_search:
    arguments:
      query:
        sink: public_search
        visibility: public
```

## Semantics

1. An observed `customer_db.lookup` tool result receives source label `customer_profile`.
2. An observed `web_search.query` argument causes its tool-call event to receive sink label `public_search`.
3. Inline classifications join the effective source and sink vocabulary used by policy compilation.
4. Conflicts with top-level source or sink classifications are rejected.
5. Boundary-only argument declarations do not activate argument-constraint checks.
6. Result boundaries require tool-result evidence.
7. Argument boundaries require tool-call and tool-argument evidence.
8. Boundary application does not modify the input trace and does not create edges.

## Evidence Boundary

Observing both boundaries does not prove flow:

```text
customer_db.lookup.result [Private]
web_search.query [Public]
```

AgentLint emits a private-to-public diagnostic only when an explicit `data_flow` edge connects the represented events. Without that relationship, no flow violation is fabricated; capture requirements can instead make the result `not_verifiable`.

## Compatibility

1. Policy version remains 1.
2. Existing top-level `sources` and `sinks` remain supported.
3. Existing application semantic helpers remain supported for dynamic boundaries and explicit relationships.
4. Native IR remains `agentlint.ir.v1`.
5. Report schema remains `agentlint.report.v4`.

## Verification

The complete suite passes on Python 3.12:

```text
280 passed, 1 skipped
```

The starter boundary policy reports one effective source, one effective sink, one result boundary, one argument boundary, the applicable private-to-public rule, and the required tool/data-flow evidence. Ruff formatting, Ruff linting, and `git diff --check` pass.
