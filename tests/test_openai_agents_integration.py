from pathlib import Path

import pytest

pytest.importorskip("agents")
from agents.tracing import agent_span, function_span, trace

from agentlint.adapters.openai_snapshot import load_openai_snapshot
from agentlint.integrations.openai_agents import (
    AgentLintTraceProcessor,
    OpenAIAgentsIntegrationError,
    OpenAICaptureSession,
)


def test_real_sdk_objects_persist_without_api_calls(tmp_path: Path) -> None:
    processor = AgentLintTraceProcessor(tmp_path)
    sdk_trace = trace("Local workflow")
    sdk_agent_span = agent_span("Support agent", parent=sdk_trace)
    sdk_function_span = function_span(
        "lookup_account",
        input='{"account_id":"A-100"}',
        output="active",
        parent=sdk_agent_span,
    )

    processor.on_trace_start(sdk_trace)
    processor.on_span_end(sdk_agent_span)
    processor.on_span_end(sdk_function_span)
    processor.on_trace_end(sdk_trace)

    paths = processor.snapshot_paths()
    assert len(paths) == 1
    snapshot = load_openai_snapshot(paths[0])
    assert snapshot.sdk_version is not None
    assert snapshot.sdk_version.startswith("0.18.")
    assert [span.span_type for span in snapshot.spans] == ["agent", "function"]


def test_processor_shutdown_is_idempotent(tmp_path: Path) -> None:
    processor = AgentLintTraceProcessor(tmp_path)

    processor.shutdown()
    processor.shutdown()

    assert processor.snapshot_paths() == []


def test_session_semantic_helpers_persist_labels_without_values(tmp_path: Path) -> None:
    processor = AgentLintTraceProcessor(tmp_path)
    sdk_trace = trace("Semantic workflow")
    processor.on_trace_start(sdk_trace)
    session = OpenAICaptureSession(processor)

    source_id = session.record_source(
        sdk_trace.trace_id,
        name="customer_profile",
        sensitivity="private",
        trust="trusted",
    )
    session.record_sink(
        sdk_trace.trace_id,
        name="external.query",
        target_event="tool_span",
        source_events=[source_id],
        visibility="public",
    )
    processor.force_flush()

    text = processor.snapshot_paths()[0].read_text(encoding="utf-8")
    assert "customer_profile" in text
    assert "external.query" in text
    assert "private customer value" not in text


def test_current_semantic_helpers_use_public_sdk_context(tmp_path: Path) -> None:
    processor = AgentLintTraceProcessor(tmp_path)
    sdk_trace = trace("Current semantic workflow")
    sdk_function_span = function_span(
        "external_search",
        input='{"query":"symbolic"}',
        output="result",
        parent=sdk_trace,
    )
    processor.on_trace_start(sdk_trace)
    processor.on_span_end(sdk_function_span)
    session = OpenAICaptureSession(processor)

    with sdk_trace:
        source_id = session.record_current_source(
            name="customer_profile",
            sensitivity="private",
        )
        with sdk_function_span:
            session.record_current_approval(decision="approved")
            session.record_current_sink(
                name="external_search.query",
                source_events=[source_id],
                visibility="public",
            )

    processor.on_trace_end(sdk_trace)
    snapshot = load_openai_snapshot(processor.snapshot_paths()[0])
    assert [span.span_type for span in snapshot.spans] == [
        "function",
        "agentlint_source",
        "agentlint_approval",
        "agentlint_sink",
    ]


def test_current_semantic_helper_fails_outside_trace_context(tmp_path: Path) -> None:
    session = OpenAICaptureSession(AgentLintTraceProcessor(tmp_path))

    with pytest.raises(OpenAIAgentsIntegrationError, match="no active OpenAI Agents trace"):
        session.record_current_approval(decision="approved")
