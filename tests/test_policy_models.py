import pytest
from pydantic import ValidationError

from agentlint.policy import (
    ArgumentType,
    Policy,
    PolicySeverity,
    RuleId,
    ToolPermission,
)


def make_policy(**overrides: object) -> Policy:
    data: dict[str, object] = {
        "version": 1,
        "policy_id": "policy_test",
    }
    data.update(overrides)
    return Policy.model_validate(data)


def test_minimal_policy_parses_with_defaults() -> None:
    policy = make_policy()

    assert policy.version == 1
    assert policy.policy_id == "policy_test"
    assert policy.metadata == {}
    assert policy.tools == {}
    assert policy.sources == {}
    assert policy.sinks == {}
    assert policy.rules == {}
    assert policy.exceptions == []


def test_policy_serializes_enums_as_stable_strings() -> None:
    policy = make_policy(
        tools={
            "lookup_account": {
                "permission": "allowed",
                "arguments": {
                    "account_id": {
                        "required": True,
                        "allowed_types": ["string"],
                        "allowed_values": ["A-100"],
                    }
                },
            }
        },
        rules={"unknown_tool": "error"},
    )

    assert policy.tools["lookup_account"].permission == ToolPermission.ALLOWED
    assert policy.tools["lookup_account"].arguments["account_id"].allowed_types == [
        ArgumentType.STRING
    ]
    assert policy.rules[RuleId.UNKNOWN_TOOL] == PolicySeverity.ERROR
    assert policy.model_dump(mode="json")["rules"] == {"unknown_tool": "error"}


def test_policy_rejects_extra_fields() -> None:
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        make_policy(unexpected=True)


def test_policy_rejects_unsupported_version() -> None:
    with pytest.raises(ValidationError, match="Input should be 1"):
        make_policy(version=2)


def test_policy_rejects_invalid_enum_values() -> None:
    with pytest.raises(ValidationError):
        make_policy(
            tools={
                "lookup_account": {
                    "permission": "maybe",
                }
            },
            rules={"unknown_tool": "loud"},
        )


@pytest.mark.parametrize(
    "overrides",
    [
        {"policy_id": " "},
        {"tools": {" ": {}}},
        {"sources": {" ": {}}},
        {"sinks": {" ": {}}},
        {"tools": {"lookup_account": {"arguments": {" ": {}}}}},
        {
            "exceptions": [
                {
                    "id": "exception_1",
                    "rules": ["unknown_tool"],
                    "reason": "temporary exception",
                    "match": {"tool": " "},
                }
            ]
        },
    ],
)
def test_policy_rejects_blank_names(overrides: dict[str, object]) -> None:
    with pytest.raises(ValidationError, match="value must not be empty"):
        make_policy(**overrides)


def test_policy_rejects_duplicate_exception_ids() -> None:
    with pytest.raises(ValidationError, match='duplicate exception id "exception_1"'):
        make_policy(
            exceptions=[
                {
                    "id": "exception_1",
                    "rules": ["unknown_tool"],
                    "reason": "first exception",
                },
                {
                    "id": "exception_1",
                    "rules": ["missing_approval"],
                    "reason": "second exception",
                },
            ]
        )


def test_policy_rejects_exception_without_rules() -> None:
    with pytest.raises(ValidationError, match="List should have at least 1 item"):
        make_policy(
            exceptions=[
                {
                    "id": "exception_1",
                    "rules": [],
                    "reason": "temporary exception",
                }
            ]
        )


@pytest.mark.parametrize("field_name", ["allowed_types", "allowed_values"])
def test_policy_rejects_empty_argument_constraint_lists(field_name: str) -> None:
    with pytest.raises(ValidationError, match="constraint list must not be empty"):
        make_policy(
            tools={
                "lookup_account": {
                    "arguments": {
                        "account_id": {
                            field_name: [],
                        }
                    }
                }
            }
        )
