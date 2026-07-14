from agentlint.capture import (
    CapabilityCoverage,
    CaptureCapabilities,
    CaptureCompleteness,
    CaptureStatus,
)
from agentlint.evidence import RequirementOrigin, assess_evidence
from agentlint.policy import Policy


def capture(**statuses: CaptureStatus) -> CaptureCompleteness:
    values = {
        capability: CapabilityCoverage(status=statuses.get(capability, CaptureStatus.UNKNOWN))
        for capability in CaptureCapabilities.model_fields
    }
    return CaptureCompleteness(
        adapter="test",
        capabilities=CaptureCapabilities.model_validate(values),
    )


def test_infers_requirements_from_policy_constructs() -> None:
    policy = Policy.model_validate(
        {
            "version": 1,
            "policy_id": "approval_policy",
            "tools": {"refund": {"approval": "required"}},
        }
    )

    assessment = assess_evidence(
        policy,
        capture(tool_calls=CaptureStatus.PARTIAL, approvals=CaptureStatus.UNAVAILABLE),
    )

    assert [item.capability.value for item in assessment.requirements] == [
        "tool_calls",
        "approvals",
    ]
    assert [item.capability.value for item in assessment.unmet] == ["approvals"]


def test_explicit_requirement_strengthens_inferred_requirement() -> None:
    policy = Policy.model_validate(
        {
            "version": 1,
            "policy_id": "strict_tools",
            "tools": {"lookup": {}},
            "capture": {"require": {"tool_calls": "captured"}},
        }
    )

    assessment = assess_evidence(policy, capture(tool_calls=CaptureStatus.PARTIAL))

    requirement = assessment.requirements[0]
    assert requirement.required.value == "captured"
    assert requirement.origin == RequirementOrigin.INFERRED_AND_EXPLICIT
    assert assessment.unmet == [requirement]
