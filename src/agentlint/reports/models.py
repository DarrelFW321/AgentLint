"""Report models for AgentLint check results."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from agentlint.checking import TraceCheckResult, TraceCheckStatus
from agentlint.diagnostics import Severity
from agentlint.version import __version__

REPORT_SCHEMA_VERSION = "agentlint.report.v1"


class FailOn(StrEnum):
    """Diagnostic threshold that should fail a check run."""

    ERROR = "error"
    WARNING = "warning"
    INFO = "info"
    NEVER = "never"


class ReportFormat(StrEnum):
    """Supported check report output formats."""

    TEXT = "text"
    JSON = "json"


class SeverityCounts(BaseModel):
    """Counts by diagnostic severity."""

    model_config = ConfigDict(extra="forbid")

    error: int = Field(default=0, ge=0)
    warning: int = Field(default=0, ge=0)
    info: int = Field(default=0, ge=0)


class ReportSummary(BaseModel):
    """Summary for an AgentLint report."""

    model_config = ConfigDict(extra="forbid")

    trace_count: int = Field(ge=0)
    passed: int = Field(ge=0)
    failed: int = Field(ge=0)
    invalid: int = Field(ge=0)
    diagnostics: SeverityCounts
    fail_on: FailOn
    failed_threshold: bool


class RedactionInfo(BaseModel):
    """Report redaction metadata."""

    model_config = ConfigDict(extra="forbid")

    mode: str = "metadata_only"
    raw_values_included: bool = False


class AgentLintReport(BaseModel):
    """Versioned AgentLint check report."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = REPORT_SCHEMA_VERSION
    agentlint_version: str = __version__
    summary: ReportSummary
    runs: list[TraceCheckResult]
    redaction: RedactionInfo = Field(default_factory=RedactionInfo)


def build_report(
    results: list[TraceCheckResult],
    fail_on: FailOn = FailOn.ERROR,
) -> AgentLintReport:
    """Build a versioned report from checked trace results."""
    diagnostics = _severity_counts(results)
    summary = ReportSummary(
        trace_count=len(results),
        passed=sum(1 for result in results if result.status == TraceCheckStatus.PASSED),
        failed=sum(1 for result in results if result.status == TraceCheckStatus.FAILED),
        invalid=sum(1 for result in results if result.status == TraceCheckStatus.INVALID),
        diagnostics=diagnostics,
        fail_on=fail_on,
        failed_threshold=threshold_failed(diagnostics, fail_on),
    )

    return AgentLintReport(summary=summary, runs=results)


def report_should_fail(report: AgentLintReport) -> bool:
    """Return whether a report should produce a non-zero process exit."""
    return report.summary.invalid > 0 or report.summary.failed_threshold


def threshold_failed(counts: SeverityCounts, fail_on: FailOn) -> bool:
    """Evaluate whether severity counts fail a configured threshold."""
    match fail_on:
        case FailOn.ERROR:
            return counts.error > 0
        case FailOn.WARNING:
            return counts.error > 0 or counts.warning > 0
        case FailOn.INFO:
            return counts.error > 0 or counts.warning > 0 or counts.info > 0
        case FailOn.NEVER:
            return False


def _severity_counts(results: list[TraceCheckResult]) -> SeverityCounts:
    counts = SeverityCounts()

    for result in results:
        for diagnostic in result.diagnostics:
            match diagnostic.severity:
                case Severity.ERROR:
                    counts.error += 1
                case Severity.WARNING:
                    counts.warning += 1
                case Severity.INFO:
                    counts.info += 1

    return counts
