import json
from pathlib import Path

from typer.testing import CliRunner

from agentlint.cli import app
from agentlint.version import __version__

runner = CliRunner()
ROOT = Path(__file__).resolve().parents[1]
TRACE_DIR = ROOT / "examples" / "traces"
POLICY_DIR = ROOT / "examples" / "policies"


def test_help_exits_successfully() -> None:
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "agentlint" in result.output.lower()
    assert "version" in result.output
    assert "doctor" in result.output
    assert "import" in result.output
    assert "policy" in result.output
    assert "check" in result.output
    assert "check-run" in result.output
    assert "explain" in result.output
    assert "validate" in result.output


def test_version_prints_package_version() -> None:
    result = runner.invoke(app, ["version"])

    assert result.exit_code == 0
    assert __version__ in result.output


def test_doctor_prints_runtime_information() -> None:
    result = runner.invoke(app, ["doctor"])

    assert result.exit_code == 0
    assert f"AgentLint: {__version__}" in result.output
    assert "Python:" in result.output
    assert "Python >=3.12:" in result.output
    assert "Working directory:" in result.output


def test_validate_succeeds_for_valid_native_trace() -> None:
    result = runner.invoke(
        app,
        ["validate", str(TRACE_DIR / "structural_valid_tool_flow.json")],
    )

    assert result.exit_code == 0
    assert "valid trace: trace_structural_valid_tool_flow" in result.stdout
    assert "events: 5" in result.stdout
    assert "edges: 5" in result.stdout
    assert "diagnostics: 0" in result.stdout
    assert result.stderr == ""


def test_validate_succeeds_with_policy_enforcement() -> None:
    result = runner.invoke(
        app,
        [
            "validate",
            str(TRACE_DIR / "structural_valid_tool_flow.json"),
            "--policy",
            str(POLICY_DIR / "customer_support.yaml"),
        ],
    )

    assert result.exit_code == 0
    assert "valid policy: customer_support_v1" in result.stdout
    assert "valid trace: trace_structural_valid_tool_flow" in result.stdout
    assert "diagnostics: 0" in result.stdout
    assert result.stderr == ""


def test_validate_with_policy_fails_for_policy_error() -> None:
    result = runner.invoke(
        app,
        [
            "validate",
            str(TRACE_DIR / "policy_unknown_tool.json"),
            "--policy",
            str(POLICY_DIR / "policy_checks.yaml"),
        ],
    )

    assert result.exit_code == 1
    assert "valid policy: policy_checks_v1" in result.stdout
    assert "error[UNKNOWN_TOOL]" in result.stderr
    assert "policy reference: policy_checks_v1:unknown_tool" in result.stderr
    assert "valid trace:" not in result.stdout


def test_validate_with_policy_warning_only_exits_successfully() -> None:
    result = runner.invoke(
        app,
        [
            "validate",
            str(TRACE_DIR / "policy_unknown_tool.json"),
            "--policy",
            str(POLICY_DIR / "policy_checks_warning_only.yaml"),
        ],
    )

    assert result.exit_code == 0
    assert "valid policy: policy_checks_warning_only_v1" in result.stdout
    assert "valid trace: trace_policy_unknown_tool" in result.stdout
    assert "diagnostics: 1" in result.stdout
    assert "warning[UNKNOWN_TOOL]" in result.stderr


def test_validate_with_policy_stops_before_policy_checks_on_structural_error() -> None:
    result = runner.invoke(
        app,
        [
            "validate",
            str(TRACE_DIR / "structural_tool_call_missing_arguments.json"),
            "--policy",
            str(POLICY_DIR / "policy_checks.yaml"),
        ],
    )

    assert result.exit_code == 1
    assert "valid policy: policy_checks_v1" in result.stdout
    assert "error[TOOL_CALL_MISSING_ARGUMENTS]" in result.stderr
    assert "policy reference:" not in result.stderr
    assert "valid trace:" not in result.stdout


def test_validate_with_policy_fails_before_trace_loading_for_invalid_policy() -> None:
    result = runner.invoke(
        app,
        [
            "validate",
            str(TRACE_DIR / "structural_valid_tool_flow.json"),
            "--policy",
            str(POLICY_DIR / "invalid_schema.yaml"),
        ],
    )

    assert result.exit_code == 1
    assert "error: policy schema validation failed" in result.stderr
    assert "valid trace:" not in result.stdout


