from typer.testing import CliRunner

from agentlint.cli import app
from agentlint.version import __version__

runner = CliRunner()


def test_help_exits_successfully() -> None:
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "agentlint" in result.output.lower()
    assert "version" in result.output
    assert "doctor" in result.output


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
