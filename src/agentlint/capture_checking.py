"""Check captured traces without writing intermediate native files."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from agentlint.adapters.openai_agents import import_openai_agents_file
from agentlint.adapters.openai_snapshot import (
    OPENAI_SNAPSHOT_SCHEMA_VERSION,
    OpenAISnapshotError,
)
from agentlint.adapters.opentelemetry import (
    OpenTelemetryImportError,
    import_opentelemetry_file,
)
from agentlint.checking import (
    InputError,
    InputErrorKind,
    TraceCheckResult,
    check_trace,
    check_trace_file,
    invalid_trace_result,
)
from agentlint.ir.v1 import SCHEMA_VERSION
from agentlint.policy import Policy
from agentlint.reports import AgentLintReport, FailOn, build_report


class CaptureCheckError(Exception):
    """Raised when a capture path cannot be discovered."""


def check_capture(
    path: str | Path,
    *,
    policy: Policy,
    fail_on: FailOn = FailOn.ERROR,
) -> AgentLintReport:
    """Detect and check every supported JSON trace at a file or directory path."""
    capture_files = discover_capture_files(path)
    results = [_check_capture_file(item, policy) for item in capture_files]
    return build_report(results, fail_on=fail_on)


def discover_capture_files(path: str | Path) -> list[Path]:
    """Return one file or the direct JSON children of a capture directory."""
    capture_path = Path(path)
    if capture_path.is_file():
        return [capture_path]
    if not capture_path.exists():
        raise CaptureCheckError(f"capture path not found: {capture_path}")
    if not capture_path.is_dir():
        raise CaptureCheckError(f"capture path is not a file or directory: {capture_path}")
    files = sorted(item for item in capture_path.glob("*.json") if item.is_file())
    if not files:
        raise CaptureCheckError(f"capture directory contains no JSON files: {capture_path}")
    return files


def _check_capture_file(path: Path, policy: Policy) -> TraceCheckResult:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return invalid_trace_result(
            path,
            InputError(
                kind=InputErrorKind.JSON,
                message=(f"malformed capture JSON at line {exc.lineno}, column {exc.colno}"),
            ),
            policy,
        )
    except OSError as exc:
        return invalid_trace_result(
            path,
            InputError(kind=InputErrorKind.FILE, message=f"could not read capture: {exc}"),
            policy,
        )

    capture_format = _detect_format(raw)
    try:
        if capture_format == "openai_agents":
            imported = import_openai_agents_file(path)
            return check_trace(imported.trace, policy=policy, trace_path=str(path))
        if capture_format == "opentelemetry":
            imported = import_opentelemetry_file(path)
            return check_trace(imported.trace, policy=policy, trace_path=str(path))
        if capture_format == "native":
            return check_trace_file(path, policy=policy)
    except (OpenAISnapshotError, OpenTelemetryImportError) as exc:
        return invalid_trace_result(
            path,
            InputError(kind=InputErrorKind.SCHEMA, message=str(exc)),
            policy,
        )

    return invalid_trace_result(
        path,
        InputError(
            kind=InputErrorKind.SCHEMA,
            message="unsupported capture JSON format",
        ),
        policy,
    )


def _detect_format(raw: Any) -> str | None:
    if not isinstance(raw, dict):
        return None
    schema_version = raw.get("schema_version")
    if schema_version == OPENAI_SNAPSHOT_SCHEMA_VERSION:
        return "openai_agents"
    if schema_version == SCHEMA_VERSION:
        return "native"
    if "resourceSpans" in raw:
        return "opentelemetry"
    return None
