# AgentLint

AgentLint is an offline, deterministic CI policy checker for recorded AI agent execution traces.

It will import traces from agent frameworks and observability systems, normalize them into an AgentLint intermediate representation, and detect policy violations involving tool use, data flow, approvals, and final-answer provenance.

AgentLint answers one bounded question:

> Did this recorded agent run violate a developer-defined policy that can be verified from the captured evidence?

It analyzes explicit trace facts and relationships. It does not infer arbitrary Python data flow, judge whether natural-language claims are true, authorize production actions, or prove that an agent is universally safe. When a policy requires evidence that the trace did not capture, AgentLint reports `not_verifiable` instead of a pass.

## Product Scope

The initial product is a developer test and CI tool:

```text
run agent scenarios
  -> collect traces
  -> normalize explicit evidence
  -> check deterministic policies
  -> emit compiler-style diagnostics and a CI result
```

In scope:

1. Importing supported completed traces.
2. Structural trace validation.
3. Deterministic checks over explicit tool, approval, data-flow, and provenance evidence.
4. Capture-completeness assessment and `not_verifiable` outcomes.
5. Human-readable and machine-readable CI reports.

Outside the initial scope:

1. Runtime authorization, action blocking, or approval user interfaces.
2. General-purpose observability, trace storage, or security dashboards.
3. Universal runtime taint tracking or natural-language data-flow inference.
4. Semantic fact-checking, subjective answer grading, or general LLM evaluation.
5. Enterprise identity, role, compliance, or policy-administration systems.

## Status

AgentLint has completed Milestone 11 scope alignment. The repository currently contains native AgentLint IR v1, structural and policy checks, a shared compiled rule/evidence plan, policy-specific evidence requirements, `not_verifiable` outcomes, report v4 diagnostic paths, a curated fixture corpus, a generic OpenTelemetry importer, and a first-class Python OpenAI Agents SDK capture adapter with semantic helpers and optional pytest integration.

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
uv run agentlint import opentelemetry examples/external/opentelemetry/missing_approval.json --output examples/generated/otel_missing_approval.agentlint.json
uv run agentlint explain UNKNOWN_TOOL
uv run pytest
```

Fallback workflow after installing the project in a Python environment:

```bash
python -m agentlint --help
python -m agentlint validate examples/traces/structural_valid_tool_flow.json
python -m agentlint policy validate examples/policies/customer_support.yaml
python -m agentlint check examples/traces/policy_tool_valid.json --policy examples/policies/policy_checks.yaml
python -m agentlint import opentelemetry examples/external/opentelemetry/missing_approval.json --output examples/generated/otel_missing_approval.agentlint.json
python -m pytest
```

On Windows, if the default `python` is not Python 3.12 or newer, use the launcher:

```bash
py -3.12 -m agentlint --help
py -3.12 -m agentlint validate examples/traces/structural_valid_tool_flow.json
py -3.12 -m agentlint policy validate examples/policies/customer_support.yaml
py -3.12 -m agentlint check examples/traces/policy_tool_valid.json --policy examples/policies/policy_checks.yaml
py -3.12 -m agentlint import opentelemetry examples/external/opentelemetry/missing_approval.json --output examples/generated/otel_missing_approval.agentlint.json
py -3.12 -m agentlint import openai-agents examples/external/openai_agents/function_handoff_guardrail.json --output examples/generated/openai_function_handoff_guardrail.agentlint.json
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
agentlint import opentelemetry examples/external/opentelemetry/missing_approval.json --output examples/generated/otel_missing_approval.agentlint.json
agentlint explain UNKNOWN_TOOL
```

`agentlint validate` currently validates native AgentLint IR v1 JSON traces, then runs structural validation and prints stable diagnostic codes for structural failures.

`agentlint policy validate` validates YAML policy files. `agentlint validate TRACE.json --policy POLICY.yaml` validates the policy, validates the trace structurally, then runs offline policy checks for tool use, approvals, explicit data flow, and final-answer provenance.

Policy validation also prints the checks activated by the policy and their inferred minimum evidence requirements. Focused policies activate checks from the constructs they configure; provenance checks require explicit activation rather than silently applying to every policy.

Starter policies are available for focused adoption:

```text
examples/policies/starter_tools.yaml
examples/policies/starter_approval.yaml
examples/policies/starter_data_flow.yaml
examples/policies/starter_provenance.yaml
```

Policies can classify observed tool boundaries once without adding per-call annotations:

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

AgentLint applies these labels to captured tool results and arguments before policy evaluation. Boundary declarations do not create `data_flow` edges or prove that one value influenced another. A flow check requires an explicit relationship from the framework, adapter, or application; otherwise required data-flow evidence remains incomplete and can produce `not_verifiable`.

`agentlint check` emits text or JSON reports for one or more explicit trace files. Use `--fail-on error|warning|info|never` to control CI exit behavior. Reports omit raw trace payload values by default and include redaction metadata.

`agentlint import opentelemetry` imports a supported OTLP-style JSON trace into native AgentLint IR. The importer expects explicit `agentlint.*` span attributes for agent semantics such as event type, event ID, tool name, source labels, sink labels, data-flow targets, approvals, and final-answer claims. Import warnings describe spans or relationships that could not be mapped precisely.

Imported traces preserve a per-trace capture completeness profile through normalization. Report schema v2 states whether relevant evidence was captured, partial, unavailable, or unknown, and passing incomplete traces explicitly limit the verification claim. See `Documents/milestone_8_build_report.md`.

The OpenTelemetry demo path is fully offline:

```bash
python examples/opentelemetry/generate_demo_trace.py
agentlint import opentelemetry examples/external/opentelemetry/demo_missing_approval.json --output examples/generated/otel_missing_approval.agentlint.json
agentlint check examples/generated/otel_missing_approval.agentlint.json --policy examples/policies/policy_checks.yaml
```

There is also an optional SDK-backed demo that uses the real OpenTelemetry SDK while still making no network calls:

```bash
pip install -e .[otel-demo]
python examples/opentelemetry/generate_sdk_demo_trace.py
agentlint import opentelemetry examples/external/opentelemetry/sdk_demo_missing_approval.json --output examples/generated/otel_sdk_demo_missing_approval.agentlint.json
agentlint check examples/generated/otel_sdk_demo_missing_approval.agentlint.json --policy examples/policies/policy_checks.yaml
```

For a fuller local support-agent run:

```bash
python examples/opentelemetry/support_agent_demo.py
agentlint import opentelemetry examples/external/opentelemetry/support_agent_demo.json --output examples/generated/support_agent_demo.agentlint.json
agentlint check examples/generated/support_agent_demo.agentlint.json --policy examples/policies/policy_checks.yaml
```

That script uses real OpenTelemetry SDK spans to simulate a support workflow with private account data, a public web-search leak, and an email sent without approval. It is still fully local and costs nothing to run.

For an agent-shaped local run with a deterministic planner and local Python tools:

```bash
python examples/opentelemetry/local_agent_demo.py
agentlint import opentelemetry examples/external/opentelemetry/local_agent_demo.json --output examples/generated/local_agent_demo.agentlint.json
agentlint check examples/generated/local_agent_demo.agentlint.json --policy examples/policies/policy_checks.yaml
```

This is not an LLM-backed agent, but it exercises an actual agent control loop: prompt, planning, tool calls, tool results, and final answer.

## OpenAI Agents SDK

Install the optional integration:

```powershell
py -3.12 -m pip install -e ".[openai-agents]"
```

For one-line in-process capture:

```python
from agentlint.integrations.openai_agents import instrument

