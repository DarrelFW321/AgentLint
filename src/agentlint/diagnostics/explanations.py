"""Diagnostic code explanations for AgentLint."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from agentlint.diagnostics.models import DiagnosticCode


class DiagnosticExplanation(BaseModel):
    """Human-facing explanation for one diagnostic code."""

    model_config = ConfigDict(extra="forbid")

    code: DiagnosticCode
    category: str = Field(min_length=1)
    kind: str = Field(min_length=1)
    meaning: str = Field(min_length=1)
    remediation: str = Field(min_length=1)


_EXPLANATIONS = {
    DiagnosticCode.DUPLICATE_EVENT_ID: DiagnosticExplanation(
        code=DiagnosticCode.DUPLICATE_EVENT_ID,
        category="structural",
        kind="trace integrity",
        meaning="More than one event in the trace uses the same event id.",
        remediation="Give every event a unique id before running policy checks.",
    ),
    DiagnosticCode.DUPLICATE_EDGE_ID: DiagnosticExplanation(
        code=DiagnosticCode.DUPLICATE_EDGE_ID,
        category="structural",
        kind="trace integrity",
        meaning="More than one edge in the trace uses the same edge id.",
        remediation="Give every edge a unique id.",
    ),
    DiagnosticCode.MISSING_EVENT_REFERENCE: DiagnosticExplanation(
        code=DiagnosticCode.MISSING_EVENT_REFERENCE,
        category="structural",
        kind="trace reference",
        meaning="An edge or approval references an event id that is not present in the trace.",
        remediation="Update the reference to point at an existing event id.",
    ),
    DiagnosticCode.TOOL_RESULT_WITHOUT_MATCHING_CALL: DiagnosticExplanation(
        code=DiagnosticCode.TOOL_RESULT_WITHOUT_MATCHING_CALL,
        category="structural",
        kind="tool relationship",
        meaning="A tool result cannot be matched to a valid prior tool call.",
        remediation=(
            "Set the result call_id to the matching tool_call event and keep tool names aligned."
        ),
    ),
    DiagnosticCode.TOOL_CALL_MISSING_ARGUMENTS: DiagnosticExplanation(
        code=DiagnosticCode.TOOL_CALL_MISSING_ARGUMENTS,
        category="structural",
        kind="tool relationship",
        meaning="A tool call event has no arguments object.",
        remediation="Add an arguments object, even when the tool takes no arguments.",
    ),
    DiagnosticCode.INVALID_EVENT_ORDER: DiagnosticExplanation(
        code=DiagnosticCode.INVALID_EVENT_ORDER,
        category="structural",
        kind="event ordering",
        meaning="A relationship in the trace points backward in an invalid way.",
        remediation="Ensure ordered relationships point from earlier events to later events.",
    ),
    DiagnosticCode.INVALID_EVIDENCE_REFERENCE: DiagnosticExplanation(
        code=DiagnosticCode.INVALID_EVIDENCE_REFERENCE,
        category="structural",
        kind="provenance reference",
        meaning="A final-answer claim references evidence that does not exist in the trace.",
        remediation="Reference an existing evidence event or remove the invalid evidence id.",
    ),
    DiagnosticCode.UNKNOWN_TOOL: DiagnosticExplanation(
        code=DiagnosticCode.UNKNOWN_TOOL,
        category="policy",
        kind="tool policy",
        meaning="A tool call uses a tool that is not declared in the active policy.",
        remediation="Add the tool to the policy or remove the tool call.",
    ),
    DiagnosticCode.UNAUTHORIZED_TOOL_CALL: DiagnosticExplanation(
        code=DiagnosticCode.UNAUTHORIZED_TOOL_CALL,
        category="policy",
        kind="tool policy",
        meaning="A tool call uses a tool that the active policy marks as denied.",
        remediation="Do not call denied tools, or update the policy if the tool should be allowed.",
    ),
    DiagnosticCode.DISALLOWED_TOOL_ARGUMENT: DiagnosticExplanation(
        code=DiagnosticCode.DISALLOWED_TOOL_ARGUMENT,
        category="policy",
        kind="tool argument",
        meaning="A configured tool argument is missing or violates a policy constraint.",
        remediation="Provide required arguments and use values/types allowed by the policy.",
    ),
    DiagnosticCode.MISSING_APPROVAL: DiagnosticExplanation(
        code=DiagnosticCode.MISSING_APPROVAL,
        category="policy",
        kind="approval",
        meaning="A tool call that requires approval has no matching prior approval.",
        remediation="Record an approved approval event before executing the tool call.",
    ),
    DiagnosticCode.APPROVAL_AFTER_ACTION: DiagnosticExplanation(
        code=DiagnosticCode.APPROVAL_AFTER_ACTION,
        category="policy",
        kind="approval",
        meaning="A required approval was recorded after the action executed.",
        remediation="Require approval before the tool call is executed.",
    ),
    DiagnosticCode.ACTION_AFTER_DENIAL: DiagnosticExplanation(
        code=DiagnosticCode.ACTION_AFTER_DENIAL,
        category="policy",
        kind="approval",
        meaning="A tool call executed after a matching approval event denied it.",
        remediation="Block the action after denial or correct the approval trace.",
    ),
    DiagnosticCode.APPROVAL_MISMATCH: DiagnosticExplanation(
        code=DiagnosticCode.APPROVAL_MISMATCH,
        category="policy",
        kind="approval",
        meaning="An approval event targets the wrong event or conflicts with an approval edge.",
        remediation=(
            "Point approval metadata and approval_for edges at the intended tool_call event."
        ),
    ),
    DiagnosticCode.PRIVATE_TO_PUBLIC_SINK: DiagnosticExplanation(
        code=DiagnosticCode.PRIVATE_TO_PUBLIC_SINK,
        category="policy",
        kind="data flow",
        meaning="Private or secret source data reaches a public sink.",
        remediation="Route private data only to non-public sinks or remove the data dependency.",
    ),
    DiagnosticCode.SECRET_EXPOSURE: DiagnosticExplanation(
        code=DiagnosticCode.SECRET_EXPOSURE,
        category="policy",
        kind="data flow",
        meaning="Secret source data reaches a model-visible, private, or public sink.",
        remediation="Keep secrets out of reportable, model-visible, and external sinks.",
    ),
    DiagnosticCode.UNTRUSTED_TO_PRIVILEGED_ACTION: DiagnosticExplanation(
        code=DiagnosticCode.UNTRUSTED_TO_PRIVILEGED_ACTION,
        category="policy",
        kind="data flow",
        meaning="Untrusted source data influences a privileged tool action.",
        remediation="Insert trusted mediation before privileged actions or lower the tool risk.",
    ),
    DiagnosticCode.SENSITIVE_FINAL_ANSWER: DiagnosticExplanation(
        code=DiagnosticCode.SENSITIVE_FINAL_ANSWER,
        category="policy",
        kind="data flow",
        meaning="Private or secret source data reaches the final answer.",
        remediation="Avoid exposing sensitive source data in final answers.",
    ),
    DiagnosticCode.UNSUPPORTED_CLAIM: DiagnosticExplanation(
        code=DiagnosticCode.UNSUPPORTED_CLAIM,
        category="policy",
        kind="provenance",
        meaning="A final-answer claim has no supporting evidence events.",
        remediation="Attach at least one evidence event id to the claim.",
    ),
    DiagnosticCode.INVALID_PROVENANCE_REFERENCE: DiagnosticExplanation(
        code=DiagnosticCode.INVALID_PROVENANCE_REFERENCE,
        category="policy",
        kind="provenance",
        meaning="Claim evidence exists but lacks the required provenance edge to the final answer.",
        remediation="Add provenance edges from evidence events to the final-answer event.",
    ),
    DiagnosticCode.EVIDENCE_AFTER_CLAIM: DiagnosticExplanation(
        code=DiagnosticCode.EVIDENCE_AFTER_CLAIM,
        category="policy",
        kind="provenance",
        meaning="A final-answer claim cites evidence that occurs after the answer.",
        remediation="Record evidence before the final answer or remove the invalid citation.",
    ),
}


def explain_diagnostic_code(code: DiagnosticCode | str) -> DiagnosticExplanation | None:
    """Return an explanation for a diagnostic code."""
    try:
        diagnostic_code = code if isinstance(code, DiagnosticCode) else DiagnosticCode(code.upper())
    except ValueError:
        return None

    return _EXPLANATIONS.get(diagnostic_code)


def all_diagnostic_explanations() -> dict[DiagnosticCode, DiagnosticExplanation]:
    """Return every known diagnostic explanation keyed by code."""
    return dict(_EXPLANATIONS)
