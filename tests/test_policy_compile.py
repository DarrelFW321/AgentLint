from agentlint.capture import CaptureCapability
from agentlint.policy import (
    Policy,
    PolicySeverity,
    RuleActivationOrigin,
    RuleId,
    compile_policy,
)


def policy(**values: object) -> Policy:
    return Policy.model_validate({"version": 1, "policy_id": "compiled", **values})


def test_empty_policy_activates_no_checks_or_evidence() -> None:
    plan = compile_policy(policy())

    assert plan.rules == {}
    assert plan.inferred_evidence() == {}


def test_tool_inventory_activates_only_tool_inventory_checks() -> None:
    plan = compile_policy(policy(tools={"lookup": {}}))

    assert list(plan.rules) == [RuleId.UNKNOWN_TOOL, RuleId.DENIED_TOOL_CALL]
    assert plan.inferred_evidence() == {CaptureCapability.TOOL_CALLS: "partial"}


def test_approval_contract_activates_approval_checks_and_evidence() -> None:
    plan = compile_policy(policy(tools={"refund": {"approval": "required"}}))

    assert set(plan.rules) == {
        RuleId.UNKNOWN_TOOL,
        RuleId.DENIED_TOOL_CALL,
        RuleId.MISSING_APPROVAL,
        RuleId.APPROVAL_AFTER_ACTION,
        RuleId.ACTION_AFTER_DENIAL,
        RuleId.APPROVAL_MISMATCH,
    }
    assert plan.inferred_evidence() == {
        CaptureCapability.APPROVALS: "partial",
        CaptureCapability.TOOL_CALLS: "partial",
    }


def test_provenance_checks_require_explicit_activation() -> None:
    implicit = compile_policy(policy())
    explicit = compile_policy(policy(rules={"unsupported_claim": "warning"}))

    assert not implicit.is_active(RuleId.UNSUPPORTED_CLAIM)
    assert explicit.rule(RuleId.UNSUPPORTED_CLAIM).origin == RuleActivationOrigin.EXPLICIT
    assert explicit.inferred_evidence() == {
        CaptureCapability.FINAL_ANSWERS: "partial",
        CaptureCapability.PROVENANCE: "partial",
    }


def test_private_public_policy_does_not_activate_unrelated_privileged_flow_check() -> None:
    plan = compile_policy(
        policy(
            sources={"customer": {"sensitivity": "private", "trust": "trusted"}},
            sinks={"search.query": {"visibility": "public"}},
        )
    )

    assert list(plan.rules) == [RuleId.PRIVATE_TO_PUBLIC_SINK]
    assert plan.inferred_evidence() == {CaptureCapability.DATA_FLOW: "partial"}


def test_explicit_off_wins_over_construct_activation() -> None:
    plan = compile_policy(
        policy(
            tools={"lookup": {}},
            rules={"unknown_tool": PolicySeverity.OFF},
        )
    )

    assert not plan.is_active(RuleId.UNKNOWN_TOOL)
    assert plan.is_active(RuleId.DENIED_TOOL_CALL)


def test_explicit_severity_strengthens_inferred_rule_without_duplication() -> None:
    plan = compile_policy(
        policy(
            tools={"lookup": {}},
            rules={"unknown_tool": "warning"},
        )
    )

    rule = plan.rule(RuleId.UNKNOWN_TOOL)
    assert rule is not None
    assert rule.severity == PolicySeverity.WARNING
    assert rule.origin == RuleActivationOrigin.INFERRED_AND_EXPLICIT
