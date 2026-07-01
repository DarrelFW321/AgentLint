"""Native JSON trace loading for AgentLint IR v1."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from agentlint.ir.v1.models import Trace


class TraceLoadError(Exception):
    """Base class for native trace loading errors."""


class TraceFileError(TraceLoadError):
    """Raised when a trace file cannot be read."""


class TraceJsonError(TraceLoadError):
    """Raised when a trace file is not valid JSON."""


class TraceSchemaError(TraceLoadError):
    """Raised when a trace file is JSON but not valid AgentLint IR v1."""

    def __init__(self, validation_error: ValidationError) -> None:
        super().__init__("trace schema validation failed")
        self.validation_error = validation_error


def load_native_trace(path: str | Path) -> Trace:
    """Load a native AgentLint IR v1 trace from a JSON file."""
    trace_path = Path(path)

    try:
        raw_text = trace_path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise TraceFileError(f"trace file not found: {trace_path}") from exc
    except IsADirectoryError as exc:
        raise TraceFileError(f"trace path is a directory, not a file: {trace_path}") from exc
    except OSError as exc:
        raise TraceFileError(f"could not read trace file {trace_path}: {exc}") from exc

    try:
        raw_data = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        message = f"malformed JSON at line {exc.lineno}, column {exc.colno}: {exc.msg}"
        raise TraceJsonError(message) from exc

    try:
        return Trace.model_validate(raw_data)
    except ValidationError as exc:
        raise TraceSchemaError(exc) from exc


def format_validation_error(error: ValidationError) -> list[str]:
    """Format Pydantic validation errors without echoing raw trace values."""
    formatted_errors: list[str] = []

    for item in error.errors(include_url=False, include_input=False):
        location = _format_location(item.get("loc", ()))
        message = item.get("msg", "validation error")
        error_type = item.get("type", "unknown")
        formatted_errors.append(f"{location}: {message} [{error_type}]")

    return formatted_errors


def _format_location(location: Any) -> str:
    if not isinstance(location, tuple) or not location:
        return "<root>"

    parts: list[str] = []
    for item in location:
        if isinstance(item, int):
            if parts:
                parts[-1] = f"{parts[-1]}[{item}]"
            else:
                parts.append(f"[{item}]")
        else:
            parts.append(str(item))

    return ".".join(parts)
