import pytest
from pydantic import ValidationError

from agentlint.capture import (
    CapabilityCoverage,
    CaptureCapabilities,
    CaptureCompleteness,
    CaptureStatus,
    unknown_capture,
)


def profile_with_statuses(**overrides: CaptureStatus) -> CaptureCompleteness:
    values = {
        field: CapabilityCoverage(status=overrides.get(field, CaptureStatus.CAPTURED))
        for field in CaptureCapabilities.model_fields
    }
    return CaptureCompleteness(
        adapter="test",
        capabilities=CaptureCapabilities.model_validate(values),
    )


@pytest.mark.parametrize(
    ("overrides", "expected"),
    [
        ({}, CaptureStatus.CAPTURED),
        ({"tool_calls": CaptureStatus.PARTIAL}, CaptureStatus.PARTIAL),
        ({"approvals": CaptureStatus.UNAVAILABLE}, CaptureStatus.UNAVAILABLE),
        ({"provenance": CaptureStatus.UNKNOWN}, CaptureStatus.UNKNOWN),
        (
            {
                "approvals": CaptureStatus.UNAVAILABLE,
                "provenance": CaptureStatus.UNKNOWN,
            },
            CaptureStatus.UNKNOWN,
        ),
    ],
)
def test_overall_status_is_conservative(
    overrides: dict[str, CaptureStatus], expected: CaptureStatus
) -> None:
    assert profile_with_statuses(**overrides).overall_status == expected


def test_unknown_capture_sets_every_capability() -> None:
    capture = unknown_capture(adapter="native")

    assert capture.adapter == "native"
    assert capture.overall_status == CaptureStatus.UNKNOWN
    assert all(
        coverage.status == CaptureStatus.UNKNOWN for _, coverage in capture.capabilities.entries()
    )


def test_capture_models_reject_unknown_capabilities() -> None:
    data = profile_with_statuses().model_dump(mode="json")
    data["capabilities"]["guardrails"] = {"status": "captured"}

    with pytest.raises(ValidationError):
        CaptureCompleteness.model_validate(data)


def test_capture_reasons_reject_multiline_payloads() -> None:
    with pytest.raises(ValidationError):
        CapabilityCoverage(status=CaptureStatus.PARTIAL, reason="unsafe\nraw payload")
