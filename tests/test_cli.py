from pathlib import Path

from typer.testing import CliRunner

from agentlint.cli import app
from agentlint.version import __version__

runner = CliRunner()
TRACE_DIR = Path(__file__).resolve().parents[1] / "examples" / "traces"


def test_help_exits_successfully() -> None:
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "agentlint" in result.output.lower()
    assert "version" in result.output
    assert "doctor" in result.output
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
