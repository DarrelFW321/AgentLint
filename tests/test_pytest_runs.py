from pathlib import Path

import pytest

from agentlint.adapters.openai_snapshot import (
    OpenAISpanSnapshot,
    OpenAITraceSnapshot,
)
from agentlint.integrations.pytest_runs import (
    PytestRunError,
    check_run,
    default_policy,
    load_routing_config,
    load_run_manifest,
    route_policy,
    write_latest_pointer,
    write_run_manifest,
)

ROOT = Path(__file__).resolve().parents[1]
POLICY = ROOT / "examples" / "policies" / "openai_function_tools.yaml"


def test_routing_uses_first_matching_route_and_separate_default(tmp_path: Path) -> None:
    config_path = tmp_path / "agentlint.pytest.yaml"
    config_path.write_text(
        """
version: 1
default_policy: policies/default.yaml
routes:
  - tests: tests/refunds/**
    policy: policies/refunds.yaml
  - tests:
      - tests/research/**
      - tests/browser/**
    policy: policies/research.yaml
""".strip(),
        encoding="utf-8",
    )

    config = load_routing_config(config_path)

    assert (
        route_policy("tests/refunds/test_agent.py::test_refund", config, config_path.parent)
        == tmp_path / "policies" / "refunds.yaml"
    )
    assert (
        route_policy("tests/browser/test_agent.py::test_search", config, config_path.parent)
        == tmp_path / "policies" / "research.yaml"
    )
    assert route_policy("tests/other/test_agent.py::test_other", config, config_path.parent) is None
    assert default_policy(config, config_path.parent) == tmp_path / "policies" / "default.yaml"


def test_invalid_routing_config_is_rejected(tmp_path: Path) -> None:
    config_path = tmp_path / "agentlint.pytest.yaml"
    config_path.write_text("version: 2\n", encoding="utf-8")

    with pytest.raises(PytestRunError, match="invalid pytest routing config"):
        load_routing_config(config_path)


def test_manifest_copies_policy_and_rechecks_run(tmp_path: Path) -> None:
    run_dir = tmp_path / "runs" / "run-123"
    snapshot_path = run_dir / "traces" / "trace.openai-agents.json"
    snapshot_path.parent.mkdir(parents=True)
    snapshot = OpenAITraceSnapshot(
        trace_id="trace_pytest_run",
        workflow_name="Support workflow",
        metadata={"pytest_node_id": "tests/test_support.py::test_lookup"},
        sdk_version="0.18.1",
        spans=[
            OpenAISpanSnapshot(
                trace_id="trace_pytest_run",
                span_id="span_lookup",
                span_type="function",
                span_data={
                    "name": "lookup_account",
                    "input": '{"account_id":"A-100"}',
                    "output": '{"status":"active"}',
                },
            )
        ],
    )
    snapshot_path.write_text(snapshot.model_dump_json(indent=2), encoding="utf-8")

    write_run_manifest(
        run_dir=run_dir,
        run_id="run-123",
        snapshots=[snapshot_path],
        policies_by_node={"tests/test_support.py::test_lookup": POLICY},
    )
    pointer = write_latest_pointer(run_dir.parent, run_dir)

    _, manifest = load_run_manifest(pointer)
    assert manifest.run_id == "run-123"
    assert manifest.traces[0].pytest_node_id == "tests/test_support.py::test_lookup"
    assert manifest.traces[0].policy_id == "openai_function_tools"
    assert (run_dir / manifest.traces[0].policy).is_file()

    report = check_run(pointer)
    assert report.summary.trace_count == 1
    assert report.summary.passed == 1


def test_manifest_rejects_trace_without_policy_assignment(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    snapshot_path = run_dir / "traces" / "trace.openai-agents.json"
    snapshot_path.parent.mkdir(parents=True)
    snapshot = OpenAITraceSnapshot(
        trace_id="trace_without_policy",
        workflow_name="Workflow",
        metadata={"pytest_node_id": "tests/test_agent.py::test_agent"},
    )
    snapshot_path.write_text(snapshot.model_dump_json(indent=2), encoding="utf-8")

    with pytest.raises(PytestRunError, match="no AgentLint policy matched"):
        write_run_manifest(
            run_dir=run_dir,
            run_id="run",
            snapshots=[snapshot_path],
            policies_by_node={},
        )
