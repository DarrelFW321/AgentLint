"""Pydantic models for AgentLint YAML policy v1."""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, field_validator, model_validator

from agentlint.capture import CaptureCapability
from agentlint.ir.v1 import JsonValue

POLICY_VERSION = 1


def _reject_blank(value: str) -> str:
    if not value.strip():
        raise ValueError("value must not be empty or whitespace")
    return value


type PolicyName = Annotated[str, Field(min_length=1), AfterValidator(_reject_blank)]
type NonEmptyText = Annotated[str, Field(min_length=1), AfterValidator(_reject_blank)]


class StrictPolicyModel(BaseModel):
    """Base model for policy objects with explicit extension fields."""

    model_config = ConfigDict(extra="forbid")


class ToolPermission(StrEnum):
    """Tool permission states."""

    ALLOWED = "allowed"
    DENIED = "denied"


class ApprovalRequirement(StrEnum):
    """Approval requirement states."""

    NOT_REQUIRED = "not_required"
    REQUIRED = "required"


class ToolRisk(StrEnum):
    """Policy-level tool risk labels."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class Sensitivity(StrEnum):
    """Source data sensitivity labels."""

    PUBLIC = "public"
    INTERNAL = "internal"
    PRIVATE = "private"
    SECRET = "secret"


class TrustLevel(StrEnum):
    """Source trust labels."""

    TRUSTED = "trusted"
    UNTRUSTED = "untrusted"
    UNKNOWN = "unknown"


class SinkVisibility(StrEnum):
    """Sink visibility labels."""

    MODEL = "model"
    INTERNAL = "internal"
    PRIVATE = "private"
    PUBLIC = "public"


class PolicySeverity(StrEnum):
    """Configurable policy rule severities."""

    OFF = "off"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class EvidenceRequirementLevel(StrEnum):
    """Minimum acceptable evidence coverage for a policy capability."""

    PARTIAL = "partial"
    CAPTURED = "captured"


class CaptureRequirements(StrictPolicyModel):
    """Explicit minimum capture requirements keyed by fixed capability names."""

    require: dict[CaptureCapability, EvidenceRequirementLevel] = Field(default_factory=dict)


class RuleId(StrEnum):
    """Stable policy rule identifiers."""

    UNKNOWN_TOOL = "unknown_tool"
    DENIED_TOOL_CALL = "denied_tool_call"
    UNAUTHORIZED_TOOL_CALL = "denied_tool_call"  # Legacy Python alias.
    DISALLOWED_TOOL_ARGUMENT = "disallowed_tool_argument"
    MISSING_APPROVAL = "missing_approval"
    APPROVAL_AFTER_ACTION = "approval_after_action"
    ACTION_AFTER_DENIAL = "action_after_denial"
    APPROVAL_MISMATCH = "approval_mismatch"
    PRIVATE_TO_PUBLIC_SINK = "private_to_public_sink"
    SECRET_EXPOSURE = "secret_exposure"
    UNTRUSTED_TO_PRIVILEGED_ACTION = "untrusted_to_privileged_action"
    SENSITIVE_FINAL_ANSWER = "sensitive_final_answer"
    UNSUPPORTED_CLAIM = "unsupported_claim"
    INVALID_PROVENANCE_REFERENCE = "invalid_provenance_reference"
    EVIDENCE_AFTER_CLAIM = "evidence_after_claim"


class ArgumentType(StrEnum):
    """Primitive JSON value types for shallow argument constraints."""

    STRING = "string"
    INTEGER = "integer"
    NUMBER = "number"
    BOOLEAN = "boolean"
    OBJECT = "object"
    ARRAY = "array"
    NULL = "null"


class ArgumentPolicy(StrictPolicyModel):
    """Policy constraints for one tool argument."""

    required: bool = False
    allowed_types: list[ArgumentType] | None = None
    allowed_values: list[JsonValue] | None = None
    sink: PolicyName | None = None
    visibility: SinkVisibility | None = None
    metadata: dict[str, JsonValue] = Field(default_factory=dict)

    @field_validator("allowed_types", "allowed_values")
    @classmethod
    def reject_empty_constraint_lists(cls, value: list[object] | None) -> list[object] | None:
        if value == []:
            raise ValueError("constraint list must not be empty when provided")
        return value

    @model_validator(mode="after")
    def visibility_requires_sink(self) -> Self:
        if self.visibility is not None and self.sink is None:
            raise ValueError("argument visibility requires a sink name")
        return self


class ToolResultBoundary(StrictPolicyModel):
    """Policy classification applied to an observed tool result."""

    source: PolicyName
    sensitivity: Sensitivity | None = None
    trust: TrustLevel | None = None


class ToolPolicy(StrictPolicyModel):
    """Policy for one named tool."""

    permission: ToolPermission = ToolPermission.ALLOWED
    approval: ApprovalRequirement = ApprovalRequirement.NOT_REQUIRED
    risk: ToolRisk = ToolRisk.LOW
    arguments: dict[PolicyName, ArgumentPolicy] = Field(default_factory=dict)
    result: ToolResultBoundary | None = None
    metadata: dict[str, JsonValue] = Field(default_factory=dict)


class SourcePolicy(StrictPolicyModel):
    """Policy for one named source."""

    sensitivity: Sensitivity = Sensitivity.INTERNAL
    trust: TrustLevel = TrustLevel.UNKNOWN
    metadata: dict[str, JsonValue] = Field(default_factory=dict)


class SinkPolicy(StrictPolicyModel):
    """Policy for one named sink."""

    visibility: SinkVisibility = SinkVisibility.INTERNAL
    metadata: dict[str, JsonValue] = Field(default_factory=dict)


class ExceptionMatch(StrictPolicyModel):
    """Policy exception match selector."""

    tool: PolicyName | None = None
    source: PolicyName | None = None
    sink: PolicyName | None = None
    event: PolicyName | None = None


class PolicyException(StrictPolicyModel):
    """Project-specific exception from one or more policy rules."""

    id: PolicyName
    rules: list[RuleId] = Field(min_length=1)
    reason: NonEmptyText
    expires: NonEmptyText | None = None
    match: ExceptionMatch = Field(default_factory=ExceptionMatch)


class Policy(StrictPolicyModel):
    """AgentLint YAML policy v1."""

    version: Literal[1]
    policy_id: PolicyName
    capture: CaptureRequirements = Field(default_factory=CaptureRequirements)
    metadata: dict[str, JsonValue] = Field(default_factory=dict)
    tools: dict[PolicyName, ToolPolicy] = Field(default_factory=dict)
    sources: dict[PolicyName, SourcePolicy] = Field(default_factory=dict)
    sinks: dict[PolicyName, SinkPolicy] = Field(default_factory=dict)
    rules: dict[RuleId, PolicySeverity] = Field(default_factory=dict)
    exceptions: list[PolicyException] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def migrate_legacy_rule_language(cls, value: object) -> object:
        """Accept the legacy authorization term while normalizing it away."""
        if not isinstance(value, dict):
            return value
        migrated = dict(value)
        rules = migrated.get("rules")
        if isinstance(rules, dict) and "unauthorized_tool_call" in rules:
            if "denied_tool_call" in rules:
                raise ValueError(
                    "policy cannot configure both denied_tool_call and legacy "
                    "unauthorized_tool_call"
                )
            migrated["rules"] = {
                ("denied_tool_call" if key == "unauthorized_tool_call" else key): item
                for key, item in rules.items()
            }
        exceptions = migrated.get("exceptions")
        if isinstance(exceptions, list):
            migrated_exceptions: list[object] = []
            for exception in exceptions:
                if not isinstance(exception, dict):
                    migrated_exceptions.append(exception)
                    continue
                migrated_exception = dict(exception)
                exception_rules = migrated_exception.get("rules")
                if isinstance(exception_rules, list):
                    migrated_exception["rules"] = [
                        "denied_tool_call" if rule == "unauthorized_tool_call" else rule
                        for rule in exception_rules
                    ]
                migrated_exceptions.append(migrated_exception)
            migrated["exceptions"] = migrated_exceptions
        return migrated

    @model_validator(mode="after")
    def reject_duplicate_exception_ids(self) -> Self:
        seen: set[str] = set()

        for policy_exception in self.exceptions:
            if policy_exception.id in seen:
                raise ValueError(f'duplicate exception id "{policy_exception.id}"')
            seen.add(policy_exception.id)

        return self

    def effective_sources(self) -> dict[str, SourcePolicy]:
        """Return global and inline tool-result source classifications."""
        result = dict(self.sources)
        for tool in self.tools.values():
            boundary = tool.result
            if boundary is None:
                continue
            inline = SourcePolicy(
                sensitivity=boundary.sensitivity or Sensitivity.INTERNAL,
                trust=boundary.trust or TrustLevel.UNKNOWN,
            )
            existing = result.get(boundary.source)
            if existing is None:
                result[boundary.source] = inline
                continue
            if boundary.sensitivity is not None and existing.sensitivity != boundary.sensitivity:
                raise ValueError(f'conflicting sensitivity for source "{boundary.source}"')
            if boundary.trust is not None and existing.trust != boundary.trust:
                raise ValueError(f'conflicting trust for source "{boundary.source}"')
        return result

    def effective_sinks(self) -> dict[str, SinkPolicy]:
        """Return global and inline tool-argument sink classifications."""
        result = dict(self.sinks)
        for tool in self.tools.values():
            for argument in tool.arguments.values():
                if argument.sink is None:
                    continue
                inline = SinkPolicy(visibility=argument.visibility or SinkVisibility.INTERNAL)
                existing = result.get(argument.sink)
                if existing is None:
                    result[argument.sink] = inline
                    continue
                if argument.visibility is not None and existing.visibility != argument.visibility:
                    raise ValueError(f'conflicting visibility for sink "{argument.sink}"')
        return result

    @model_validator(mode="after")
    def reject_conflicting_inline_boundaries(self) -> Self:
        self.effective_sources()
        self.effective_sinks()
        return self