def test_check_succeeds_for_passing_trace() -> None:
    result = runner.invoke(
        app,
        [
            "check",
            str(TRACE_DIR / "policy_tool_valid.json"),
            "--policy",
            str(POLICY_DIR / "policy_checks.yaml"),
        ],
    )

    assert result.exit_code == 0
    assert "AgentLint Report" in result.stdout
    assert "traces: 1 passed, 0 failed, 0 not verifiable, 0 invalid" in result.stdout
    assert "diagnostics: 0 error, 0 warning, 0 info" in result.stdout
    assert result.stderr == ""


def test_check_fails_for_error_diagnostic_by_default() -> None:
    result = runner.invoke(
        app,
        [
            "check",
            str(TRACE_DIR / "policy_unknown_tool.json"),
            "--policy",
            str(POLICY_DIR / "policy_checks.yaml"),
        ],
    )

    assert result.exit_code == 1
    assert "error[UNKNOWN_TOOL]" in result.stdout
    assert "policy reference: policy_checks_v1:unknown_tool" in result.stdout
    assert result.stderr == ""


def test_check_json_outputs_parseable_json_only() -> None:
    result = runner.invoke(
        app,
        [
            "check",
            str(TRACE_DIR / "policy_unknown_tool.json"),
            "--policy",
            str(POLICY_DIR / "policy_checks.yaml"),
            "--format",
            "json",
        ],
    )

    assert result.exit_code == 1
    assert result.stderr == ""

    report = json.loads(result.stdout)
    assert report["schema_version"] == "agentlint.report.v4"
    assert report["summary"]["capture"]["unknown"] == 1
    assert report["summary"]["diagnostics"]["error"] == 1
    assert report["runs"][0]["diagnostics"][0]["code"] == "UNKNOWN_TOOL"


def test_import_openai_agents_writes_native_trace(tmp_path: Path) -> None:
    snapshot = (
        ROOT / "examples" / "external" / "openai_agents" / ("function_handoff_guardrail.json")
    )
    output = tmp_path / "openai.agentlint.json"

    result = runner.invoke(
        app,
        ["import", "openai-agents", str(snapshot), "--output", str(output)],
    )

    assert result.exit_code == 0
    assert "imported trace: trace_openai_support" in result.stdout
    assert "events: 6" in result.stdout
    assert "capture: unavailable" in result.stdout
    assert output.is_file()
    from agentlint.ir.v1 import load_native_trace

    trace = load_native_trace(output)
    model_call = next(event for event in trace.events if event.type == "model_call")
    assert model_call.input is None  # type: ignore[union-attr]


def test_check_warning_only_respects_fail_on_threshold() -> None:
    base_args = [
        "check",
        str(TRACE_DIR / "policy_sensitive_final_answer.json"),
        "--policy",
        str(POLICY_DIR / "policy_checks.yaml"),
    ]

    default_result = runner.invoke(app, base_args)
    warning_result = runner.invoke(app, [*base_args, "--fail-on", "warning"])

    assert default_result.exit_code == 0
    assert "warning[SENSITIVE_FINAL_ANSWER]" in default_result.stdout
    assert warning_result.exit_code == 1
    assert "warning[SENSITIVE_FINAL_ANSWER]" in warning_result.stdout


def test_check_never_does_not_fail_on_diagnostics() -> None:
    result = runner.invoke(
        app,
        [
            "check",
            str(TRACE_DIR / "policy_unknown_tool.json"),
            "--policy",
            str(POLICY_DIR / "policy_checks.yaml"),
            "--fail-on",
            "never",
        ],
    )

    assert result.exit_code == 0
    assert "error[UNKNOWN_TOOL]" in result.stdout


def test_check_invalid_trace_input_is_reported_and_fails_even_with_never() -> None:
    result = runner.invoke(
        app,
        [
            "check",
            str(TRACE_DIR / "native_invalid_schema.json"),
            "--fail-on",
            "never",
        ],
    )

    assert result.exit_code == 1
    assert "status: invalid" in result.stdout
    assert "input error[schema]: trace schema validation failed" in result.stdout
    assert result.stderr == ""


def test_check_invalid_policy_fails_before_report_output() -> None:
    result = runner.invoke(
        app,
        [
            "check",
            str(TRACE_DIR / "policy_tool_valid.json"),
            "--policy",
            str(POLICY_DIR / "invalid_schema.yaml"),
            "--format",
            "json",
        ],
    )

    assert result.exit_code == 1
    assert result.stdout == ""
    assert "error: policy schema validation failed" in result.stderr


def test_check_multiple_traces_preserves_argument_order() -> None:
    first_trace = TRACE_DIR / "policy_unknown_tool.json"
    second_trace = TRACE_DIR / "policy_missing_approval.json"
    result = runner.invoke(
        app,
        [
            "check",
            str(first_trace),
            str(second_trace),
            "--policy",
            str(POLICY_DIR / "policy_checks.yaml"),
            "--fail-on",
            "never",
        ],
    )

    assert result.exit_code == 0
    assert result.stdout.index(str(first_trace)) < result.stdout.index(str(second_trace))


