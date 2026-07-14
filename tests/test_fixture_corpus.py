import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest
import yaml

from agentlint.checking import TraceCheckResult, check_trace_file
from agentlint.diagnostics import DiagnosticCode
from agentlint.policy import Policy, load_policy
from agentlint.reports import FailOn, build_report, render_json_report, render_text_report

ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "examples" / "fixtures" / "manifest.yaml"
MULTI_TRACE_EXPECTED_REPORT = (
    ROOT / "examples" / "expected_reports" / ("multi_policy_unknown_missing_approval.json")
)


@dataclass(frozen=True)
class FixtureCase:
    id: str
    trace: Path
    policy: Path | None
    categories: tuple[str, ...]
    expected_status: str
    expected_diagnostics: tuple[DiagnosticCode, ...]
    expected_report: Path | None
    report_cases: tuple[str, ...]
    redaction_forbidden_strings: tuple[str, ...]
    performance: bool
    report_fail_on: FailOn


def load_fixture_cases() -> list[FixtureCase]:
    raw = yaml.safe_load(MANIFEST_PATH.read_text())
    assert isinstance(raw, dict), "fixture manifest must be a mapping"
    assert raw.get("version") == 1, "fixture manifest version must be 1"
    fixtures = raw.get("fixtures")
    assert isinstance(fixtures, list), "fixture manifest must contain a fixture list"

    cases = [_parse_fixture(entry) for entry in fixtures]
    ids = [case.id for case in cases]
    assert len(ids) == len(set(ids)), "fixture manifest contains duplicate ids"
    return cases


def _parse_fixture(entry: Any) -> FixtureCase:
    assert isinstance(entry, dict), "fixture entries must be mappings"
    fixture_id = _required_str(entry, "id")
    trace = _required_path(entry, "trace")
    policy = _optional_path(entry, "policy")
    expected_report = _optional_path(entry, "expected_report")

    categories = _string_tuple(entry.get("categories", ()), f"{fixture_id}.categories")
    expected_status = _required_str(entry, "expected_status")
    assert expected_status in {"passed", "failed", "not_verifiable", "invalid"}, (
        f"{fixture_id}.expected_status must be passed, failed, not_verifiable, or invalid"
    )

    report_cases = _string_tuple(entry.get("report_cases", ()), f"{fixture_id}.report_cases")
    forbidden = _string_tuple(
        entry.get("redaction_forbidden_strings", ()),
        f"{fixture_id}.redaction_forbidden_strings",
    )
    expected_diagnostics = tuple(
        DiagnosticCode(code)
        for code in _string_tuple(
            entry.get("expected_diagnostics", ()),
            f"{fixture_id}.expected_diagnostics",
        )
    )
    report_fail_on = FailOn(entry.get("report_fail_on", FailOn.ERROR.value))

    assert (ROOT / trace).is_file(), f"{fixture_id}.trace does not exist: {trace}"
    if policy is not None:
        assert (ROOT / policy).is_file(), f"{fixture_id}.policy does not exist: {policy}"
    if expected_report is not None:
        assert (ROOT / expected_report).is_file(), (
            f"{fixture_id}.expected_report does not exist: {expected_report}"
        )

    return FixtureCase(
        id=fixture_id,
        trace=trace,
        policy=policy,
        categories=categories,
        expected_status=expected_status,
        expected_diagnostics=expected_diagnostics,
        expected_report=expected_report,
        report_cases=report_cases,
        redaction_forbidden_strings=forbidden,
        performance=bool(entry.get("performance", False)),
        report_fail_on=report_fail_on,
    )


def _required_str(entry: dict[str, Any], key: str) -> str:
    value = entry.get(key)
    assert isinstance(value, str) and value, f"fixture entry requires string field {key}"
    return value


def _required_path(entry: dict[str, Any], key: str) -> Path:
    return Path(_required_str(entry, key))


def _optional_path(entry: dict[str, Any], key: str) -> Path | None:
    value = entry.get(key)
    if value is None:
        return None
    assert isinstance(value, str) and value, f"optional field {key} must be a string"
    return Path(value)


def _string_tuple(value: Any, field: str) -> tuple[str, ...]:
    assert isinstance(value, list | tuple), f"{field} must be a list"
    assert all(isinstance(item, str) and item for item in value), (
        f"{field} must contain only non-empty strings"
    )
    return tuple(value)


FIXTURES = load_fixture_cases()


def _policy_for(case: FixtureCase) -> Policy | None:
    if case.policy is None:
        return None
    return load_policy(ROOT / case.policy)


def _check(case: FixtureCase) -> TraceCheckResult:
    return check_trace_file(ROOT / case.trace, policy=_policy_for(case))


