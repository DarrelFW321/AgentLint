"""Compile policy constructs into active checks and evidence requirements."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict

from agentlint.capture import CaptureCapability
from agentlint.policy.models import (
    ApprovalRequirement,
    EvidenceRequirementLevel,
    Policy,
    PolicySeverity,
    RuleId,
    Sensitivity,
    SinkVisibility,
    ToolPermission,
    ToolRisk,
    TrustLevel,
)


class RuleActivationOrigin(StrEnum):
    """Why a policy rule is active."""

    INFERRED = "inferred"
    EXPLICIT = "explicit"
    INFERRED_AND_EXPLICIT = "inferred_and_explicit"


class CompiledRule(BaseModel):
    """One active rule with its effective severity and evidence needs."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    rule_id: RuleId
    severity: PolicySeverity
    origin: RuleActivationOrigin
    evidence: dict[CaptureCapability, EvidenceRequirementLevel]


class CompiledPolicyPlan(BaseModel):
    """Single normative plan shared by evaluation and evidence assessment."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    policy_id: str
    rules: dict[RuleId, CompiledRule]

    def is_active(self, rule_id: RuleId) -> bool:
        return rule_id in self.rules

    def rule(self, rule_id: RuleId) -> CompiledRule | None:
        return self.rules.get(rule_id)

    def inferred_evidence(self) -> dict[CaptureCapability, EvidenceRequirementLevel]:
        result: dict[CaptureCapability, EvidenceRequirementLevel] = {}
        for rule in self.rules.values():
            for capability, level in rule.evidence.items():
                current = result.get(capability)
                if current == EvidenceRequirementLevel.CAPTURED:
                    continue
                result[capability] = level
        return result


DEFAULT_RULE_SEVERITIES: dict[RuleId, PolicySeverity] = {
    RuleId.UNKNOWN_TOOL: PolicySeverity.ERROR,
    RuleId.DENIED_TOOL_CALL: PolicySeverity.ERROR,
    RuleId.DISALLOWED_TOOL_ARGUMENT: PolicySeverity.ERROR,
    RuleId.MISSING_APPROVAL: PolicySeverity.ERROR,
    RuleId.APPROVAL_AFTER_ACTION: PolicySeverity.ERROR,
    RuleId.ACTION_AFTER_DENIAL: PolicySeverity.ERROR,
    RuleId.APPROVAL_MISMATCH: PolicySeverity.ERROR,
    RuleId.PRIVATE_TO_PUBLIC_SINK: PolicySeverity.ERROR,
    RuleId.SECRET_EXPOSURE: PolicySeverity.ERROR,
    RuleId.UNTRUSTED_TO_PRIVILEGED_ACTION: PolicySeverity.ERROR,
    RuleId.SENSITIVE_FINAL_ANSWER: PolicySeverity.ERROR,
    RuleId.UNSUPPORTED_CLAIM: PolicySeverity.WARNING,
    RuleId.INVALID_PROVENANCE_REFERENCE: PolicySeverity.ERROR,
    RuleId.EVIDENCE_AFTER_CLAIM: PolicySeverity.WARNING,
}

_RULE_EVIDENCE: dict[RuleId, set[CaptureCapability]] = {
    RuleId.UNKNOWN_TOOL: {CaptureCapability.TOOL_CALLS},
    RuleId.DENIED_TOOL_CALL: {CaptureCapability.TOOL_CALLS},
    RuleId.DISALLOWED_TOOL_ARGUMENT: {
        CaptureCapability.TOOL_CALLS,
        CaptureCapability.TOOL_ARGUMENTS,
    },
    RuleId.MISSING_APPROVAL: {CaptureCapability.TOOL_CALLS, CaptureCapability.APPROVALS},
    RuleId.APPROVAL_AFTER_ACTION: {
        CaptureCapability.TOOL_CALLS,
        CaptureCapability.APPROVALS,
    },
    RuleId.ACTION_AFTER_DENIAL: {CaptureCapability.TOOL_CALLS, CaptureCapability.APPROVALS},
    RuleId.APPROVAL_MISMATCH: {CaptureCapability.TOOL_CALLS, CaptureCapability.APPROVALS},
    RuleId.PRIVATE_TO_PUBLIC_SINK: {CaptureCapability.DATA_FLOW},
    RuleId.SECRET_EXPOSURE: {CaptureCapability.DATA_FLOW},
    RuleId.UNTRUSTED_TO_PRIVILEGED_ACTION: {
        CaptureCapability.TOOL_CALLS,
        CaptureCapability.DATA_FLOW,
    },
    RuleId.SENSITIVE_FINAL_ANSWER: {
        CaptureCapability.DATA_FLOW,
        CaptureCapability.FINAL_ANSWERS,
    },
    RuleId.UNSUPPORTED_CLAIM: {
        CaptureCapability.PROVENANCE,
        CaptureCapability.FINAL_ANSWERS,
    },
    RuleId.INVALID_PROVENANCE_REFERENCE: {
        CaptureCapability.PROVENANCE,
        CaptureCapability.FINAL_ANSWERS,
    },
    RuleId.EVIDENCE_AFTER_CLAIM: {
        CaptureCapability.PROVENANCE,
        CaptureCapability.FINAL_ANSWERS,
    },
}


def compile_policy(policy: Policy) -> CompiledPolicyPlan:
    """Compile construct-driven and explicit rule activation once."""
    inferred = _inferred_rules(policy)
    rules: dict[RuleId, CompiledRule] = {}

    for rule_id in RuleId:
        explicit = policy.rules.get(rule_id)
        if explicit == PolicySeverity.OFF:
            continue
        is_inferred = rule_id in inferred
        if explicit is None and not is_inferred:
            continue
        severity = explicit or DEFAULT_RULE_SEVERITIES[rule_id]
        origin = (
            RuleActivationOrigin.INFERRED_AND_EXPLICIT
            if is_inferred and explicit is not None
            else RuleActivationOrigin.INFERRED
            if is_inferred
            else RuleActivationOrigin.EXPLICIT
        )
        evidence_capabilities = set(_RULE_EVIDENCE[rule_id])
        if rule_id in {
            RuleId.PRIVATE_TO_PUBLIC_SINK,
            RuleId.SECRET_EXPOSURE,
            RuleId.UNTRUSTED_TO_PRIVILEGED_ACTION,
        }:
            if any(tool.result is not None for tool in policy.tools.values()):
                evidence_capabilities.add(CaptureCapability.TOOL_RESULTS)
            if any(
                argument.sink is not None
                for tool in policy.tools.values()
                for argument in tool.arguments.values()
            ):
                evidence_capabilities.update(
                    {CaptureCapability.TOOL_CALLS, CaptureCapability.TOOL_ARGUMENTS}
                )
        rules[rule_id] = CompiledRule(
            rule_id=rule_id,
            severity=severity,
            origin=origin,
            evidence={
                capability: EvidenceRequirementLevel.PARTIAL
                for capability in sorted(evidence_capabilities, key=lambda item: item.value)
            },
        )

    return CompiledPolicyPlan(policy_id=policy.policy_id, rules=rules)


def _inferred_rules(policy: Policy) -> set[RuleId]:
    rules: set[RuleId] = set()
    sources = policy.effective_sources()
    sinks = policy.effective_sinks()
    if policy.tools:
        rules.update({RuleId.UNKNOWN_TOOL, RuleId.DENIED_TOOL_CALL})
    if any(
        argument.required
        or argument.allowed_types is not None
        or argument.allowed_values is not None
        for tool in policy.tools.values()
        for argument in tool.arguments.values()
    ):
        rules.add(RuleId.DISALLOWED_TOOL_ARGUMENT)
    if any(tool.approval == ApprovalRequirement.REQUIRED for tool in policy.tools.values()):
        rules.update(
            {
                RuleId.MISSING_APPROVAL,
                RuleId.APPROVAL_AFTER_ACTION,
                RuleId.ACTION_AFTER_DENIAL,
                RuleId.APPROVAL_MISMATCH,
            }
        )
    has_public_sink = any(sink.visibility == SinkVisibility.PUBLIC for sink in sinks.values())
    has_private_source = any(
        source.sensitivity in {Sensitivity.PRIVATE, Sensitivity.SECRET}
        for source in sources.values()
    )
    has_secret_source = any(source.sensitivity == Sensitivity.SECRET for source in sources.values())
    has_exposed_sink = any(
        sink.visibility in {SinkVisibility.PUBLIC, SinkVisibility.MODEL, SinkVisibility.PRIVATE}
        for sink in sinks.values()
    )
    has_untrusted_source = any(source.trust == TrustLevel.UNTRUSTED for source in sources.values())
    has_privileged_tool = any(
        tool.risk in {ToolRisk.HIGH, ToolRisk.CRITICAL}
        or tool.approval == ApprovalRequirement.REQUIRED
        or tool.permission == ToolPermission.DENIED
        for tool in policy.tools.values()
    )
    if has_private_source and has_public_sink:
        rules.add(RuleId.PRIVATE_TO_PUBLIC_SINK)
    if has_secret_source and has_exposed_sink:
        rules.add(RuleId.SECRET_EXPOSURE)
    if has_untrusted_source and has_privileged_tool:
        rules.add(RuleId.UNTRUSTED_TO_PRIVILEGED_ACTION)
    if sources and "final_answer" in sinks:
        rules.add(RuleId.SENSITIVE_FINAL_ANSWER)
    return rules
