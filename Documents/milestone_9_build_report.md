# Milestone 9 Build Report: OpenAI Agents Capture Adapter

Status: implemented.

## Outcome

AgentLint now has its first framework-native Python adapter. OpenAI Agents SDK workflows can be captured locally through the SDK tracing processor interface, persisted as strict replayable snapshots, normalized into AgentLint IR, and checked by the existing framework-independent engine.

## Implemented

1. Added optional `openai-agents>=0.18,<0.19` support, tested with 0.18.2.
2. Added strict `agentlint.openai_agents.snapshot.v1` trace and span models.
3. Added sanitized snapshot loading errors.
4. Added `agent_run`, `handoff`, and `guardrail` IR events.
5. Added deterministic parent-first span ordering with timestamp and span-ID tie breaking.
6. Mapped agent, generation, response, function, handoff, and guardrail spans.
7. Split function spans into matching `tool_call` and `tool_result` events.
8. Added stable warnings for unsupported spans, invalid function input, missing parents, and incomplete spans.
9. Added a conservative OpenAI Agents completeness profile.
10. Added `agentlint import openai-agents INPUT --output OUTPUT`.
11. Added a thread-safe, non-networking AgentLint trace processor.
12. Added additive processor registration and explicit local-only replacement mode.
13. Added idempotent capture-session flushing and shutdown.
14. Added explicit session helpers for authoritative final outputs and approval decisions.
15. Added an explicitly activated pytest plugin with node association, no-trace failure, policy checking, and existing fail thresholds.
16. Added recorded snapshot, normalized IR, corpus coverage, and real-SDK offline tests.
17. Added zero-cost SDK and opt-in live agent demos.

## Mapping

| OpenAI Agents input | AgentLint IR |
| --- | --- |
| Trace | One AgentLint trace |
| Agent span | `agent_run` |
| Generation span | `model_call` |
| Response span | `model_call` with nullable payload |
| Function span input | `tool_call` |
| Function span output | `tool_result` |
| Handoff span | `handoff` |
| Guardrail span | `guardrail` |
| Span parent ID | `parent` edge |
| Explicit recorded result | `final_answer` |
| Explicit recorded decision | `approval` |

SDK `task` and `turn` custom spans are transparent containers. AgentLint collapses their parent chains to the nearest supported event and emits no warning for those two framework-owned names. Unknown application custom spans still produce `OPENAI_AGENTS_UNSUPPORTED_SPAN`.

## Completeness Boundary

The processor baseline marks agent runs and model calls captured; function-tool calls, arguments, and results partial; and approvals, value-level data flow, provenance, and final answers unavailable. Explicit result or approval helpers improve only the relevant trace capability to partial.

AgentLint does not infer approval from successful execution, final output from the last generation, data flow from parent spans, or claim provenance from model messages.

## User Workflows

Recorded snapshot:

```powershell
agentlint import openai-agents snapshot.json --output trace.agentlint.json
agentlint check trace.agentlint.json --policy agentlint.yaml
```

In process:

```python
from agentlint.integrations.openai_agents import instrument

session = instrument()
# Existing SDK runs.
session.close()
```

Pytest:

```powershell
pytest --agentlint --agentlint-policy agentlint.yaml
```

## Privacy and Operational Behavior

1. AgentLint reports retain metadata-only redaction.
2. Snapshot schema errors do not echo payloads.
3. Adapter warnings use structural messages rather than raw malformed inputs.
4. Additive mode preserves existing SDK trace export behavior.
5. Local-only mode replaces processors and is intended for isolated tests.
6. Users can disable SDK payload capture with `OPENAI_AGENTS_TRACE_INCLUDE_SENSITIVE_DATA=0` when raw model/function data is not required.
7. Default tests and the SDK tracing demo make no API calls and cost nothing.

## Deferred

1. Generic command wrapping and `sitecustomize` injection.
2. Automatic `Runner` result interception.
3. Automatic `RunState` decision interception.
4. Hosted/built-in tool parity.
5. Realtime, voice, and sandbox agents.
6. Full `pytest-xdist` support.
7. Policy-required capture enforcement.
8. Additional agent frameworks.
9. Hosted trace retrieval.
10. Automatic value-level data flow and provenance.

## Verification

Verified on Python 3.12.10 with OpenAI Agents SDK 0.18.2:

```text
240 passed, 1 skipped
```

The skipped default test is the explicitly activated pytest-plugin sample. Running it with `--agentlint` captured a real local SDK trace, produced one passing AgentLint report, and exited zero without an API call. A separate no-trace run exited one with an explicit capture error.

Ruff linting, Ruff formatting, and `git diff --check` also pass.

## Live Compatibility Correction

The first live API-backed demo against SDK 0.18.2 revealed that Responses runs emitted `response` spans and framework `custom` spans named `task` and `turn`. The initial adapter skipped those records, emitted seven warnings, and overstated model-call coverage.

The corrected adapter:

1. Maps `response` spans to nullable-payload `model_call` events.
2. Treats `task` and `turn` as transparent hierarchy containers.
3. Collapses parent edges through those containers.
4. Preserves warnings for genuinely unknown custom spans.
5. Preserves required null IR fields during CLI serialization.

Reimporting the same live snapshot produced five events, four edges, zero adapter warnings, and the expected `UNKNOWN_TOOL` policy diagnostic.