def _report_for(case: FixtureCase):
    return build_report([_check(case)], fail_on=case.report_fail_on)


def _normalize_report(value: dict[str, Any]) -> dict[str, Any]:
    normalized = json.loads(json.dumps(value))
    for run in normalized.get("runs", []):
        trace_path = run.get("trace_path")
        if isinstance(trace_path, str):
            run["trace_path"] = _normalize_path(trace_path)
    return normalized


def _normalize_path(path: str) -> str:
    parsed = Path(path)
    if parsed.is_absolute():
        try:
            return parsed.resolve().relative_to(ROOT).as_posix()
        except ValueError:
            return parsed.as_posix()
    return path.replace("\\", "/")


def _normalized_json_report(report) -> dict[str, Any]:
    return _normalize_report(json.loads(render_json_report(report)))


@pytest.mark.parametrize("case", FIXTURES, ids=[case.id for case in FIXTURES])
def test_fixture_manifest_entries_emit_expected_results(case: FixtureCase) -> None:
    result = _check(case)

    assert result.status.value == case.expected_status
    assert tuple(diagnostic.code for diagnostic in result.diagnostics) == case.expected_diagnostics


def test_fixture_manifest_covers_every_diagnostic_code() -> None:
    covered = {
        diagnostic_code for case in FIXTURES for diagnostic_code in case.expected_diagnostics
    }

    assert covered == set(DiagnosticCode)


@pytest.mark.parametrize(
    "case",
    [case for case in FIXTURES if case.expected_report is not None],
    ids=[case.id for case in FIXTURES if case.expected_report is not None],
)
def test_json_expected_reports_match_fixture_outputs(case: FixtureCase) -> None:
    generated = _normalized_json_report(_report_for(case))
    expected = _normalize_report(json.loads((ROOT / case.expected_report).read_text()))

    assert generated == expected


def test_multi_trace_json_expected_report_matches_output() -> None:
    policy = load_policy(ROOT / "examples" / "policies" / "policy_checks.yaml")
    results = [
        check_trace_file(ROOT / "examples" / "traces" / "policy_unknown_tool.json", policy=policy),
        check_trace_file(
            ROOT / "examples" / "traces" / "policy_missing_approval.json", policy=policy
        ),
    ]
    report = build_report(results, fail_on=FailOn.NEVER)

    generated = _normalized_json_report(report)
    expected = _normalize_report(json.loads(MULTI_TRACE_EXPECTED_REPORT.read_text()))

    assert generated == expected


@pytest.mark.parametrize(
    "case",
    [case for case in FIXTURES if "text" in case.report_cases],
    ids=[case.id for case in FIXTURES if "text" in case.report_cases],
)
def test_text_report_key_lines_are_stable(case: FixtureCase) -> None:
    rendered = render_text_report(_report_for(case))

    assert "AgentLint Report" in rendered
    assert f"fail-on: {case.report_fail_on.value}" in rendered
    assert f"status: {case.expected_status}" in rendered
    assert case.trace.name in rendered
    for diagnostic_code in case.expected_diagnostics:
        assert f"[{diagnostic_code.value}]" in rendered


@pytest.mark.parametrize(
    "case",
    [case for case in FIXTURES if case.expected_report is not None],
    ids=[case.id for case in FIXTURES if case.expected_report is not None],
)
def test_reports_are_deterministic(case: FixtureCase) -> None:
    first = _report_for(case)
    second = _report_for(case)

    assert _normalized_json_report(first) == _normalized_json_report(second)
    assert render_text_report(first) == render_text_report(second)


@pytest.mark.parametrize(
    "case",
    [case for case in FIXTURES if case.redaction_forbidden_strings],
    ids=[case.id for case in FIXTURES if case.redaction_forbidden_strings],
)
def test_reports_omit_manifest_forbidden_redaction_strings(case: FixtureCase) -> None:
    report = _report_for(case)
    text_report = render_text_report(report)
    json_report = render_json_report(report)

    assert report.redaction.mode == "metadata_only"
    assert report.redaction.raw_values_included is False
    for forbidden in case.redaction_forbidden_strings:
        assert forbidden not in text_report
        assert forbidden not in json_report


@pytest.mark.performance
def test_fixture_corpus_performance_smoke() -> None:
    performance_cases = [case for case in FIXTURES if case.performance]
    assert len(performance_cases) >= 8

    started_at = time.perf_counter()
    results = [_check(case) for case in performance_cases]
    elapsed_seconds = time.perf_counter() - started_at

    assert len(results) == len(performance_cases)
    assert elapsed_seconds < 10
