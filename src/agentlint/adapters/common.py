"""Shared adapter models for external trace importers."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator

from agentlint.capture import CaptureCompleteness
from agentlint.ir.v1 import SourceRef, Trace


class AdapterWarning(BaseModel):
    """Warning emitted while importing an external trace."""

    model_config = ConfigDict(extra="forbid")

    code: str = Field(min_length=1)
    message: str = Field(min_length=1)
    source_ref: SourceRef | None = None


class AdapterResult(BaseModel):
    """Result of importing an external trace into AgentLint IR."""

    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    trace: Trace
    capture: CaptureCompleteness
    warnings: list[AdapterWarning] = Field(default_factory=list)

    @model_validator(mode="after")
    def capture_matches_trace(self) -> AdapterResult:
        if self.trace.capture != self.capture:
            raise ValueError("adapter capture must match the normalized trace capture")
        return self