def test_check_rejects_invalid_format_choice() -> None:
    result = runner.invoke(
        app,
        [
            "check",
            str(TRACE_DIR / "policy_tool_valid.json"),
            "--format",
            "xml",
        ],
    )

    assert result.exit_code != 0
    assert "invalid" in (result.stdout + result.stderr).lower()


def test_check_rejects_invalid_fail_on_choice() -> None:
    result = runner.invoke(
        app,
        [
            "check",
            str(TRACE_DIR / "policy_tool_valid.json"),
            "--fail-on",
            "critical",
        ],
    )

    assert result.exit_code != 0
    assert "invalid" in (result.stdout + result.stderr).lower()


def test_check_run_reports_missing_manifest() -> None:
    result = runner.invoke(app, ["check-run", "missing-run"])

    assert result.exit_code == 1
    assert "pytest run manifest not found" in result.stderr


def test_explain_succeeds_for_known_code() -> None:
    result = runner.invoke(app, ["explain", "unknown_tool"])

    assert result.exit_code == 0
    assert "code: UNKNOWN_TOOL" in result.stdout
    assert "category: policy" in result.stdout
    assert "remediation:" in result.stdout
    assert result.stderr == ""


def test_explain_fails_for_unknown_code() -> None:
    result = runner.invoke(app, ["explain", "NOT_A_CODE"])

    assert result.exit_code == 1
    assert "error: unknown diagnostic code: NOT_A_CODE" in result.stderr


def test_validate_fails_for_structural_diagnostic() -> None:
    result = runner.invoke(
        app,
        ["validate", str(TRACE_DIR / "structural_duplicate_event_id.json")],
    )

    assert result.exit_code == 1
    assert "error[DUPLICATE_EVENT_ID]" in result.stderr
    assert 'duplicate event id "evt_duplicate"' in result.stderr


def test_validate_fails_for_schema_error() -> None:
    result = runner.invoke(
        app,
        ["validate", str(TRACE_DIR / "native_invalid_schema.json")],
    )

    assert result.exit_code == 1
    assert "error: trace schema validation failed" in result.stderr
    assert "Field required" in result.stderr


def test_validate_fails_for_missing_file() -> None:
    result = runner.invoke(app, ["validate", str(TRACE_DIR / "does_not_exist.json")])

    assert result.exit_code == 1
    assert "trace file not found" in result.stderr


def test_policy_validate_succeeds_for_valid_policy() -> None:
    result = runner.invoke(
        app,
        ["policy", "validate", str(POLICY_DIR / "customer_support.yaml")],
    )

    assert result.exit_code == 0
    assert "valid policy: customer_support_v1" in result.stdout
    assert "version: 1" in result.stdout
    assert "tools: 5" in result.stdout
    assert "sources: 3" in result.stdout
    assert "sinks: 3" in result.stdout
    assert "rules: 14" in result.stdout
    assert "active checks:" in result.stdout
    assert "inferred evidence:" in result.stdout
    assert "exceptions: 1" in result.stdout
    assert result.stderr == ""


def test_policy_validate_explains_focused_checks_and_evidence() -> None:
    result = runner.invoke(
        app,
        ["policy", "validate", str(POLICY_DIR / "starter_approval.yaml")],
    )

    assert result.exit_code == 0
    assert (
        "active checks: unknown_tool, denied_tool_call, missing_approval, "
        "approval_after_action, action_after_denial, approval_mismatch"
    ) in result.stdout
    assert "inferred evidence: tool_calls>=partial, approvals>=partial" in result.stdout


def test_policy_validate_fails_for_invalid_schema() -> None:
    result = runner.invoke(
        app,
        ["policy", "validate", str(POLICY_DIR / "invalid_schema.yaml")],
    )

    assert result.exit_code == 1
    assert "error: policy schema validation failed" in result.stderr
    assert "version" in result.stderr


def test_policy_validate_fails_for_duplicate_yaml_key() -> None:
    result = runner.invoke(
        app,
        ["policy", "validate", str(POLICY_DIR / "duplicate_key.yaml")],
    )

    assert result.exit_code == 1
    assert "policy YAML parse failed" in result.stderr
    assert "duplicate key" in result.stderr


def test_policy_validate_fails_for_missing_file() -> None:
    result = runner.invoke(app, ["policy", "validate", str(POLICY_DIR / "missing.yaml")])

    assert result.exit_code == 1
    assert "policy file not found" in result.stderr
