from pathlib import Path

from agentlint.capture import CaptureStatus
from agentlint.checking import InputErrorKind, TraceCheckStatus, check_trace_file
from agentlint.diagnostics import DiagnosticCode
from agentlint.policy import load_policy

TRACE_DIR = Path(__file__).resolve().parents[1] / "examples" / "traces"
POLICY_DIR = Path(__file__).resolve().parents[1] / "examples" / "policies"


def test_check_trace_file_passes_valid_trace_without_policy() -> None:
    result = check_trace_file(TRACE_DIR / "structural_valid_tool_flow.json")

    assert result.status == TraceCheckStatus.PASSED
    assert result.trace_id == "trace_structural_valid_tool_flow"
    assert result.policy_id is None
    assert result.events == 5
    assert result.edges == 5
    assert result.diagnostics == []
    assert result.input_error is None
    assert result.capture.adapter == "native"
    assert result.capture.overall_status == CaptureStatus.UNKNOWN


def test_check_trace_file_runs_policy_checks() -> None:
    policy = load_policy(POLICY_DIR / "policy_checks.yaml")
    result = check_trace_file(TRACE_DIR / "policy_unknown_tool.json", policy=policy)

    assert result.status == TraceCheckStatus.FAILED
    assert result.policy_id == "policy_checks_v1"
    assert [diagnostic.code for diagnostic in result.diagnostics] == [DiagnosticCode.UNKNOWN_TOOL]


def test_check_trace_file_gates_policy_on_structural_error() -> None:
    policy = load_policy(POLICY_DIR / "policy_checks.yaml")
    result = check_trace_file(
        TRACE_DIR / "structural_tool_call_missing_arguments.json",
        policy=policy,
    )

    assert result.status == TraceCheckStatus.FAILED
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        DiagnosticCode.TOOL_CALL_MISSING_ARGUMENTS
    ]
    assert result.diagnostics[0].policy_reference is None


def test_check_trace_file_reports_schema_error_as_invalid_result() -> None:
    result = check_trace_file(TRACE_DIR / "native_invalid_schema.json")

    assert result.status == TraceCheckStatus.INVALID
    assert result.input_error is not None
    assert result.input_error.kind == InputErrorKind.SCHEMA
    assert result.input_error.details
    assert result.capture.overall_status == CaptureStatus.UNKNOWN


def test_check_trace_file_reports_missing_file_as_invalid_result() -> None:
    result = check_trace_file(TRACE_DIR / "does_not_exist.json")

    assert result.status == TraceCheckStatus.INVALID
    assert result.input_error is not None
    assert result.input_error.kind == InputErrorKind.FILE
    assert "trace file not found" in result.input_error.message
