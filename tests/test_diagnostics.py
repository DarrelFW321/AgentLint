from agentlint.diagnostics import (
    Diagnostic,
    DiagnosticCode,
    Severity,
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
