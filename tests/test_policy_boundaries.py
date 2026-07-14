import pytest
from pydantic import ValidationError

from agentlint.diagnostics import DiagnosticCode
from agentlint.ir.v1 import SCHEMA_VERSION, Trace
from agentlint.passes import apply_policy_boundaries, evaluate_policy
from agentlint.policy import Policy, RuleId, compile_policy


def boundary_policy() -> Policy:
    return Policy.model_validate(
        {
            "version": 1,
            "policy_id": "boundary_policy",
            "tools": {
                "customer_db.lookup": {
                    "result": {
                        "source": "customer_profile",
                        "sensitivity": "private",
                        "trust": "trusted",
                    }
                },
                "web_search": {
                    "arguments": {
                        "query": {
                            "sink": "public_search",
                            "visibility": "public",
                        }
                    }
                },
            },
        }
    )


def boundary_trace(*, include_flow: bool) -> Trace:
    return Trace.model_validate(
        {
            "schema_version": SCHEMA_VERSION,
            "trace_id": "trace_boundaries",
            "events": [
                {
                    "id": "lookup_call",
                    "type": "tool_call",
                    "sequence": 0,
                    "tool_name": "customer_db.lookup",
                    "arguments": {},
                },
                {
                    "id": "lookup_result",
                    "type": "tool_result",
                    "sequence": 1,
                    "tool_name": "customer_db.lookup",
                    "call_id": "lookup_call",
                    "result": {"email": "private@example.com"},
                },
                {
                    "id": "search_call",
                    "type": "tool_call",
                    "sequence": 2,
                    "tool_name": "web_search",
                    "arguments": {"query": "customer issue"},
                },
            ],
            "edges": (
                [
                    {
                        "id": "declared_flow",
                        "type": "data_flow",
                        "from_event": "lookup_result",
                        "to_event": "search_call",
                    }
                ]
                if include_flow
                else []
            ),
        }
    )


def test_boundary_enrichment_labels_observed_result_and_argument_without_flow_edge() -> None:
    enriched = apply_policy_boundaries(boundary_trace(include_flow=False), boundary_policy())

    assert enriched.events[1].metadata == {"sources": ["customer_profile"]}
    assert enriched.events[2].metadata == {"sinks": ["public_search"]}
    assert enriched.edges == []


def test_boundaries_do_not_manufacture_data_flow_diagnostic() -> None:
    diagnostics = evaluate_policy(boundary_trace(include_flow=False), boundary_policy())

    assert diagnostics == []


def test_explicit_flow_between_declared_boundaries_produces_exact_diagnostic_path() -> None:
    diagnostics = evaluate_policy(boundary_trace(include_flow=True), boundary_policy())

    assert [item.code for item in diagnostics] == [DiagnosticCode.PRIVATE_TO_PUBLIC_SINK]
    assert diagnostics[0].path is not None
    assert [edge.edge_id for edge in diagnostics[0].path.edges] == ["declared_flow"]


def test_inline_boundaries_activate_only_applicable_data_flow_rule() -> None:
    plan = compile_policy(boundary_policy())

    assert RuleId.PRIVATE_TO_PUBLIC_SINK in plan.rules
    assert RuleId.SECRET_EXPOSURE not in plan.rules
    assert RuleId.UNTRUSTED_TO_PRIVILEGED_ACTION not in plan.rules
    assert RuleId.DISALLOWED_TOOL_ARGUMENT not in plan.rules
    assert {item.value for item in plan.inferred_evidence()} == {
        "tool_calls",
        "tool_arguments",
        "tool_results",
        "data_flow",
    }


def test_inline_boundary_conflict_with_global_classification_is_rejected() -> None:
    with pytest.raises(ValidationError, match="conflicting sensitivity"):
        Policy.model_validate(
            {
                "version": 1,
                "policy_id": "conflict",
                "sources": {"customer_profile": {"sensitivity": "public"}},
                "tools": {
                    "lookup": {
                        "result": {
                            "source": "customer_profile",
                            "sensitivity": "private",
                        }
                    }
                },
            }
        )


def test_argument_visibility_requires_sink_name() -> None:
    with pytest.raises(ValidationError, match="visibility requires a sink"):
        Policy.model_validate(
            {
                "version": 1,
                "policy_id": "invalid_argument_boundary",
                "tools": {
                    "search": {
                        "arguments": {"query": {"visibility": "public"}},
                    }
                },
            }
        )
