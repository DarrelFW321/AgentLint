from pathlib import Path

import pytest

from agentlint.diagnostics import DiagnosticCode, Severity
from agentlint.ir.v1 import SCHEMA_VERSION, Trace, load_native_trace
from agentlint.passes import evaluate_policy, validate_structure
from agentlint.policy import Policy, PolicySeverity, RuleId, load_policy

TRACE_DIR = Path(__file__).resolve().parents[1] / "examples" / "traces"
POLICY_DIR = Path(__file__).resolve().parents[1] / "examples" / "policies"


def make_trace(events: list[dict], edges: list[dict] | None = None) -> Trace:
    return Trace.model_validate(
        {
            "schema_version": SCHEMA_VERSION,
            "trace_id": "trace_test",
            "metadata": {},
            "events": events,
            "edges": edges or [],
        }
    )


def policy_checks() -> Policy:
    return load_policy(POLICY_DIR / "policy_checks.yaml")


def warning_policy() -> Policy:
    return load_policy(POLICY_DIR / "policy_checks_warning_only.yaml")


def diagnostic_codes(trace: Trace, policy: Policy) -> list[DiagnosticCode]:
    return [diagnostic.code for diagnostic in evaluate_policy(trace, policy)]


@pytest.mark.parametrize(
    "fixture_name",
    [
        "policy_tool_valid.json",
        "policy_approval_valid.json",
        "policy_data_flow_valid.json",
        "policy_provenance_valid.json",
    ],
)
def test_policy_passing_fixtures_have_no_diagnostics(fixture_name: str) -> None:
    trace = load_native_trace(TRACE_DIR / fixture_name)

    assert validate_structure(trace) == []
    assert evaluate_policy(trace, policy_checks()) == []


@pytest.mark.parametrize(
    ("fixture_name", "expected_code"),
    [
        ("policy_unknown_tool.json", DiagnosticCode.UNKNOWN_TOOL),
        ("policy_denied_tool_call.json", DiagnosticCode.DENIED_TOOL_CALL),
        ("policy_disallowed_tool_argument.json", DiagnosticCode.DISALLOWED_TOOL_ARGUMENT),
        ("policy_missing_approval.json", DiagnosticCode.MISSING_APPROVAL),
        ("policy_approval_after_action.json", DiagnosticCode.APPROVAL_AFTER_ACTION),
        ("policy_action_after_denial.json", DiagnosticCode.ACTION_AFTER_DENIAL),
        ("policy_approval_mismatch.json", DiagnosticCode.APPROVAL_MISMATCH),
        ("policy_private_to_public_sink.json", DiagnosticCode.PRIVATE_TO_PUBLIC_SINK),
        ("policy_secret_exposure.json", DiagnosticCode.SECRET_EXPOSURE),
        (
            "policy_untrusted_to_privileged_action.json",
            DiagnosticCode.UNTRUSTED_TO_PRIVILEGED_ACTION,
        ),
        ("policy_sensitive_final_answer.json", DiagnosticCode.SENSITIVE_FINAL_ANSWER),
        ("policy_unsupported_claim.json", DiagnosticCode.UNSUPPORTED_CLAIM),
        (
            "policy_invalid_provenance_reference.json",
            DiagnosticCode.INVALID_PROVENANCE_REFERENCE,
        ),
    ],
)
def test_policy_failing_fixtures_emit_expected_diagnostic(
    fixture_name: str,
    expected_code: DiagnosticCode,
) -> None:
    trace = load_native_trace(TRACE_DIR / fixture_name)

    assert validate_structure(trace) == []
    assert diagnostic_codes(trace, policy_checks()) == [expected_code]


def test_evidence_after_claim_can_be_checked_without_invalid_provenance_cascade() -> None:
    trace = load_native_trace(TRACE_DIR / "policy_evidence_after_claim.json")

    assert validate_structure(trace) == []
    assert diagnostic_codes(trace, warning_policy()) == [DiagnosticCode.EVIDENCE_AFTER_CLAIM]


def test_policy_diagnostics_include_severity_reference_and_remediation() -> None:
    trace = load_native_trace(TRACE_DIR / "policy_unknown_tool.json")
    diagnostic = evaluate_policy(trace, policy_checks())[0]

    assert diagnostic.severity == Severity.ERROR
    assert diagnostic.policy_reference == "policy_checks_v1:unknown_tool"
    assert diagnostic.remediation is not None


def test_data_flow_diagnostic_includes_only_explicit_sanitized_path() -> None:
    trace = load_native_trace(TRACE_DIR / "policy_private_to_public_sink.json")
    diagnostic = evaluate_policy(trace, policy_checks())[0]

    assert diagnostic.path is not None
    assert [node.event_id for node in diagnostic.path.nodes] == [
        "evt_customer_profile",
        "evt_web_search",
    ]
    assert [node.label for node in diagnostic.path.nodes] == [
        "user_message",
        "tool_call:web_search",
    ]
    assert [edge.edge_id for edge in diagnostic.path.edges] == ["edge_data_customer_to_search"]


def test_diagnostic_does_not_invent_path_when_trace_has_no_edge() -> None:
    trace = load_native_trace(TRACE_DIR / "policy_approval_after_action.json")
    diagnostic = evaluate_policy(trace, policy_checks())[0]

    assert diagnostic.path is None


