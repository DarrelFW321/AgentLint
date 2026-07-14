from pathlib import Path

import pytest

from agentlint.policy import (
    PolicyFileError,
    PolicySchemaError,
    PolicyYamlError,
    format_policy_validation_error,
    load_policy,
)

POLICY_DIR = Path(__file__).resolve().parents[1] / "examples" / "policies"


def test_load_policy_loads_customer_support_example() -> None:
    policy = load_policy(POLICY_DIR / "customer_support.yaml")

    assert policy.policy_id == "customer_support_v1"
    assert len(policy.tools) == 5
    assert len(policy.sources) == 3
    assert len(policy.sinks) == 3
    assert len(policy.rules) == 14
    assert len(policy.exceptions) == 1


@pytest.mark.parametrize(
    "fixture_name",
    [
        "research.yaml",
        "coding.yaml",
        "policy_checks.yaml",
        "policy_checks_warning_only.yaml",
        "policy_checks_with_exception.yaml",
        "openai_function_tools.yaml",
        "starter_tools.yaml",
        "starter_approval.yaml",
        "starter_data_flow.yaml",
        "starter_provenance.yaml",
        "../openai_agents/live_policy_agent/agentlint.yaml",
    ],
)
def test_load_policy_loads_valid_examples(fixture_name: str) -> None:
    policy = load_policy(POLICY_DIR / fixture_name)

    assert policy.version == 1


def test_load_policy_rejects_missing_file() -> None:
    with pytest.raises(PolicyFileError, match="policy file not found"):
        load_policy(POLICY_DIR / "does_not_exist.yaml")


def test_load_policy_rejects_directory_path() -> None:
    with pytest.raises(PolicyFileError, match="policy path is a directory"):
        load_policy(POLICY_DIR)


def test_load_policy_rejects_malformed_yaml() -> None:
    with pytest.raises(PolicyYamlError, match="policy YAML parse failed"):
        load_policy(POLICY_DIR / "malformed.yaml")


def test_load_policy_rejects_duplicate_yaml_keys() -> None:
    with pytest.raises(PolicyYamlError, match="duplicate key"):
        load_policy(POLICY_DIR / "duplicate_key.yaml")


@pytest.mark.parametrize("fixture_name", ["empty.yaml", "non_mapping.yaml"])
def test_load_policy_rejects_non_policy_yaml_documents(fixture_name: str) -> None:
    with pytest.raises(PolicySchemaError):
        load_policy(POLICY_DIR / fixture_name)


def test_load_policy_rejects_invalid_schema() -> None:
    with pytest.raises(PolicySchemaError) as exc_info:
        load_policy(POLICY_DIR / "invalid_schema.yaml")

    formatted_errors = format_policy_validation_error(exc_info.value.validation_error)

    assert any("version" in error for error in formatted_errors)
    assert any("permission" in error for error in formatted_errors)
    assert any("rules.unknown_tool" in error for error in formatted_errors)
