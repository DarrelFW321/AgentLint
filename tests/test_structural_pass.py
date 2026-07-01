from pathlib import Path

import pytest

from agentlint.diagnostics import DiagnosticCode
from agentlint.ir.v1 import SCHEMA_VERSION, Trace, load_native_trace
from agentlint.passes import validate_structure

TRACE_DIR = Path(__file__).resolve().parents[1] / "examples" / "traces"


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


def diagnostic_codes(trace: Trace) -> list[DiagnosticCode]:
    return [diagnostic.code for diagnostic in validate_structure(trace)]


def test_valid_structural_fixture_has_no_diagnostics() -> None:
    trace = load_native_trace(TRACE_DIR / "structural_valid_tool_flow.json")

    assert validate_structure(trace) == []


@pytest.mark.parametrize(
    ("fixture_name", "expected_code"),
    [
        ("structural_duplicate_event_id.json", DiagnosticCode.DUPLICATE_EVENT_ID),
        ("structural_duplicate_edge_id.json", DiagnosticCode.DUPLICATE_EDGE_ID),
        ("structural_missing_event_reference.json", DiagnosticCode.MISSING_EVENT_REFERENCE),
        (
            "structural_tool_result_without_call.json",
            DiagnosticCode.TOOL_RESULT_WITHOUT_MATCHING_CALL,
        ),
        (
            "structural_tool_call_missing_arguments.json",
            DiagnosticCode.TOOL_CALL_MISSING_ARGUMENTS,
        ),
        ("structural_invalid_event_order.json", DiagnosticCode.INVALID_EVENT_ORDER),
        (
            "structural_invalid_evidence_reference.json",
            DiagnosticCode.INVALID_EVIDENCE_REFERENCE,
        ),
    ],
)
def test_structural_fixtures_emit_expected_diagnostic(
    fixture_name: str,
    expected_code: DiagnosticCode,
) -> None:
    trace = load_native_trace(TRACE_DIR / fixture_name)
    diagnostics = validate_structure(trace)

    assert [diagnostic.code for diagnostic in diagnostics] == [expected_code]


def test_structural_diagnostics_are_ordered_deterministically() -> None:
    trace = make_trace(
        [
            {
                "id": "evt_a",
                "type": "user_message",
                "sequence": 0,
                "content": "Hello.",
            },
            {
                "id": "evt_duplicate",
                "type": "user_message",
                "sequence": 1,
                "content": "Hello.",
            },
            {
                "id": "evt_duplicate",
                "type": "final_answer",
                "sequence": 2,
                "content": "Hello.",
            },
            {
                "id": "evt_tool_call",
                "type": "tool_call",
                "sequence": 3,
                "tool_name": "lookup_account",
            },
            {
                "id": "evt_tool_result",
                "type": "tool_result",
                "sequence": 4,
                "tool_name": "lookup_account",
                "result": {},
            },
            {
                "id": "evt_late",
                "type": "user_message",
                "sequence": 5,
                "content": "Late event.",
            },
            {
                "id": "evt_final",
                "type": "final_answer",
                "sequence": 6,
                "content": "Done.",
                "claims": [
                    {
                        "id": "claim_1",
                        "text": "Done.",
                        "evidence": ["evt_missing_evidence"],
                    }
                ],
            },
        ],
        [
            {
                "id": "edge_duplicate",
                "type": "parent",
                "from_event": "evt_a",
                "to_event": "evt_tool_call",
            },
            {
                "id": "edge_duplicate",
                "type": "data_flow",
                "from_event": "evt_a",
                "to_event": "evt_tool_call",
            },
            {
                "id": "edge_missing",
                "type": "data_flow",
                "from_event": "evt_missing",
                "to_event": "evt_final",
            },
            {
                "id": "edge_backward",
                "type": "parent",
                "from_event": "evt_late",
                "to_event": "evt_a",
            },
        ],
    )

    assert diagnostic_codes(trace) == [
        DiagnosticCode.DUPLICATE_EVENT_ID,
        DiagnosticCode.DUPLICATE_EDGE_ID,
        DiagnosticCode.MISSING_EVENT_REFERENCE,
        DiagnosticCode.TOOL_CALL_MISSING_ARGUMENTS,
        DiagnosticCode.TOOL_RESULT_WITHOUT_MATCHING_CALL,
        DiagnosticCode.INVALID_EVENT_ORDER,
        DiagnosticCode.INVALID_EVIDENCE_REFERENCE,
    ]


