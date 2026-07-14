"""Versioned snapshots captured from the OpenAI Agents SDK."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from agentlint.ir.v1 import JsonValue

OPENAI_SNAPSHOT_SCHEMA_VERSION = "agentlint.openai_agents.snapshot.v1"


class OpenAISnapshotError(Exception):
    """Raised when an OpenAI Agents snapshot cannot be loaded."""


class StrictSnapshotModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class OpenAISpanSnapshot(StrictSnapshotModel):
    """Serializable public fields from one completed SDK span."""

    trace_id: str = Field(min_length=1)
    span_id: str = Field(min_length=1)
    parent_id: str | None = None
    started_at: str | None = None
    ended_at: str | None = None
    has_error: bool = False
    span_type: str = Field(min_length=1)
    span_data: dict[str, JsonValue] = Field(default_factory=dict)


class OpenAITraceSnapshot(StrictSnapshotModel):
    """Framework-neutral persisted capture of one SDK trace."""

    schema_version: Literal["agentlint.openai_agents.snapshot.v1"] = OPENAI_SNAPSHOT_SCHEMA_VERSION
    trace_id: str = Field(min_length=1)
    workflow_name: str = Field(min_length=1)
    group_id: str | None = None
    metadata: dict[str, JsonValue] = Field(default_factory=dict)
    started_at: str | None = None
    ended_at: str | None = None
    sdk_version: str | None = None
    spans: list[OpenAISpanSnapshot] = Field(default_factory=list)
    capture_incidents: list[str] = Field(default_factory=list)


def load_openai_snapshot(path: str | Path) -> OpenAITraceSnapshot:
    """Load and validate one OpenAI Agents snapshot JSON file."""
    snapshot_path = Path(path)
    try:
        raw = json.loads(snapshot_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise OpenAISnapshotError(f"OpenAI Agents snapshot not found: {snapshot_path}") from exc
    except json.JSONDecodeError as exc:
        raise OpenAISnapshotError(
            f"malformed OpenAI Agents snapshot JSON at line {exc.lineno}, column {exc.colno}"
        ) from exc
    except OSError as exc:
        raise OpenAISnapshotError(f"could not read OpenAI Agents snapshot: {exc}") from exc

    try:
        return OpenAITraceSnapshot.model_validate(raw)
    except ValidationError as exc:
        details = "; ".join(
            ".".join(str(item) for item in error["loc"]) + f": {error['msg']}"
            for error in exc.errors(include_input=False, include_url=False)
        )
        raise OpenAISnapshotError(f"invalid OpenAI Agents snapshot: {details}") from exc


def snapshot_from_data(raw_data: Any) -> OpenAITraceSnapshot:
    """Validate snapshot-compatible data supplied in memory."""
    try:
        return OpenAITraceSnapshot.model_validate(raw_data)
    except ValidationError as exc:
        raise OpenAISnapshotError("invalid OpenAI Agents snapshot") from exc
