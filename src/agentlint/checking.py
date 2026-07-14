"""Shared trace checking execution for AgentLint."""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from agentlint.capture import CaptureCompleteness, unknown_capture
from agentlint.diagnostics import Diagnostic, Severity
from agentlint.evidence import EvidenceAssessment, assess_evidence
from agentlint.ir.v1 import (
    Trace,
    TraceFileError,
    TraceJsonError,
    TraceLoadError,
    TraceSchemaError,
    format_validation_error,
    load_native_trace,
)
from agentlint.passes import evaluate_policy, validate_structure
from agentlint.policy import Policy, compile_policy


class TraceCheckStatus(StrEnum):
    """Status for one checked trace input."""

    PASSED = "passed"
    FAILED = "failed"
    NOT_VERIFIABLE = "not_verifiable"
    INVALID = "invalid"


class InputErrorKind(StrEnum):
    """Trace input error categories represented in reports."""

    FILE = "file"
    JSON = "json"
    SCHEMA = "schema"


class InputError(BaseModel):
    """Sanitized trace input error for reports."""

    model_config = ConfigDict(extra="forbid")

    kind: InputErrorKind
    message: str = Field(min_length=1)
    details: list[str] = Field(default_factory=list)


class TraceCheckResult(BaseModel):
    """Result for one trace checked by AgentLint."""

    model_config = ConfigDict(extra="forbid")

    trace_path: str
    trace_id: str | None = None
    policy_id: str | None = None
    status: TraceCheckStatus
    events: int = Field(default=0, ge=0)
    edges: int = Field(default=0, ge=0)
    capture: CaptureCompleteness
    evidence: EvidenceAssessment
    diagnostics: list[Diagnostic] = Field(default_factory=list)
    input_error: InputError | None = None


def check_trace(
    trace: Trace, policy: Policy | None = None, trace_path: str = "<memory>"
) -> TraceCheckResult:
    """Run structural and optional policy checks for a parsed trace."""
    diagnostics = validate_structure(trace)
    structural_errors = [
        diagnostic for diagnostic in diagnostics if diagnostic.severity == Severity.ERROR
    ]

    plan = compile_policy(policy) if policy is not None else None
    if policy is not None and not structural_errors:
        diagnostics.extend(evaluate_policy(trace, policy, plan=plan))

    capture = trace.capture or unknown_capture(adapter="native")
    evidence = assess_evidence(policy, capture, plan=plan)
    status = (
        TraceCheckStatus.FAILED
        if diagnostics
        else TraceCheckStatus.NOT_VERIFIABLE
        if evidence.unmet
        else TraceCheckStatus.PASSED
    )

    return TraceCheckResult(
        trace_path=trace_path,
        trace_id=trace.trace_id,
        policy_id=policy.policy_id if policy is not None else None,
        status=status,
        events=len(trace.events),
        edges=len(trace.edges),
        capture=capture,
        evidence=evidence,
        diagnostics=diagnostics,
    )


def check_trace_file(path: str | Path, policy: Policy | None = None) -> TraceCheckResult:
    """Load and check one native trace file, representing input failures as results."""
    trace_path = Path(path)

    try:
        trace = load_native_trace(trace_path)
    except TraceSchemaError as exc:
        return _invalid_trace_result(
            trace_path,
            InputError(
                kind=InputErrorKind.SCHEMA,
                message=str(exc),
                details=format_validation_error(exc.validation_error),
            ),
            policy,
        )
    except TraceJsonError as exc:
        return _invalid_trace_result(
            trace_path,
            InputError(kind=InputErrorKind.JSON, message=str(exc)),
            policy,
        )
    except (TraceFileError, TraceLoadError) as exc:
        return _invalid_trace_result(
            trace_path,
            InputError(kind=InputErrorKind.FILE, message=str(exc)),
            policy,
        )

    return check_trace(trace, policy=policy, trace_path=str(trace_path))


def _invalid_trace_result(
    trace_path: Path,
    input_error: InputError,
    policy: Policy | None,
) -> TraceCheckResult:
    return TraceCheckResult(
        trace_path=str(trace_path),
        policy_id=policy.policy_id if policy is not None else None,
        status=TraceCheckStatus.INVALID,
        capture=unknown_capture(
            reason="Capture completeness is unknown because the trace could not be loaded."
        ),
        evidence=EvidenceAssessment(requirements=[], unmet=[]),
        input_error=input_error,
    )
