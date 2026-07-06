from agentlint.diagnostics import (
    Diagnostic,
    DiagnosticCode,
    Severity,
    all_diagnostic_explanations,
    explain_diagnostic_code,
    format_diagnostic,
    format_diagnostics,
)


def test_diagnostic_defaults_and_json_serialization() -> None:
    diagnostic = Diagnostic(
        code=DiagnosticCode.DUPLICATE_EVENT_ID,
        message='duplicate event id "evt_1"',
    )

    assert diagnostic.severity == Severity.ERROR
    assert diagnostic.related_events == []
    assert diagnostic.related_edges == []
    assert diagnostic.model_dump(mode="json") == {
        "code": "DUPLICATE_EVENT_ID",
        "severity": "error",
        "message": 'duplicate event id "evt_1"',
        "related_events": [],
        "related_edges": [],
        "policy_reference": None,
        "remediation": None,
    }


def test_format_diagnostic_includes_related_ids_and_remediation() -> None:
    diagnostic = Diagnostic(
        code=DiagnosticCode.MISSING_EVENT_REFERENCE,
        message='edge "edge_1" references missing event "evt_missing"',
        related_events=["evt_missing"],
        related_edges=["edge_1"],
        remediation="Reference only event ids that exist in the trace.",
    )

    assert format_diagnostic(diagnostic) == (
        'error[MISSING_EVENT_REFERENCE]: edge "edge_1" references missing event '
        '"evt_missing"\n'
        "  related events: evt_missing\n"
        "  related edges: edge_1\n"
        "  remediation: Reference only event ids that exist in the trace."
    )


def test_format_diagnostics_joins_multiple_diagnostics() -> None:
    diagnostics = [
        Diagnostic(
            code=DiagnosticCode.DUPLICATE_EVENT_ID,
            message='duplicate event id "evt_1"',
        ),
        Diagnostic(
            code=DiagnosticCode.DUPLICATE_EDGE_ID,
            message='duplicate edge id "edge_1"',
        ),
    ]

    assert format_diagnostics(diagnostics) == (
        'error[DUPLICATE_EVENT_ID]: duplicate event id "evt_1"\n'
        'error[DUPLICATE_EDGE_ID]: duplicate edge id "edge_1"'
    )


def test_diagnostic_code_contains_milestone_4_policy_codes() -> None:
    policy_codes = {
        DiagnosticCode.UNKNOWN_TOOL,
        DiagnosticCode.UNAUTHORIZED_TOOL_CALL,
        DiagnosticCode.DISALLOWED_TOOL_ARGUMENT,
        DiagnosticCode.MISSING_APPROVAL,
        DiagnosticCode.APPROVAL_AFTER_ACTION,
        DiagnosticCode.ACTION_AFTER_DENIAL,
        DiagnosticCode.APPROVAL_MISMATCH,
        DiagnosticCode.PRIVATE_TO_PUBLIC_SINK,
        DiagnosticCode.SECRET_EXPOSURE,
        DiagnosticCode.UNTRUSTED_TO_PRIVILEGED_ACTION,
        DiagnosticCode.SENSITIVE_FINAL_ANSWER,
        DiagnosticCode.UNSUPPORTED_CLAIM,
        DiagnosticCode.INVALID_PROVENANCE_REFERENCE,
        DiagnosticCode.EVIDENCE_AFTER_CLAIM,
    }

    assert {code.value for code in policy_codes} <= {code.value for code in DiagnosticCode}


def test_every_diagnostic_code_has_explanation() -> None:
    explanations = all_diagnostic_explanations()

    assert set(explanations) == set(DiagnosticCode)


def test_explain_diagnostic_code_is_case_insensitive() -> None:
    explanation = explain_diagnostic_code("unknown_tool")

    assert explanation is not None
    assert explanation.code == DiagnosticCode.UNKNOWN_TOOL
    assert explanation.category == "policy"


def test_explain_diagnostic_code_returns_none_for_unknown_code() -> None:
    assert explain_diagnostic_code("NOT_A_CODE") is None
