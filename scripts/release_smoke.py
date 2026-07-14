"""Smoke-test an installed AgentLint distribution."""

from __future__ import annotations

import os
import subprocess
import sys
import sysconfig
import tempfile
from importlib.metadata import distribution
from pathlib import Path

EXPECTED_DISTRIBUTION = "agentlint-trace"


def run(*args: str, expected: int = 0) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        args,
        check=False,
        capture_output=True,
        text=True,
        env={key: value for key, value in os.environ.items() if key != "PYTHONPATH"},
    )
    if result.returncode != expected:
        raise RuntimeError(
            f"command returned {result.returncode}, expected {expected}: {' '.join(args)}\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )
    return result


def main() -> None:
    package = distribution(EXPECTED_DISTRIBUTION)
    version = package.version

    from agentlint.integrations.openai_agents import instrument  # noqa: F401
    from agentlint.version import __version__

    if version != __version__:
        raise RuntimeError(f"metadata version {version!r} != package version {__version__!r}")

    executable = Path(sysconfig.get_path("scripts")) / (
        "agentlint.exe" if sys.platform == "win32" else "agentlint"
    )
    if not executable.is_file():
        raise RuntimeError(f"console script was not installed: {executable}")
    if run(str(executable), "version").stdout.strip() != version:
        raise RuntimeError("the CLI version does not match installed package metadata")
    run(str(executable), "--help")
    run(str(executable), "doctor")

    pytest_help = run(sys.executable, "-m", "pytest", "--help").stdout
    if "--agentlint" not in pytest_help:
        raise RuntimeError("the installed pytest plugin was not discovered")

    with tempfile.TemporaryDirectory(prefix="agentlint-smoke-") as temporary:
        root = Path(temporary)
        trace = root / "trace.json"
        policy = root / "policy.yaml"
        trace.write_text(
            """{
  "schema_version": "agentlint.ir.v1",
  "trace_id": "release-smoke",
  "capture": {
    "schema_version": "agentlint.capture.v1",
    "adapter": "release_smoke",
    "capabilities": {
      "agent_runs": {"status": "captured"},
      "model_calls": {"status": "captured"},
      "tool_calls": {"status": "captured"},
      "tool_arguments": {"status": "captured"},
      "tool_results": {"status": "captured"},
      "approvals": {"status": "captured"},
      "data_flow": {"status": "captured"},
      "provenance": {"status": "captured"},
      "final_answers": {"status": "captured"}
    }
  },
  "events": [
    {
      "id": "evt-user",
      "type": "user_message",
      "sequence": 0,
      "content": "Run the release smoke test."
    }
  ],
  "edges": []
}
""",
            encoding="utf-8",
        )
        policy.write_text(
            """version: 1
policy_id: release_smoke
rules:
  unknown_tool: error
""",
            encoding="utf-8",
        )
        report = run(
            str(executable),
            "check-capture",
            str(trace),
            "--policy",
            str(policy),
            "--fail-on",
            "never",
        ).stdout
        if "release-smoke" not in report:
            raise RuntimeError(f"unexpected check-capture output:\n{report}")

    print(f"smoke test passed: {EXPECTED_DISTRIBUTION} {version}")


if __name__ == "__main__":
    main()
