"""Diagnostic models for AgentLint findings."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class Severity(StrEnum):
    """Diagnostic severity levels."""

    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class DiagnosticCode(StrEnum):
    """Stable AgentLint diagnostic codes."""

    DUPLICATE_EVENT_ID = "DUPLICATE_EVENT_ID"
    DUPLICATE_EDGE_ID = "DUPLICATE_EDGE_ID"
    MISSING_EVENT_REFERENCE = "MISSING_EVENT_REFERENCE"
    TOOL_RESULT_WITHOUT_MATCHING_CALL = "TOOL_RESULT_WITHOUT_MATCHING_CALL"
    TOOL_CALL_MISSING_ARGUMENTS = "TOOL_CALL_MISSING_ARGUMENTS"
    INVALID_EVENT_ORDER = "INVALID_EVENT_ORDER"
    INVALID_EVIDENCE_REFERENCE = "INVALID_EVIDENCE_REFERENCE"


class Diagnostic(BaseModel):
    """A structured AgentLint diagnostic."""

    model_config = ConfigDict(extra="forbid")

    code: DiagnosticCode
    severity: Severity = Severity.ERROR
    message: str = Field(min_length=1)
    related_events: list[str] = Field(default_factory=list)
    related_edges: list[str] = Field(default_factory=list)
    policy_reference: str | None = None
    remediation: str | None = None
