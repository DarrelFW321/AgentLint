"""Generate a real OpenAI Agents SDK trace without making an API call."""

from pathlib import Path

from agents.tracing import agent_span, function_span, generation_span, guardrail_span, trace

from agentlint.integrations.openai_agents import instrument

OUTPUT_DIR = Path("examples/external/openai_agents/sdk_demo_capture")


def main() -> None:
    session = instrument(OUTPUT_DIR, export_mode="local_only")
    with trace("AgentLint local SDK demo") as workflow:
        with agent_span("Support agent", parent=workflow) as agent:
            with generation_span(
                input=[{"role": "user", "content": "Look up synthetic account A-100."}],
                output=[{"type": "function_call", "name": "lookup_account"}],
                model="local-demo-model",
                parent=agent,
            ):
                pass
            with function_span(
                "lookup_account",
                input='{"account_id":"A-100"}',
                output='{"status":"active"}',
                parent=agent,
            ):
                pass
            with guardrail_span("safe_output", triggered=False, parent=agent):
                pass

    paths = session.close()
    for path in paths:
        print(path)


if __name__ == "__main__":
    main()
