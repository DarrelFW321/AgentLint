"""Opt-in live OpenAI Agents demo with one local function tool."""

import os
from pathlib import Path

from agents import Agent, Runner, function_tool

from agentlint.integrations.openai_agents import instrument

OUTPUT_DIR = Path("examples/external/openai_agents/live_demo_capture")


@function_tool
def lookup_status(ticket_id: str) -> str:
    """Return synthetic local ticket status."""
    return f"Ticket {ticket_id} is open."


def main() -> None:
    if not os.environ.get("OPENAI_API_KEY"):
        raise SystemExit("OPENAI_API_KEY is required for the live demo")

    session = instrument(OUTPUT_DIR, export_mode="local_only")
    agent = Agent(
        name="Ticket assistant",
        instructions="Use lookup_status once, then answer in one short sentence.",
        model="gpt-5.4-mini",
        tools=[lookup_status],
    )
    result = Runner.run_sync(agent, "What is the status of ticket T-100?")
    print(result.final_output)
    for path in session.close():
        print(path)


if __name__ == "__main__":
    main()
