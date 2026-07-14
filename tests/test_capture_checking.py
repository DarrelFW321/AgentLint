import shutil
from pathlib import Path

import pytest

from agentlint.adapters.openai_snapshot import (
    OpenAISpanSnapshot,
    OpenAITraceSnapshot,
)
from agentlint.capture_checking import (
    CaptureCheckError,
    check_capture,
    discover_capture_files,
)
from agentlint.policy import load_policy

ROOT = Path(__file__).resolve().parents[1]
POLICY = ROOT / "examples" / "policies" / "openai_function_tools.yaml"


def test_discover_capture_files_accepts_file_and_directory(tmp_path: Path) -> None:
    first = tmp_path / "a.json"
    second = tmp_path / "b.json"
    ignored = tmp_path / "notes.txt"
    for path in (first, second, ignored):
        path.write_text("{}", encoding="utf-8")

    assert discover_capture_files(first) == [first]
    assert discover_capture_files(tmp_path) == [first, second]


def test_discover_capture_files_rejects_missing_or_empty_directory(tmp_path: Path) -> None:
    with pytest.raises(CaptureCheckError, match="capture path not found"):
        discover_capture_files(tmp_path / "missing")

    empty = tmp_path / "empty"
    empty.mkdir()
    with pytest.raises(CaptureCheckError, match="contains no JSON files"):
        discover_capture_files(empty)


def test_check_capture_detects_openai_otel_and_native_files(tmp_path: Path) -> None:
    snapshot = OpenAITraceSnapshot(
        trace_id="trace_capture_openai",
        workflow_name="Capture workflow",
        sdk_version="0.18.1",
        spans=[
            OpenAISpanSnapshot(
                trace_id="trace_capture_openai",
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
    (tmp_path / "openai.json").write_text(snapshot.model_dump_json(indent=2), encoding="utf-8")
    shutil.copyfile(
        ROOT / "examples" / "external" / "opentelemetry" / "passing_tool_flow.json",
        tmp_path / "otel.json",
    )
    shutil.copyfile(
        ROOT / "examples" / "traces" / "policy_tool_valid.json",
        tmp_path / "native.json",
    )

    report = check_capture(tmp_path, policy=load_policy(POLICY))

    assert report.summary.trace_count == 3
    assert report.summary.passed == 3


def test_check_capture_reports_malformed_and_unknown_json_as_invalid(tmp_path: Path) -> None:
    (tmp_path / "malformed.json").write_text("{", encoding="utf-8")
    (tmp_path / "unknown.json").write_text('{"kind":"unknown"}', encoding="utf-8")

    report = check_capture(tmp_path, policy=load_policy(POLICY))

    assert report.summary.trace_count == 2
    assert report.summary.invalid == 2
    assert {run.input_error.message for run in report.runs if run.input_error} == {
        "malformed capture JSON at line 1, column 2",
        "unsupported capture JSON format",
    }