session = instrument(".agentlint/openai-agents")
# Run ordinary OpenAI Agents SDK workflows.
session.close()
```

`export_mode="additive"` preserves the SDK's existing trace processors. Use `export_mode="local_only"` only in an isolated test process when AgentLint should replace existing processors and avoid hosted trace export.

For pytest:

```powershell
pytest --agentlint --agentlint-policy examples/policies/openai_function_tools.yaml
```

Capture begins only when `--agentlint` is supplied. A requested session that captures no supported traces fails instead of reporting a clean policy result.

Policies may require minimum evidence levels:

```yaml
capture:
  require:
    tool_calls: partial
    approvals: partial
```

AgentLint also infers minimum evidence from configured policy constructs. A structurally valid trace with no known violation is `not_verifiable` when required evidence is unavailable or unknown. Invalid and not-verifiable traces fail CLI and pytest independently of `--fail-on`.

The zero-cost SDK demo creates real SDK spans without a model call:

```powershell
py -3.12 examples/openai_agents/sdk_trace_demo.py
agentlint import openai-agents <printed-snapshot-path> --output openai-demo.agentlint.json
agentlint check openai-demo.agentlint.json --policy examples/policies/policy_checks.yaml
```

`examples/openai_agents/live_agent_demo.py` is an optional API-backed demo. It requires `OPENAI_API_KEY`, uses one short run and one local function tool, and is never run by the default test suite.

`examples/openai_agents/live_policy_agent/` runs three actual API-backed agent workflows and demonstrates an approved tool pass, an unknown-tool failure, and a not-verifiable evidence result. Its tools are synthetic and local, and generated snapshots are ignored by Git.

OpenAI Agents tracing does not automatically expose authoritative general approval decisions, AgentLint data-flow/provenance semantics, or `RunResult.final_output`. Reports show those limitations through M8 capture completeness instead of implying they were verified.

For SDK 0.18.x, AgentLint recognizes both `generation` and `response` model-call spans. It also treats SDK `task` and `turn` custom spans as transparent hierarchy containers, preserving parent relationships without reporting them as unsupported application events.

## Fixture Corpus

The curated fixture corpus is indexed by `examples/fixtures/manifest.yaml`. The manifest records each canonical trace, optional policy, expected status, expected diagnostic codes, report coverage, redaction expectations, and performance-smoke membership.

When adding a new diagnostic code or behavior check:

1. Add or update a trace under `examples/traces/`.
2. Add a manifest entry with the expected diagnostic code.
3. Add a JSON golden under `examples/expected_reports/` when report output is part of the behavior.
4. Run `py -3.12 -m pytest tests\test_fixture_corpus.py`.

The corpus tests enforce that every current diagnostic code has fixture coverage and that representative JSON reports are deterministic.

The zero-cost M10 customer-support workflow demonstrates passing, failed, and not-verifiable outcomes with real SDK trace objects:

```powershell
py -3.12 examples\openai_agents\customer_support\demo.py
```

See `Documents/milestone_10_build_report.md`. Additional framework adapters, including a likely LangGraph adapter, follow after the evidence contract is evaluated against real projects.
