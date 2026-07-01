"""Pydantic models for the native AgentLint IR v1 trace format."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, RootModel

SCHEMA_VERSION = "agentlint.ir.v1"

type JsonValue = str | int | float | bool | None | list[JsonValue] | dict[str, JsonValue]
type EdgeType = Literal["parent", "data_flow", "approval_for", "provenance"]
type ReferenceId = Annotated[str, Field(min_length=1)]


class StrictModel(BaseModel):
    """Base model for IR objects with explicit extension fields."""

    model_config = ConfigDict(extra="forbid")


class TraceMetadata(RootModel[dict[str, JsonValue]]):
    """Top-level trace metadata."""

    root: dict[str, JsonValue] = Field(default_factory=dict)

    def __getitem__(self, key: str) -> JsonValue:
        return self.root[key]

    def __iter__(self):
        return iter(self.root)

    def __len__(self) -> int:
        return len(self.root)

    def get(self, key: str, default: JsonValue = None) -> JsonValue:
        return self.root.get(key, default)


class SourceRef(StrictModel):
    """Stable pointer back to source trace data."""

    source: str | None = None
    path: str | None = None
    line: int | None = Field(default=None, strict=True, ge=1)
    column: int | None = Field(default=None, strict=True, ge=1)
    raw_id: str | None = None


class Claim(StrictModel):
    """Minimal final-answer claim for future provenance checks."""

    id: str = Field(min_length=1)
    text: str = Field(min_length=1)
    evidence: list[ReferenceId] = Field(default_factory=list)
    metadata: dict[str, JsonValue] = Field(default_factory=dict)
    source_ref: SourceRef | None = None


class EventBase(StrictModel):
    """Common event fields shared by all AgentLint IR v1 events."""

    id: str = Field(min_length=1)
    sequence: int = Field(strict=True, ge=0)
    timestamp: str | None = None
    actor: str | None = None
    metadata: dict[str, JsonValue] = Field(default_factory=dict)
    source_ref: SourceRef | None = None


class UserMessageEvent(EventBase):
    """User message event."""

    type: Literal["user_message"]
    content: str = Field(min_length=1)


class DeveloperInstructionEvent(EventBase):
    """Developer instruction event."""

    type: Literal["developer_instruction"]
    content: str = Field(min_length=1)


class ModelCallEvent(EventBase):
    """Model call event."""

    type: Literal["model_call"]
    input: JsonValue
    output: JsonValue = None
    model: str | None = None


class ToolCallEvent(EventBase):
    """Tool call event."""

    type: Literal["tool_call"]
    tool_name: str = Field(min_length=1)
    arguments: dict[str, JsonValue] | None = None


class ToolResultEvent(EventBase):
    """Tool result event."""

    type: Literal["tool_result"]
    tool_name: str = Field(min_length=1)
    call_id: ReferenceId | None = None
    result: JsonValue


class ApprovalEvent(EventBase):
    """Approval or denial event."""

    type: Literal["approval"]
    decision: Literal["approved", "denied"]
    subject_event: ReferenceId | None = None
    approved_by: str | None = None
    reason: str | None = None


class FinalAnswerEvent(EventBase):
    """Final answer event."""

    type: Literal["final_answer"]
    content: str = Field(min_length=1)
    claims: list[Claim] = Field(default_factory=list)


Event = Annotated[
    UserMessageEvent
    | DeveloperInstructionEvent
    | ModelCallEvent
    | ToolCallEvent
    | ToolResultEvent
    | ApprovalEvent
    | FinalAnswerEvent,
    Field(discriminator="type"),
]


class Edge(StrictModel):
    """Relationship between two events in an AgentLint trace."""

    id: str = Field(min_length=1)
    type: EdgeType
    from_event: str = Field(min_length=1)
    to_event: str = Field(min_length=1)
    metadata: dict[str, JsonValue] = Field(default_factory=dict)
    source_ref: SourceRef | None = None


class Trace(StrictModel):
    """Native AgentLint IR v1 trace."""

    schema_version: Literal["agentlint.ir.v1"]
    trace_id: str = Field(min_length=1)
    metadata: TraceMetadata = Field(default_factory=TraceMetadata)
    events: list[Event]
    edges: list[Edge] = Field(default_factory=list)
