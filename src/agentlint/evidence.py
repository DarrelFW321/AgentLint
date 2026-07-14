"""Compile policy constructs into minimum capture requirements."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict

from agentlint.capture import CaptureCapability, CaptureCompleteness, CaptureStatus
from agentlint.policy import CompiledPolicyPlan, EvidenceRequirementLevel, Policy, compile_policy


class RequirementOrigin(StrEnum):
    INFERRED = "inferred"
    EXPLICIT = "explicit"
    INFERRED_AND_EXPLICIT = "inferred_and_explicit"


class EvidenceRequirement(BaseModel):
    model_config = ConfigDict(extra="forbid")

    capability: CaptureCapability
    required: EvidenceRequirementLevel
    observed: CaptureStatus
    origin: RequirementOrigin
    reason: str


class EvidenceAssessment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    requirements: list[EvidenceRequirement]
    unmet: list[EvidenceRequirement]


def assess_evidence(
    policy: Policy | None,
    capture: CaptureCompleteness,
    *,
    plan: CompiledPolicyPlan | None = None,
) -> EvidenceAssessment:
    """Compile and compare effective policy evidence requirements."""
    if policy is None:
        return EvidenceAssessment(requirements=[], unmet=[])

    compiled = plan or compile_policy(policy)
    inferred = compiled.inferred_evidence()
    explicit = policy.capture.require
    requirements: list[EvidenceRequirement] = []

    for capability in CaptureCapability:
        inferred_level = inferred.get(capability)
        explicit_level = explicit.get(capability)
        if inferred_level is None and explicit_level is None:
            continue
        required = _stricter(inferred_level, explicit_level)
        coverage = getattr(capture.capabilities, capability.value)
        origin = (
            RequirementOrigin.INFERRED_AND_EXPLICIT
            if inferred_level is not None and explicit_level is not None
            else RequirementOrigin.INFERRED
            if inferred_level is not None
            else RequirementOrigin.EXPLICIT
        )
        requirements.append(
            EvidenceRequirement(
                capability=capability,
                required=required,
                observed=coverage.status,
                origin=origin,
                reason=coverage.reason or "No capture explanation was provided.",
            )
        )

    unmet = [item for item in requirements if not _satisfies(item.observed, item.required)]
    return EvidenceAssessment(requirements=requirements, unmet=unmet)


def _stricter(
    inferred: EvidenceRequirementLevel | None,
    explicit: EvidenceRequirementLevel | None,
) -> EvidenceRequirementLevel:
    if EvidenceRequirementLevel.CAPTURED in {inferred, explicit}:
        return EvidenceRequirementLevel.CAPTURED
    return EvidenceRequirementLevel.PARTIAL


def _satisfies(observed: CaptureStatus, required: EvidenceRequirementLevel) -> bool:
    if required == EvidenceRequirementLevel.CAPTURED:
        return observed == CaptureStatus.CAPTURED
    return observed in {CaptureStatus.PARTIAL, CaptureStatus.CAPTURED}
