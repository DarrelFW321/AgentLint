"""Zero-cost M10 workflow using real OpenAI Agents SDK trace objects."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from agents.tracing import agent_span, function_span, trace

from agentlint.adapters.openai_agents import import_openai_agents_file
from agentlint.checking import check_trace
from agentlint.integrations.openai_agents import AgentLintTraceProcessor, OpenAICaptureSession
from agentlint.policy import load_policy
from agentlint.reports import build_report, render_text_report

HERE = Path(__file__).resolve().parent
OUTPUT = HERE / "generated"


def capture_scenario(name: str, *, call_refund: bool, approved: bool) -> Path:
    processor = AgentLintTraceProcessor(OUTPUT / name)
    session = OpenAICaptureSession(processor)
    sdk_trace = trace(name)
    agent = agent_span("Customer support", parent=sdk_trace)

    processor.on_trace_start(sdk_trace)
    processor.on_span_end(agent)

    if call_refund:
        refund = function_span(
            "issue_refund",
            input='{"ticket_id":"T-100"}',
            output="refund queued",
            parent=agent,
        )
        if approved:
            session.record_approval(
                sdk_trace.trace_id,
                refund.span_id,
                decision="approved",
            )
        processor.on_span_end(refund)

    session.record_result(sdk_trace.trace_id, SimpleNamespace(final_output="Request handled."))
    processor.on_trace_end(sdk_trace)
    paths = processor.snapshot_paths()
    processor.shutdown()
    return paths[0]


def main() -> None:
    policy = load_policy(HERE / "agentlint.yaml")
    paths = [
        capture_scenario("approved_refund", call_refund=True, approved=True),
        capture_scenario("missing_approval", call_refund=True, approved=False),
        capture_scenario("approval_not_observed", call_refund=False, approved=False),
    ]
    results = []
    for path in paths:
        imported = import_openai_agents_file(path)
        results.append(check_trace(imported.trace, policy=policy, trace_path=str(path)))
    print(render_text_report(build_report(results)))


if __name__ == "__main__":
    main()
