import pytest

pytest.importorskip("agents")
from agents.tracing import agent_span, function_span, trace


def test_pytest_plugin_captures_local_sdk_trace(request: pytest.FixtureRequest) -> None:
    if not request.config.getoption("--agentlint"):
        pytest.skip("sample runs only during explicit AgentLint plugin verification")

    with trace("Pytest plugin sample") as workflow:
        with agent_span("Support agent", parent=workflow) as agent:
            with function_span(
                "lookup_account",
                input='{"account_id":"A-100"}',
                output='{"status":"active"}',
                parent=agent,
            ):
                pass
