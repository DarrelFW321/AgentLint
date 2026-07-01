import pytest
from pydantic import ValidationError

from agentlint.ir.v1 import SCHEMA_VERSION, Trace


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


@pytest.mark.parametrize(
    "event",
    [
        {
            "id": "evt_user",
            "type": "user_message",
            "sequence": 0,
            "content": "Hello.",
        },
        {
            "id": "evt_instruction",
            "type": "developer_instruction",
            "sequence": 0,
            "content": "Use approved tools only.",
        },
        {
            "id": "evt_model",
            "type": "model_call",
            "sequence": 0,
            "model": "example-model",
            "input": {"messages": ["Hello."]},
            "output": {"content": "I will help."},
        },
        {
            "id": "evt_tool_call",
            "type": "tool_call",
            "sequence": 0,
            "tool_name": "lookup_account",
            "arguments": {"account_id": "A-100"},
        },
        {
            "id": "evt_tool_result",
            "type": "tool_result",
            "sequence": 0,
            "tool_name": "lookup_account",
            "call_id": "evt_tool_call",
            "result": {"status": "active"},
        },
        {
            "id": "evt_approval",
            "type": "approval",
            "sequence": 0,
            "decision": "approved",
            "subject_event": "evt_tool_call",
            "approved_by": "user",
        },
        {
            "id": "evt_final",
            "type": "final_answer",
            "sequence": 0,
            "content": "Account A-100 is active.",
            "claims": [
                {
                    "id": "claim_1",
                    "text": "Account A-100 is active.",
                }
            ],
        },
    ],
)
def test_supported_event_types_parse(event: dict) -> None:
    trace = make_trace([event])

    assert trace.events[0].id == event["id"]


@pytest.mark.parametrize("edge_type", ["parent", "data_flow", "approval_for", "provenance"])
def test_supported_edge_types_parse(edge_type: str) -> None:
    trace = make_trace(
        [
            {
                "id": "evt_1",
                "type": "user_message",
                "sequence": 0,
                "content": "Hello.",
            },
            {
                "id": "evt_2",
                "type": "final_answer",
                "sequence": 1,
                "content": "Hello.",
            },
        ],
        [
            {
                "id": f"edge_{edge_type}",
                "type": edge_type,
                "from_event": "evt_1",
                "to_event": "evt_2",
            }
        ],
    )

    assert trace.edges[0].type == edge_type


def test_trace_allows_duplicate_event_ids_for_structural_validation() -> None:
    event = {
        "id": "evt_duplicate",
        "type": "user_message",
        "sequence": 0,
        "content": "Hello.",
    }

    trace = make_trace([event, {**event, "sequence": 1}])

    assert [trace_event.id for trace_event in trace.events] == [
        "evt_duplicate",
        "evt_duplicate",
    ]


def test_trace_allows_duplicate_edge_ids_for_structural_validation() -> None:
    events = [
        {
            "id": "evt_1",
            "type": "user_message",
            "sequence": 0,
            "content": "Hello.",
        },
        {
            "id": "evt_2",
            "type": "final_answer",
            "sequence": 1,
            "content": "Hello.",
        },
    ]
    edge = {
        "id": "edge_duplicate",
        "type": "parent",
        "from_event": "evt_1",
        "to_event": "evt_2",
    }

    trace = make_trace(events, [edge, {**edge, "type": "data_flow"}])

    assert [trace_edge.id for trace_edge in trace.edges] == [
        "edge_duplicate",
        "edge_duplicate",
    ]


def test_trace_allows_missing_edge_endpoint_for_structural_validation() -> None:
    trace = make_trace(
        [
            {
                "id": "evt_1",
                "type": "user_message",
                "sequence": 0,
                "content": "Hello.",
            }
        ],
        [
            {
                "id": "edge_missing",
                "type": "data_flow",
                "from_event": "evt_missing",
                "to_event": "evt_1",
            }
        ],
    )

    assert trace.edges[0].from_event == "evt_missing"


