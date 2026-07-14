from pathlib import Path

from agentlint.adapters.openai_agents import (
    OpenAIAgentsWarningCode,
    import_openai_agents_file,
    import_openai_agents_snapshot,
)
from agentlint.adapters.openai_snapshot import OpenAISpanSnapshot, load_openai_snapshot
from agentlint.capture import CaptureStatus
from agentlint.checking import TraceCheckStatus, check_trace
from agentlint.diagnostics import DiagnosticCode
from agentlint.passes import evaluate_policy, validate_structure
from agentlint.policy import load_policy

ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT = ROOT / "examples" / "external" / "openai_agents" / ("function_handoff_guardrail.json")


def test_openai_snapshot_maps_supported_spans() -> None:
    result = import_openai_agents_file(SNAPSHOT)

    assert result.trace.trace_id == "trace_openai_support"
    assert [event.type for event in result.trace.events] == [
        "agent_run",
        "model_call",
        "tool_call",
        "tool_result",
        "guardrail",
        "handoff",
    ]
    assert result.trace.events[2].id == "span_function:call"
    assert result.trace.events[3].id == "span_function:result"
    assert result.trace.events[3].call_id == "span_function:call"  # type: ignore[union-attr]
    assert validate_structure(result.trace) == []
    assert result.warnings == []
    parent_edges = {
        (edge.from_event, edge.to_event) for edge in result.trace.edges if edge.type == "parent"
    }
    assert ("span_agent", "span_response") in parent_edges
    assert ("span_agent", "span_function:call") in parent_edges


def test_openai_snapshot_runs_existing_policy_checks() -> None:
    result = import_openai_agents_file(SNAPSHOT)
    policy = load_policy(ROOT / "examples" / "policies" / "policy_checks.yaml")

    diagnostics = evaluate_policy(result.trace, policy)

    assert [diagnostic.code for diagnostic in diagnostics] == [DiagnosticCode.MISSING_APPROVAL]


def test_openai_capture_profile_is_conservative() -> None:
    capture = import_openai_agents_file(SNAPSHOT).capture

    assert capture.framework == "openai_agents"
    assert capture.framework_version == "0.18.1"
    assert capture.capabilities.agent_runs.status == CaptureStatus.CAPTURED
    assert capture.capabilities.model_calls.status == CaptureStatus.CAPTURED
    assert capture.capabilities.tool_calls.status == CaptureStatus.PARTIAL
    assert capture.capabilities.approvals.status == CaptureStatus.UNAVAILABLE
    assert capture.capabilities.final_answers.status == CaptureStatus.UNAVAILABLE
    assert capture.overall_status == CaptureStatus.UNAVAILABLE


def test_unknown_custom_span_still_warns() -> None:
    snapshot = load_openai_snapshot(SNAPSHOT)
    snapshot.spans.append(
        OpenAISpanSnapshot(
            trace_id=snapshot.trace_id,
            span_id="span_unknown_custom",
            parent_id="span_agent",
            span_type="custom",
            span_data={"name": "application_specific", "data": {}},
        )
    )

    result = import_openai_agents_snapshot(snapshot)

    assert [warning.code for warning in result.warnings] == [
        OpenAIAgentsWarningCode.UNSUPPORTED_SPAN.value
    ]


def test_semantic_records_map_approval_and_declared_data_flow() -> None:
    snapshot = load_openai_snapshot(SNAPSHOT)
    snapshot.spans.extend(
        [
            OpenAISpanSnapshot(
                trace_id=snapshot.trace_id,
                span_id="source_customer",
                span_type="agentlint_source",
                span_data={"name": "customer_profile", "sensitivity": "private"},
            ),
            OpenAISpanSnapshot(
                trace_id=snapshot.trace_id,
                span_id="approval_function",
                span_type="agentlint_approval",
                span_data={"decision": "approved", "subject_event": "span_function"},
            ),
            OpenAISpanSnapshot(
                trace_id=snapshot.trace_id,
                span_id="sink_function",
                span_type="agentlint_sink",
                span_data={
                    "name": "web_search.query",
                    "target_event": "span_function",
                    "source_events": ["source_customer"],
                    "visibility": "public",
                },
            ),
        ]
    )

    result = import_openai_agents_snapshot(snapshot)

    approval = next(event for event in result.trace.events if event.type == "approval")
    assert approval.subject_event == "span_function:call"  # type: ignore[union-attr]
    assert any(
        edge.type == "data_flow"
        and edge.from_event == "source_customer"
        and edge.to_event == "span_function:call"
        for edge in result.trace.edges
    )
    call = next(event for event in result.trace.events if event.id == "span_function:call")
    assert call.metadata["sink"] == "web_search.query"
    assert result.capture.capabilities.approvals.status == CaptureStatus.PARTIAL
    assert result.capture.capabilities.data_flow.status == CaptureStatus.PARTIAL
    assert result.warnings == []

    checked = check_trace(
        result.trace,
        policy=load_policy(ROOT / "examples" / "policies" / "policy_checks.yaml"),
    )
    assert checked.status == TraceCheckStatus.FAILED