def test_references_to_duplicated_event_ids_are_not_missing_references() -> None:
    trace = make_trace(
        [
            {
                "id": "evt_duplicate",
                "type": "user_message",
                "sequence": 0,
                "content": "Hello.",
            },
            {
                "id": "evt_duplicate",
                "type": "final_answer",
                "sequence": 1,
                "content": "Hello.",
            },
            {
                "id": "evt_unique",
                "type": "final_answer",
                "sequence": 2,
                "content": "Hello.",
            },
        ],
        [
            {
                "id": "edge_1",
                "type": "parent",
                "from_event": "evt_duplicate",
                "to_event": "evt_unique",
            }
        ],
    )

    assert diagnostic_codes(trace) == [DiagnosticCode.DUPLICATE_EVENT_ID]


def test_missing_approval_subject_event_is_a_missing_reference() -> None:
    trace = make_trace(
        [
            {
                "id": "evt_approval",
                "type": "approval",
                "sequence": 0,
                "decision": "approved",
                "subject_event": "evt_missing",
            }
        ]
    )

    assert diagnostic_codes(trace) == [DiagnosticCode.MISSING_EVENT_REFERENCE]


@pytest.mark.parametrize(
    "tool_result",
    [
        {
            "id": "evt_tool_result",
            "type": "tool_result",
            "sequence": 2,
            "tool_name": "lookup_account",
            "call_id": "evt_missing",
            "result": {},
        },
        {
            "id": "evt_tool_result",
            "type": "tool_result",
            "sequence": 2,
            "tool_name": "lookup_account",
            "call_id": "evt_user",
            "result": {},
        },
        {
            "id": "evt_tool_result",
            "type": "tool_result",
            "sequence": 2,
            "tool_name": "other_tool",
            "call_id": "evt_tool_call",
            "result": {},
        },
    ],
)
def test_tool_result_matching_failures(tool_result: dict) -> None:
    trace = make_trace(
        [
            {
                "id": "evt_user",
                "type": "user_message",
                "sequence": 0,
                "content": "Hello.",
            },
            {
                "id": "evt_tool_call",
                "type": "tool_call",
                "sequence": 1,
                "tool_name": "lookup_account",
                "arguments": {},
            },
            tool_result,
        ]
    )

    assert diagnostic_codes(trace) == [DiagnosticCode.TOOL_RESULT_WITHOUT_MATCHING_CALL]


def test_same_sequence_edge_is_allowed() -> None:
    trace = make_trace(
        [
            {
                "id": "evt_a",
                "type": "user_message",
                "sequence": 0,
                "content": "Hello.",
            },
            {
                "id": "evt_b",
                "type": "final_answer",
                "sequence": 0,
                "content": "Hello.",
            },
        ],
        [
            {
                "id": "edge_same_sequence",
                "type": "parent",
                "from_event": "evt_a",
                "to_event": "evt_b",
            }
        ],
    )

    assert validate_structure(trace) == []


def test_same_sequence_tool_result_is_invalid_order() -> None:
    trace = make_trace(
        [
            {
                "id": "evt_tool_call",
                "type": "tool_call",
                "sequence": 0,
                "tool_name": "lookup_account",
                "arguments": {},
            },
            {
                "id": "evt_tool_result",
                "type": "tool_result",
                "sequence": 0,
                "tool_name": "lookup_account",
                "call_id": "evt_tool_call",
                "result": {},
            },
        ]
    )

    assert diagnostic_codes(trace) == [DiagnosticCode.INVALID_EVENT_ORDER]
