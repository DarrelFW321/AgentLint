# Changelog

All notable changes to AgentLint are recorded here.

## 0.1.0a2 - 2026-07-14

### Fixed

- Use absolute repository links in the package README so documentation, examples,
  and license links work on PyPI.

## 0.1.0a1 - 2026-07-14

First public alpha of the `agentlint-trace` package.

### Added

- Compiler-style checks for tool use, approvals, data boundaries, and evidence.
- Native trace capture and policy routing for OpenAI Agents.
- Standalone CLI and optional pytest integration.
- JSON, text, and SARIF reports for local development and CI.
- OpenTelemetry import for spans carrying AgentLint semantic attributes.

### Known limitations

- OpenAI Agents is the only first-class framework integration.
- Data-flow checks depend on policy-declared sources, sinks, and boundaries.
- Evidence checks report `not_verifiable` when the trace lacks enough provenance.
