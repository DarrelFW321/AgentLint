import json
from pathlib import Path

import pytest

from agentlint.checking import check_trace_file
from agentlint.policy import load_policy
from agentlint.reports import (
    REPORT_SCHEMA_VERSION,
    FailOn,
    build_report,
    render_json_report,
    render_text_report,
    report_should_fail,
    threshold_failed,
)
from agentlint.reports.models import SeverityCounts

TRACE_DIR = Path(__file__).resolve().parents[1] / "examples" / "traces"
POLICY_DIR = Path(__file__).resolve().parents[1] / "examples" / "policies"
EXPECTED_REPORT_DIR = Path(__file__).resolve().parents[1] / "examples" / "expected_reports"


def policy_checks():
    return load_policy(POLICY_DIR / "policy_checks.yaml")


def test_build_report_counts_results_and_diagnostics() -> None:
    policy = policy_checks()
    results = [
        check_trace_file(TRACE_DIR / "policy_tool_valid.json", policy=policy),
        check_trace_file(TRACE_DIR / "policy_unknown_tool.json", policy=policy),
        check_trace_file(TRACE_DIR / "native_invalid_schema.json", policy=policy),
    ]

    report = build_report(results, fail_on=FailOn.ERROR)

    assert report.schema_version == REPORT_SCHEMA_VERSION
    assert report.summary.trace_count == 3
    assert report.summary.passed == 1
    assert report.summary.failed == 1
    assert report.summary.invalid == 1
    assert report.summary.diagnostics.error == 1
    assert report.summary.diagnostics.warning == 0
    assert report.summary.failed_threshold is True
    assert report_should_fail(report) is True


@pytest.mark.parametrize(
    ("fail_on", "expected"),
    [
        (FailOn.ERROR, True),
        (FailOn.WARNING, True),
        (FailOn.INFO, True),
        (FailOn.NEVER, False),
    ],
)
def test_threshold_failed_for_error_counts(fail_on: FailOn, expected: bool) -> None:
    counts = SeverityCounts(error=1, warning=0, info=0)

    assert threshold_failed(counts, fail_on) is expected


@pytest.mark.parametrize(
    ("fail_on", "expected"),
    [
        (FailOn.ERROR, False),
        (FailOn.WARNING, True),
        (FailOn.INFO, True),
        (FailOn.NEVER, False),
    ],
)
def test_threshold_failed_for_warning_counts(fail_on: FailOn, expected: bool) -> None:
    counts = SeverityCounts(error=0, warning=1, info=0)

    assert threshold_failed(counts, fail_on) is expected


def test_render_text_report_includes_summary_and_diagnostics() -> None:
    policy = policy_checks()
    result = check_trace_file(TRACE_DIR / "policy_unknown_tool.json", policy=policy)
    report = build_report([result], fail_on=FailOn.ERROR)

    rendered = render_text_report(report)

    assert "AgentLint Report" in rendered
    assert "traces: 0 passed, 1 failed, 0 invalid" in rendered
    assert "diagnostics: 1 error, 0 warning, 0 info" in rendered
    assert "error[UNKNOWN_TOOL]" in rendered
    assert "policy reference: policy_checks_v1:unknown_tool" in rendered


def test_render_json_report_is_parseable_and_stable() -> None:
    policy = policy_checks()
    result = check_trace_file(TRACE_DIR / "policy_unknown_tool.json", policy=policy)
    report = build_report([result], fail_on=FailOn.ERROR)

    parsed = json.loads(render_json_report(report))
    expected = json.loads((EXPECTED_REPORT_DIR / "policy_unknown_tool.json").read_text())

    assert parsed["schema_version"] == expected["schema_version"]
    assert parsed["summary"] == expected["summary"]
    assert parsed["runs"][0]["status"] == expected["runs"][0]["status"]
    assert parsed["runs"][0]["diagnostics"] == expected["runs"][0]["diagnostics"]
    assert parsed["redaction"] == expected["redaction"]


def test_invalid_trace_result_renders_in_text_report() -> None:
    result = check_trace_file(TRACE_DIR / "native_invalid_schema.json")
    report = build_report([result], fail_on=FailOn.NEVER)

    rendered = render_text_report(report)

    assert "status: invalid" in rendered
    assert "input error[schema]: trace schema validation failed" in rendered


def test_reports_do_not_include_raw_trace_payloads() -> None:
    policy = policy_checks()
    result = check_trace_file(TRACE_DIR / "policy_private_to_public_sink.json", policy=policy)
    report = build_report([result], fail_on=FailOn.ERROR)

    text_report = render_text_report(report)
    json_report = render_json_report(report)

    assert "Customer profile details." not in text_report
    assert "customer profile details" not in text_report
    assert "Customer profile details." not in json_report
    assert "customer profile details" not in json_report
    assert report.redaction.raw_values_included is False