def test_tool_call_arguments_may_be_omitted_for_structural_validation() -> None:
    trace = make_trace(
        [
            {
                "id": "evt_tool_call",
                "type": "tool_call",
                "sequence": 0,
                "tool_name": "lookup_account",
            }
        ]
    )

    assert trace.events[0].type == "tool_call"
    assert trace.events[0].arguments is None


def test_tool_call_arguments_accept_empty_object() -> None:
    trace = make_trace(
        [
            {
                "id": "evt_tool_call",
                "type": "tool_call",
                "sequence": 0,
                "tool_name": "lookup_account",
                "arguments": {},
            }
        ]
    )

    assert trace.events[0].type == "tool_call"
    assert trace.events[0].arguments == {}


def test_tool_call_arguments_reject_invalid_type() -> None:
    with pytest.raises(ValidationError, match="dictionary"):
        make_trace(
            [
                {
                    "id": "evt_tool_call",
                    "type": "tool_call",
                    "sequence": 0,
                    "tool_name": "lookup_account",
                    "arguments": "account_id=A-100",
                }
            ]
        )


def test_claim_evidence_defaults_to_empty_list() -> None:
    trace = make_trace(
        [
            {
                "id": "evt_final",
                "type": "final_answer",
                "sequence": 0,
                "content": "Account A-100 is active.",
                "claims": [
                    {
                        "id": "claim_1",
                        "text": "Account A-100 is active.",
                    }
                ],
            }
        ]
    )

    assert trace.events[0].type == "final_answer"
    assert trace.events[0].claims[0].evidence == []


def test_claim_evidence_accepts_reference_ids() -> None:
    trace = make_trace(
        [
            {
                "id": "evt_final",
                "type": "final_answer",
                "sequence": 0,
                "content": "Account A-100 is active.",
                "claims": [
                    {
                        "id": "claim_1",
                        "text": "Account A-100 is active.",
                        "evidence": ["evt_tool_result"],
                    }
                ],
            }
        ]
    )

    assert trace.events[0].type == "final_answer"
    assert trace.events[0].claims[0].evidence == ["evt_tool_result"]


def test_claim_evidence_rejects_invalid_type() -> None:
    with pytest.raises(ValidationError, match="valid list"):
        make_trace(
            [
                {
                    "id": "evt_final",
                    "type": "final_answer",
                    "sequence": 0,
                    "content": "Account A-100 is active.",
                    "claims": [
                        {
                            "id": "claim_1",
                            "text": "Account A-100 is active.",
                            "evidence": "evt_tool_result",
                        }
                    ],
                }
            ]
        )


@pytest.mark.parametrize(
    "event",
    [
        {
            "id": "evt_tool_result",
            "type": "tool_result",
            "sequence": 0,
            "tool_name": "lookup_account",
            "call_id": "",
            "result": {},
        },
        {
            "id": "evt_approval",
            "type": "approval",
            "sequence": 0,
            "decision": "approved",
            "subject_event": "",
        },
        {
            "id": "evt_final",
            "type": "final_answer",
            "sequence": 0,
            "content": "Account A-100 is active.",
            "claims": [
                {
                    "id": "claim_1",
                    "text": "Account A-100 is active.",
                    "evidence": [""],
                }
            ],
        },
    ],
)
def test_optional_reference_strings_reject_empty_values(event: dict) -> None:
    with pytest.raises(ValidationError, match="at least 1 character"):
        make_trace([event])


def test_trace_rejects_string_sequence() -> None:
    with pytest.raises(ValidationError, match="valid integer"):
        make_trace(
            [
                {
                    "id": "evt_1",
                    "type": "user_message",
                    "sequence": "0",
                    "content": "Hello.",
                }
            ]
        )


def test_trace_json_schema_contains_event_discriminator() -> None:
    schema = Trace.model_json_schema()
    events_schema = schema["properties"]["events"]["items"]

    assert events_schema["discriminator"]["propertyName"] == "type"
