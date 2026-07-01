from pathlib import Path

import pytest

from agentlint.ir.v1 import (
    TraceFileError,
    TraceJsonError,
    TraceSchemaError,
    format_validation_error,
    load_native_trace,
)

TRACE_DIR = Path(__file__).resolve().parents[1] / "examples" / "traces"


def test_load_native_trace_loads_minimal_valid_example() -> None:
    trace = load_native_trace(TRACE_DIR / "native_minimal_valid.json")

    assert trace.trace_id == "trace_minimal_valid"
    assert len(trace.events) == 1
    assert len(trace.edges) == 0


def test_load_native_trace_loads_tool_flow_valid_example() -> None:
    trace = load_native_trace(TRACE_DIR / "native_tool_flow_valid.json")

    assert trace.trace_id == "trace_tool_flow_valid"
    assert len(trace.events) == 5
    assert len(trace.edges) == 5


def test_load_native_trace_loads_missing_edge_endpoint_for_structural_validation() -> None:
    trace = load_native_trace(TRACE_DIR / "native_invalid_missing_event_ref.json")

    assert trace.trace_id == "trace_invalid_missing_event_ref"
    assert trace.edges[0].from_event == "evt_missing"


def test_load_native_trace_rejects_invalid_schema() -> None:
    with pytest.raises(TraceSchemaError) as exc_info:
        load_native_trace(TRACE_DIR / "native_invalid_schema.json")

    formatted_errors = format_validation_error(exc_info.value.validation_error)

    assert any("Field required" in error for error in formatted_errors)
    assert any("valid integer" in error for error in formatted_errors)


def test_load_native_trace_rejects_malformed_json() -> None:
    with pytest.raises(TraceJsonError, match="malformed JSON"):
        load_native_trace(TRACE_DIR / "native_malformed.json")


def test_load_native_trace_rejects_missing_file() -> None:
    with pytest.raises(TraceFileError, match="trace file not found"):
        load_native_trace(TRACE_DIR / "does_not_exist.json")
