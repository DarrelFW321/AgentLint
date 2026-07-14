"""Models describing which execution evidence a trace captured."""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

CAPTURE_SCHEMA_VERSION = "agentlint.capture.v1"


class CaptureStatus(StrEnum):
    """Confidence that a policy-relevant capability was captured."""

    CAPTURED = "captured"
    PARTIAL = "partial"
    UNAVAILABLE = "unavailable"
    UNKNOWN = "unknown"


class CaptureCapability(StrEnum):
    """Policy-relevant execution capabilities tracked in capture v1."""

    AGENT_RUNS = "agent_runs"
    MODEL_CALLS = "model_calls"
    TOOL_CALLS = "tool_calls"
    TOOL_ARGUMENTS = "tool_arguments"
    TOOL_RESULTS = "tool_results"
    APPROVALS = "approvals"
    DATA_FLOW = "data_flow"
    PROVENANCE = "provenance"
    FINAL_ANSWERS = "final_answers"


class StrictCaptureModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CapabilityCoverage(StrictCaptureModel):
    """Capture state and a sanitized structural explanation."""

    status: CaptureStatus
    reason: str | None = Field(default=None, min_length=1, max_length=240)

    @field_validator("reason")
    @classmethod
    def reason_must_be_single_line(cls, value: str | None) -> str | None:
        if value is not None and any(ord(character) < 32 for character in value):
            raise ValueError("reason must be single-line text without control characters")
        return value


class CaptureCapabilities(StrictCaptureModel):
    """Fixed capture capability set for agentlint.capture.v1."""

    agent_runs: CapabilityCoverage
    model_calls: CapabilityCoverage
    tool_calls: CapabilityCoverage
    tool_arguments: CapabilityCoverage
    tool_results: CapabilityCoverage
    approvals: CapabilityCoverage
    data_flow: CapabilityCoverage
    provenance: CapabilityCoverage
    final_answers: CapabilityCoverage

    def entries(self) -> list[tuple[CaptureCapability, CapabilityCoverage]]:
        """Return capability entries in stable report order."""
        return [(capability, getattr(self, capability.value)) for capability in CaptureCapability]


class CaptureCompleteness(StrictCaptureModel):
    """Versioned declaration of evidence captured for one trace."""

    schema_version: Literal["agentlint.capture.v1"] = CAPTURE_SCHEMA_VERSION
    adapter: str = Field(min_length=1, max_length=80)
    adapter_version: str | None = Field(default=None, min_length=1, max_length=80)
    framework: str | None = Field(default=None, min_length=1, max_length=80)
    framework_version: str | None = Field(default=None, min_length=1, max_length=80)
    capabilities: CaptureCapabilities
    notes: list[str] = Field(default_factory=list, max_length=20)

    @field_validator("notes")
    @classmethod
    def notes_must_be_sanitized(cls, values: list[str]) -> list[str]:
        for value in values:
            if not value or len(value) > 240 or any(ord(character) < 32 for character in value):
                raise ValueError(
                    "notes must be non-empty single-line text of at most 240 characters"
                )
        return values

    @property
    def overall_status(self) -> CaptureStatus:
        """Derive a conservative aggregate state for report scanning."""
        statuses = {coverage.status for _, coverage in self.capabilities.entries()}
        for status in (
            CaptureStatus.UNKNOWN,
            CaptureStatus.UNAVAILABLE,
            CaptureStatus.PARTIAL,
        ):
            if status in statuses:
                return status
        return CaptureStatus.CAPTURED


def unknown_capture(
    *, adapter: str = "unknown", reason: str = "No capture declaration was provided."
) -> CaptureCompleteness:
    """Build an all-unknown profile for undeclared or unreadable traces."""
    coverage = {
        capability.value: CapabilityCoverage(status=CaptureStatus.UNKNOWN, reason=reason)
        for capability in CaptureCapability
    }
    return CaptureCompleteness(
        adapter=adapter,
        capabilities=CaptureCapabilities.model_validate(coverage),
    )
