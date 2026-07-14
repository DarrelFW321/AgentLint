"""Small API-backed OpenAI agent exercising AgentLint M10 outcomes."""

from __future__ import annotations

import os
from pathlib import Path
from uuid import uuid4

from agents import Agent, ModelSettings, Runner, function_tool
from agents.tracing import get_current_span, get_current_trace

from agentlint.adapters.openai_agents import import_openai_agents_file
from agentlint.adapters.openai_snapshot import load_openai_snapshot
from agentlint.checking import check_trace
from agentlint.integrations.openai_agents import OpenAICaptureSession, instrument
from agentlint.policy import load_policy
from agentlint.reports import build_report, render_text_report

HERE = Path(__file__).resolve().parent
OUTPUT_DIR = HERE / "generated" / uuid4().hex
MODEL = os.environ.get("AGENTLINT_OPENAI_MODEL", "gpt-5.4-mini")
SESSION: OpenAICaptureSession | None = None


@function_tool
def lookup_status(ticket_id: str) -> str:
    """Return a synthetic local ticket status."""
    return f"Ticket {ticket_id} is open."


@function_tool
def issue_refund(ticket_id: str) -> str:
    """Approve and queue a synthetic refund without contacting any external system."""
    if SESSION is None:
        raise RuntimeError("AgentLint capture session was not initialized")
    trace = get_current_trace()
    span = get_current_span()
    if trace is None or span is None:
        raise RuntimeError("OpenAI tracing context was unavailable inside issue_refund")
    SESSION.record_approval(trace.trace_id, span.span_id, decision="approved")
    return f"Synthetic refund for {ticket_id} was queued."


@function_tool
def diagnose_ticket(ticket_id: str) -> str:
    """Return a synthetic diagnosis; intentionally absent from the policy."""
    return f"Ticket {ticket_id} needs manual review."


def run_agent(name: str, instructions: str, prompt: str, tools: list[object]) -> Path:
    if SESSION is None:
        raise RuntimeError("AgentLint capture session was not initialized")
    before = set(SESSION.flush())
    agent = Agent(
        name=name,
        instructions=instructions,
        model=MODEL,
        tools=tools,
        model_settings=ModelSettings(tool_choice="required"),
        tool_use_behavior="stop_on_first_tool",
    )
    result = Runner.run_sync(agent, prompt, max_turns=3)
    after = set(SESSION.flush())
    new_paths = sorted(after - before)
    if len(new_paths) != 1:
        raise RuntimeError(f"expected one new trace for {name}, captured {len(new_paths)}")
    path = new_paths[0]
    snapshot = load_openai_snapshot(path)
    SESSION.record_result(snapshot.trace_id, result)
    print(f"{name}: {result.final_output}")
    return path


def main() -> None:
    global SESSION
    if not os.environ.get("OPENAI_API_KEY"):
        raise SystemExit("OPENAI_API_KEY is required")

    SESSION = instrument(OUTPUT_DIR, export_mode="local_only")
    paths = [
        run_agent(
            "Approved refund agent",
            "Call issue_refund exactly once for the requested ticket, then answer briefly.",
            "Issue a synthetic refund for ticket T-200.",
            [issue_refund],
        ),
        run_agent(
            "Unknown tool agent",
            "Call diagnose_ticket exactly once for the requested ticket, then answer briefly.",
            "Diagnose ticket T-201.",
            [diagnose_ticket],
        ),
        run_agent(
            "Status agent",
            "Call lookup_status exactly once for the requested ticket, then answer briefly.",
            "Check ticket T-202.",
            [lookup_status],
        ),
    ]
    SESSION.close()

    policy = load_policy(HERE / "agentlint.yaml")
    results = []
    for path in paths:
        imported = import_openai_agents_file(path)
        results.append(check_trace(imported.trace, policy=policy, trace_path=str(path)))
    print()
    print(render_text_report(build_report(results)))
    print(f"\nSnapshots: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
