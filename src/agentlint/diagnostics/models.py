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
    UNKNOWN_TOOL = "UNKNOWN_TOOL"
    DENIED_TOOL_CALL = "DENIED_TOOL_CALL"
    UNAUTHORIZED_TOOL_CALL = "DENIED_TOOL_CALL"  # Legacy Python alias.
    DISALLOWED_TOOL_ARGUMENT = "DISALLOWED_TOOL_ARGUMENT"
    MISSING_APPROVAL = "MISSING_APPROVAL"
    APPROVAL_AFTER_ACTION = "APPROVAL_AFTER_ACTION"
    ACTION_AFTER_DENIAL = "ACTION_AFTER_DENIAL"
    APPROVAL_MISMATCH = "APPROVAL_MISMATCH"
    PRIVATE_TO_PUBLIC_SINK = "PRIVATE_TO_PUBLIC_SINK"
    SECRET_EXPOSURE = "SECRET_EXPOSURE"
    UNTRUSTED_TO_PRIVILEGED_ACTION = "UNTRUSTED_TO_PRIVILEGED_ACTION"
    SENSITIVE_FINAL_ANSWER = "SENSITIVE_FINAL_ANSWER"
    UNSUPPORTED_CLAIM = "UNSUPPORTED_CLAIM"
    INVALID_PROVENANCE_REFERENCE = "INVALID_PROVENANCE_REFERENCE"
    EVIDENCE_AFTER_CLAIM = "EVIDENCE_AFTER_CLAIM"


class DiagnosticPathNode(BaseModel):
    """Sanitized event reference in a diagnostic path."""

    model_config = ConfigDict(extra="forbid")

    event_id: str = Field(min_length=1)
    label: str = Field(min_length=1)


class DiagnosticPathEdge(BaseModel):
    """Explicit IR edge reference in a diagnostic path."""

    model_config = ConfigDict(extra="forbid")

    edge_id: str = Field(min_length=1)
    edge_type: str = Field(min_length=1)


class DiagnosticPath(BaseModel):
    """Deterministic path composed only of represented IR events and edges."""

    model_config = ConfigDict(extra="forbid")

    nodes: list[DiagnosticPathNode] = Field(min_length=2)
    edges: list[DiagnosticPathEdge] = Field(min_length=1)


class Diagnostic(BaseModel):
    """A structured AgentLint diagnostic."""

    model_config = ConfigDict(extra="forbid")

    code: DiagnosticCode
    severity: Severity = Severity.ERROR
    message: str = Field(min_length=1)
    related_events: list[str] = Field(default_factory=list)
    related_edges: list[str] = Field(default_factory=list)
    path: DiagnosticPath | None = None
    policy_reference: str | None = None
    remediation: str | None = None