def test_rule_severity_info_is_applied() -> None:
    policy = policy_checks()
    policy = policy.model_copy(
        update={"rules": {**policy.rules, RuleId.UNKNOWN_TOOL: PolicySeverity.INFO}}
    )
    trace = load_native_trace(TRACE_DIR / "policy_unknown_tool.json")

    diagnostics = evaluate_policy(trace, policy)

    assert [diagnostic.severity for diagnostic in diagnostics] == [Severity.INFO]


def test_rule_severity_off_suppresses_rule() -> None:
    policy = policy_checks()
    policy = policy.model_copy(
        update={"rules": {**policy.rules, RuleId.UNKNOWN_TOOL: PolicySeverity.OFF}}
    )
    trace = load_native_trace(TRACE_DIR / "policy_unknown_tool.json")

    assert evaluate_policy(trace, policy) == []


def test_policy_exception_suppresses_exact_match() -> None:
    trace = load_native_trace(TRACE_DIR / "policy_private_to_public_sink.json")
    policy = load_policy(POLICY_DIR / "policy_checks_with_exception.yaml")

    assert evaluate_policy(trace, policy) == []


def test_policy_exception_does_not_suppress_unmatched_diagnostic() -> None:
    trace = load_native_trace(TRACE_DIR / "policy_unknown_tool.json")
    policy = load_policy(POLICY_DIR / "policy_checks_with_exception.yaml")

    assert diagnostic_codes(trace, policy) == [DiagnosticCode.UNKNOWN_TOOL]


def test_policy_diagnostics_are_ordered_by_decision_contract() -> None:
    trace = make_trace(
        [
            {
                "id": "evt_unknown_tool",
                "type": "tool_call",
                "sequence": 0,
                "tool_name": "unknown_tool",
                "arguments": {},
            },
            {
                "id": "evt_user_approval",
                "type": "user_message",
                "sequence": 1,
                "content": "Approve this.",
            },
            {
                "id": "evt_bad_approval",
                "type": "approval",
                "sequence": 2,
                "decision": "approved",
                "subject_event": "evt_user_approval",
            },
            {
                "id": "evt_send_email",
                "type": "tool_call",
                "sequence": 3,
                "tool_name": "send_email",
                "arguments": {
                    "recipient": "customer@example.com",
                    "body": "Your case has been updated.",
                },
            },
            {
                "id": "evt_customer_profile",
                "type": "user_message",
                "sequence": 4,
                "content": "Customer profile details.",
                "metadata": {
                    "source": "customer_profile",
                },
            },
            {
                "id": "evt_web_search",
                "type": "tool_call",
                "sequence": 5,
                "tool_name": "web_search",
                "arguments": {
                    "query": "customer profile details",
                },
                "metadata": {
                    "sink": "web_search.query",
                },
            },
            {
                "id": "evt_final",
                "type": "final_answer",
                "sequence": 6,
                "content": "The customer profile says the account is active.",
                "claims": [
                    {
                        "id": "claim_status",
                        "text": "The account is active.",
                        "evidence": [],
                    }
                ],
            },
        ],
        [
            {
                "id": "edge_data_customer_to_search",
                "type": "data_flow",
                "from_event": "evt_customer_profile",
                "to_event": "evt_web_search",
            },
            {
                "id": "edge_data_customer_to_final",
                "type": "data_flow",
                "from_event": "evt_customer_profile",
                "to_event": "evt_final",
            },
        ],
    )

    assert diagnostic_codes(trace, policy_checks()) == [
        DiagnosticCode.UNKNOWN_TOOL,
        DiagnosticCode.APPROVAL_MISMATCH,
        DiagnosticCode.MISSING_APPROVAL,
        DiagnosticCode.PRIVATE_TO_PUBLIC_SINK,
        DiagnosticCode.SENSITIVE_FINAL_ANSWER,
        DiagnosticCode.UNSUPPORTED_CLAIM,
    ]


def test_unknown_source_and_sink_metadata_labels_are_ignored() -> None:
    trace = make_trace(
        [
            {
                "id": "evt_unknown_source",
                "type": "user_message",
                "sequence": 0,
                "content": "Unknown source.",
                "metadata": {
                    "source": "unknown_source",
                },
            },
            {
                "id": "evt_web_search",
                "type": "tool_call",
                "sequence": 1,
                "tool_name": "web_search",
                "arguments": {
                    "query": "public status",
                },
                "metadata": {
                    "sink": "unknown_sink",
                },
            },
        ],
        [
            {
                "id": "edge_data_unknown_to_search",
                "type": "data_flow",
                "from_event": "evt_unknown_source",
                "to_event": "evt_web_search",
            }
        ],
    )

    assert evaluate_policy(trace, policy_checks()) == []


def test_boolean_does_not_satisfy_integer_argument_type() -> None:
    policy = Policy.model_validate(
        {
            "version": 1,
            "policy_id": "integer_policy",
            "tools": {
                "set_count": {
                    "arguments": {
                        "count": {
                            "required": True,
                            "allowed_types": ["integer"],
                        }
                    }
                }
            },
            "rules": {
                "disallowed_tool_argument": "error",
            },
        }
    )
    trace = make_trace(
        [
            {
                "id": "evt_set_count",
                "type": "tool_call",
                "sequence": 0,
                "tool_name": "set_count",
                "arguments": {
                    "count": True,
                },
            }
        ]
    )

    assert diagnostic_codes(trace, policy) == [DiagnosticCode.DISALLOWED_TOOL_ARGUMENT]
