from pathlib import Path

from typer.testing import CliRunner

from agentlint.adapters.opentelemetry import (
    OpenTelemetryWarningCode,
    import_opentelemetry_file,
)
from agentlint.capture import CaptureStatus
from agentlint.checking import check_trace
from agentlint.cli import app
from agentlint.diagnostics import DiagnosticCode
from agentlint.passes import validate_structure
from agentlint.policy import load_policy

ROOT = Path(__file__).resolve().parents[1]
OTEL_DIR = ROOT / "examples" / "external" / "opentelemetry"
POLICY_DIR = ROOT / "examples" / "policies"


def policy_checks():
    return load_policy(POLICY_DIR / "policy_checks.yaml")


def diagnostic_codes(fixture_name: str) -> list[DiagnosticCode]:
    result = import_opentelemetry_file(OTEL_DIR / fixture_name)
    check_result = check_trace(result.trace, policy=policy_checks())
    return [diagnostic.code for diagnostic in check_result.diagnostics]


def test_imports_passing_tool_flow_to_native_ir() -> None:
    result = import_opentelemetry_file(OTEL_DIR / "passing_tool_flow.json")

    assert result.trace.trace_id == "otel_passing_tool_flow"
    assert [event.type for event in result.trace.events] == ["tool_call", "tool_result"]
    assert [edge.type for edge in result.trace.edges] == ["parent"]
    assert validate_structure(result.trace) == []
    assert result.warnings == []
    assert result.capture == result.trace.capture
    assert result.capture.adapter == "opentelemetry"
    assert result.capture.overall_status == CaptureStatus.PARTIAL
    assert all(
        coverage.status == CaptureStatus.PARTIAL
        for _, coverage in result.capture.capabilities.entries()
    )


def test_imported_missing_approval_runs_existing_policy_check() -> None:
    assert diagnostic_codes("missing_approval.json") == [DiagnosticCode.MISSING_APPROVAL]


def test_imported_private_to_public_flow_runs_existing_policy_check() -> None:
    assert diagnostic_codes("private_to_public_sink.json") == [
        DiagnosticCode.PRIVATE_TO_PUBLIC_SINK
    ]


def test_imported_unsupported_claim_runs_existing_policy_check() -> None:
    assert diagnostic_codes("unsupported_claim.json") == [DiagnosticCode.UNSUPPORTED_CLAIM]


def test_adapter_warnings_explain_unsupported_metadata() -> None:
    result = import_opentelemetry_file(OTEL_DIR / "unsupported_metadata.json")

    assert result.trace.trace_id == "otel_unsupported_metadata"
    assert [event.id for event in result.trace.events] == ["evt_lookup_account"]
    assert [warning.code for warning in result.warnings] == [
        OpenTelemetryWarningCode.SPAN_SKIPPED_MISSING_EVENT_TYPE.value,
        OpenTelemetryWarningCode.SPAN_SKIPPED_UNSUPPORTED_EVENT_TYPE.value,
        OpenTelemetryWarningCode.EDGE_TARGET_NOT_FOUND.value,
    ]


def test_import_cli_writes_native_trace_and_prints_summary() -> None:
    output_path = ROOT / "examples" / "generated" / "otel_missing_approval.agentlint.json"
    result = CliRunner().invoke(
        app,
        [
            "import",
            "opentelemetry",
            str(OTEL_DIR / "missing_approval.json"),
            "--output",
            str(output_path),
        ],
    )

    assert result.exit_code == 0
    assert "imported trace: otel_missing_approval" in result.stdout
    assert "events: 1" in result.stdout
    assert "warnings: 0" in result.stdout
    assert result.stderr == ""
    assert output_path.is_file()
    assert diagnostic_codes_from_import(output_path) == [DiagnosticCode.MISSING_APPROVAL]
    assert "capture: partial" in result.stdout

    from agentlint.ir.v1 import load_native_trace

    imported_trace = load_native_trace(output_path)
    assert imported_trace.capture is not None
    assert imported_trace.capture.overall_status == CaptureStatus.PARTIAL


def test_import_cli_prints_warnings_to_stderr() -> None:
    output_path = ROOT / "examples" / "generated" / "otel_unsupported_metadata.agentlint.json"
    result = CliRunner().invoke(
        app,
        [
            "import",
            "opentelemetry",
            str(OTEL_DIR / "unsupported_metadata.json"),
            "--output",
            str(output_path),
        ],
    )

    assert result.exit_code == 0
    assert "warnings: 3" in result.stdout
    assert "warning[OTEL_SPAN_SKIPPED_MISSING_EVENT_TYPE]" in result.stderr
    assert "warning[OTEL_EDGE_TARGET_NOT_FOUND]" in result.stderr
    imported = import_opentelemetry_file(OTEL_DIR / "unsupported_metadata.json")
    assert imported.capture.notes == sorted(imported.capture.notes)
    assert all("evt_" not in note for note in imported.capture.notes)


def diagnostic_codes_from_import(path: Path) -> list[DiagnosticCode]:
    from agentlint.ir.v1 import load_native_trace

    trace = load_native_trace(path)
    result = check_trace(trace, policy=policy_checks())
    return [diagnostic.code for diagnostic in result.diagnostics]
