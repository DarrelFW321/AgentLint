import json
import subprocess
import sys
from pathlib import Path

import pytest

pytest.importorskip("agents")

from agentlint.integrations.pytest_runs import load_run_manifest

ROOT = Path(__file__).resolve().parents[1]
BASE_POLICY = ROOT / "examples" / "policies" / "openai_function_tools.yaml"


def test_pytest_capture_routes_policies_and_writes_recheckable_run(tmp_path: Path) -> None:
    first_policy = tmp_path / "first.yaml"
    second_policy = tmp_path / "second.yaml"
    policy_text = BASE_POLICY.read_text(encoding="utf-8")
    first_policy.write_text(
        policy_text.replace("policy_id: openai_function_tools", "policy_id: first_policy"),
        encoding="utf-8",
    )
    second_policy.write_text(
        policy_text.replace("policy_id: openai_function_tools", "policy_id: second_policy"),
        encoding="utf-8",
    )
    test_file = tmp_path / "test_agents.py"
    test_file.write_text(
        f"""
import pytest
from agents.tracing import function_span, trace

@pytest.mark.agentlint(policy={json.dumps(str(first_policy))})
def test_first_agent():
    with trace("First workflow") as workflow:
        with function_span(
            "lookup_account",
            input='{{"account_id":"A-100"}}',
            output='{{"status":"active"}}',
            parent=workflow,
        ):
            pass

def test_second_agent():
    with trace("Second workflow") as workflow:
        with function_span(
            "lookup_status",
            input='{{}}',
            output='{{"status":"ready"}}',
            parent=workflow,
        ):
            pass
""".strip(),
        encoding="utf-8",
    )
    runs_dir = tmp_path / "agentlint-runs"
    routing_config = tmp_path / "agentlint.pytest.yaml"
    routing_config.write_text(
        f"""
version: 1
routes:
  - tests: "*::test_second_agent"
    policy: {json.dumps(str(second_policy))}
""".strip(),
        encoding="utf-8",
    )

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            str(test_file),
            "-q",
            "--agentlint",
            "--agentlint-output",
            str(runs_dir),
            "--agentlint-config",
            str(routing_config),
            "--basetemp",
            str(tmp_path / "pytest-temp"),
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr
    pointer = runs_dir / "latest.json"
    assert pointer.is_file()
    manifest_path, manifest = load_run_manifest(pointer)
    assert manifest_path.is_file()
    assert len(manifest.traces) == 2
    assert {entry.policy_id for entry in manifest.traces} == {
        "first_policy",
        "second_policy",
    }
    assert {entry.pytest_node_id.split("::")[-1] for entry in manifest.traces} == {
        "test_first_agent",
        "test_second_agent",
    }
