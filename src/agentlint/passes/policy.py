"""Policy evaluation pass for AgentLint IR traces."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from agentlint.diagnostics import (
    Diagnostic,
    DiagnosticCode,
    DiagnosticPath,
    DiagnosticPathEdge,
    DiagnosticPathNode,
    Severity,
)
from agentlint.ir.v1 import (
    ApprovalEvent,
    Edge,
    Event,
    FinalAnswerEvent,
    JsonValue,
    ToolCallEvent,
    Trace,
)
from agentlint.passes.boundaries import apply_policy_boundaries
from agentlint.policy import (
    ApprovalRequirement,
    ArgumentType,
    CompiledPolicyPlan,
    Policy,
    PolicyException,
    PolicySeverity,
    RuleId,
    Sensitivity,
    SinkPolicy,
    SinkVisibility,
    SourcePolicy,
    ToolPermission,
    ToolRisk,
    TrustLevel,
    compile_policy,
)

_RULE_TO_CODE = {
    RuleId.UNKNOWN_TOOL: DiagnosticCode.UNKNOWN_TOOL,
    RuleId.DENIED_TOOL_CALL: DiagnosticCode.DENIED_TOOL_CALL,
    RuleId.DISALLOWED_TOOL_ARGUMENT: DiagnosticCode.DISALLOWED_TOOL_ARGUMENT,
    RuleId.MISSING_APPROVAL: DiagnosticCode.MISSING_APPROVAL,
    RuleId.APPROVAL_AFTER_ACTION: DiagnosticCode.APPROVAL_AFTER_ACTION,
    RuleId.ACTION_AFTER_DENIAL: DiagnosticCode.ACTION_AFTER_DENIAL,
    RuleId.APPROVAL_MISMATCH: DiagnosticCode.APPROVAL_MISMATCH,
    RuleId.PRIVATE_TO_PUBLIC_SINK: DiagnosticCode.PRIVATE_TO_PUBLIC_SINK,
    RuleId.SECRET_EXPOSURE: DiagnosticCode.SECRET_EXPOSURE,
    RuleId.UNTRUSTED_TO_PRIVILEGED_ACTION: DiagnosticCode.UNTRUSTED_TO_PRIVILEGED_ACTION,
    RuleId.SENSITIVE_FINAL_ANSWER: DiagnosticCode.SENSITIVE_FINAL_ANSWER,
    RuleId.UNSUPPORTED_CLAIM: DiagnosticCode.UNSUPPORTED_CLAIM,
    RuleId.INVALID_PROVENANCE_REFERENCE: DiagnosticCode.INVALID_PROVENANCE_REFERENCE,
    RuleId.EVIDENCE_AFTER_CLAIM: DiagnosticCode.EVIDENCE_AFTER_CLAIM,
}

_POLICY_TO_DIAGNOSTIC_SEVERITY = {
    PolicySeverity.ERROR: Severity.ERROR,
    PolicySeverity.WARNING: Severity.WARNING,
    PolicySeverity.INFO: Severity.INFO,
}


@dataclass(frozen=True)
class _CandidateDiagnostic:
    rule_id: RuleId
    diagnostic: Diagnostic
    tool: str | None = None
    source: str | None = None
    sink: str | None = None


def evaluate_policy(
    trace: Trace,
    policy: Policy,
    *,
    plan: CompiledPolicyPlan | None = None,
) -> list[Diagnostic]:
    """Evaluate a parsed policy against a structurally valid trace."""
    trace = apply_policy_boundaries(trace, policy)
    events_by_id = {event.id: event for event in trace.events}
    context = _EvaluationContext(
        trace=trace,
        policy=policy,
        plan=plan or compile_policy(policy),
        source_policies=policy.effective_sources(),
        sink_policies=policy.effective_sinks(),
        events_by_id=events_by_id,
    )

    candidates: list[_CandidateDiagnostic] = []
    candidates.extend(_tool_check_candidates(context))
    candidates.extend(_approval_mismatch_candidates(context))
    candidates.extend(_required_approval_candidates(context))
    candidates.extend(_data_flow_candidates(context))
    candidates.extend(_provenance_candidates(context))

    return [
        candidate.diagnostic
        for candidate in candidates
        if not _is_suppressed_by_exception(policy, candidate)
    ]


@dataclass(frozen=True)
class _EvaluationContext:
    trace: Trace
    policy: Policy
    plan: CompiledPolicyPlan
    source_policies: dict[str, SourcePolicy]
    sink_policies: dict[str, SinkPolicy]
    events_by_id: dict[str, Event]


def _tool_check_candidates(context: _EvaluationContext) -> list[_CandidateDiagnostic]:
    candidates: list[_CandidateDiagnostic] = []

    for event in context.trace.events:
        if not isinstance(event, ToolCallEvent):
            continue

        tool_policy = context.policy.tools.get(event.tool_name)
        if tool_policy is None:
            candidate = _candidate(
                context,
                RuleId.UNKNOWN_TOOL,
                f'tool call "{event.id}" uses unknown tool "{event.tool_name}"',
                related_events=[event.id],
                remediation="Add the tool to the policy or remove the tool call from the trace.",
                tool=event.tool_name,
            )
            _append_if_enabled(candidates, candidate)
            continue

        if tool_policy.permission == ToolPermission.DENIED:
            candidate = _candidate(
                context,
                RuleId.DENIED_TOOL_CALL,
                f'tool call "{event.id}" uses tool "{event.tool_name}" denied by trace policy',
                related_events=[event.id],
                remediation=(
                    "Remove the call or update the trace policy when this tool should be permitted."
                ),
                tool=event.tool_name,
            )
            _append_if_enabled(candidates, candidate)
            continue

        if event.arguments is None:
            continue

        for argument_name, argument_policy in tool_policy.arguments.items():
            if argument_name not in event.arguments:
                if argument_policy.required:
                    candidate = _candidate(
                        context,
                        RuleId.DISALLOWED_TOOL_ARGUMENT,
                        (f'tool call "{event.id}" is missing required argument "{argument_name}"'),
                        related_events=[event.id],
                        remediation="Provide the required tool argument.",
                        tool=event.tool_name,
                    )
                    _append_if_enabled(candidates, candidate)
                continue

            argument_value = event.arguments[argument_name]
            if argument_policy.allowed_types is not None and not _matches_any_type(
                argument_value,
                argument_policy.allowed_types,
            ):
                allowed_types = ", ".join(
                    argument_type.value for argument_type in argument_policy.allowed_types
                )
                candidate = _candidate(
                    context,
                    RuleId.DISALLOWED_TOOL_ARGUMENT,
                    (
                        f'tool call "{event.id}" argument "{argument_name}" has disallowed '
                        f"type; expected one of: {allowed_types}"
                    ),
                    related_events=[event.id],
                    remediation="Pass an argument value with an allowed JSON type.",
                    tool=event.tool_name,
                )
                _append_if_enabled(candidates, candidate)
                continue

            if (
                argument_policy.allowed_values is not None
                and argument_value not in argument_policy.allowed_values
            ):
                candidate = _candidate(
                    context,
                    RuleId.DISALLOWED_TOOL_ARGUMENT,
                    (
                        f'tool call "{event.id}" argument "{argument_name}" has a value '
                        "that is not allowed by policy"
                    ),
                    related_events=[event.id],
                    remediation="Use one of the values allowed by the policy.",
                    tool=event.tool_name,
                )
                _append_if_enabled(candidates, candidate)

    return candidates


def _approval_mismatch_candidates(context: _EvaluationContext) -> list[_CandidateDiagnostic]:
    candidates: list[_CandidateDiagnostic] = []
    outgoing_approval_edges = _outgoing_approval_edges(context.trace)

    for event in context.trace.events:
        if not isinstance(event, ApprovalEvent):
            continue

        edge_targets = [edge.to_event for edge in outgoing_approval_edges[event.id]]
        subject_target = event.subject_event

        if subject_target is not None:
            for edge in outgoing_approval_edges[event.id]:
                if edge.to_event == subject_target:
                    continue

                candidate = _candidate(
                    context,
                    RuleId.APPROVAL_MISMATCH,
                    (
                        f'approval event "{event.id}" references subject "{subject_target}" '
                        f'but approval edge "{edge.id}" targets "{edge.to_event}"'
                    ),
                    related_events=[event.id, subject_target, edge.to_event],
                    related_edges=[edge.id],
                    remediation="Make approval subject_event and approval_for edge targets agree.",
                )
                _append_if_enabled(candidates, candidate)

        for target_id in _unique_strings([subject_target, *edge_targets]):
            target_event = context.events_by_id.get(target_id)
            if isinstance(target_event, ToolCallEvent):
                continue

            candidate = _candidate(
                context,
                RuleId.APPROVAL_MISMATCH,
                f'approval event "{event.id}" targets non-tool-call event "{target_id}"',
                related_events=[event.id, target_id],
                remediation="Point approval events only at tool_call events.",
            )
            _append_if_enabled(candidates, candidate)

    return candidates


def _required_approval_candidates(context: _EvaluationContext) -> list[_CandidateDiagnostic]:
    candidates: list[_CandidateDiagnostic] = []
    approvals_by_target = _approvals_by_target(context.trace)

    for event in context.trace.events:
        if not isinstance(event, ToolCallEvent):
            continue

        tool_policy = context.policy.tools.get(event.tool_name)
        if tool_policy is None:
            continue
        if tool_policy.permission == ToolPermission.DENIED:
            continue
        if tool_policy.approval != ApprovalRequirement.REQUIRED:
            continue

        approvals = approvals_by_target[event.id]
        prior_denials = [
            approval
            for approval in approvals
            if approval.decision == "denied" and approval.sequence < event.sequence
        ]
        if prior_denials:
            denial = prior_denials[0]
            candidate = _candidate(
                context,
                RuleId.ACTION_AFTER_DENIAL,
                (
                    f'tool call "{event.id}" ran after approval event "{denial.id}" '
                    "denied the action"
                ),
                related_events=[denial.id, event.id],
                remediation="Do not execute an action after it has been denied.",
                tool=event.tool_name,
            )
            _append_if_enabled(candidates, candidate)
            continue

        prior_approvals = [
            approval
            for approval in approvals
            if approval.decision == "approved" and approval.sequence < event.sequence
        ]
        if prior_approvals:
            continue

        late_approvals = [
            approval
            for approval in approvals
            if approval.decision == "approved" and approval.sequence > event.sequence
        ]
        if late_approvals:
            approval = late_approvals[0]
            candidate = _candidate(
                context,
                RuleId.APPROVAL_AFTER_ACTION,
                (
                    f'tool call "{event.id}" executed before approval event '
                    f'"{approval.id}" approved it'
                ),
                related_events=[event.id, approval.id],
                remediation="Record approval before executing the tool call.",
                tool=event.tool_name,
            )
            _append_if_enabled(candidates, candidate)
            continue

        candidate = _candidate(
            context,
            RuleId.MISSING_APPROVAL,
            f'tool call "{event.id}" requires prior approval for tool "{event.tool_name}"',
            related_events=[event.id],
            remediation="Add a prior approved approval event for this tool call.",
            tool=event.tool_name,
        )
        _append_if_enabled(candidates, candidate)

    return candidates


def _data_flow_candidates(context: _EvaluationContext) -> list[_CandidateDiagnostic]:
    candidates: list[_CandidateDiagnostic] = []
    upstream_by_event = _upstream_data_flow_events(context.trace)

    for event in context.trace.events:
        upstream_sources = _upstream_source_contexts(context, event.id, upstream_by_event[event.id])
        if not upstream_sources:
            continue

        candidates.extend(_sink_exposure_candidates(context, event, upstream_sources))
        candidates.extend(_untrusted_privileged_action_candidates(context, event, upstream_sources))
        candidates.extend(_sensitive_final_answer_candidates(context, event, upstream_sources))

    return candidates


def _sink_exposure_candidates(
    context: _EvaluationContext,
    event: Event,
    upstream_sources: list[_SourceContext],
) -> list[_CandidateDiagnostic]:
    candidates: list[_CandidateDiagnostic] = []

    for sink_label in _sink_labels(event):
        sink_policy = context.sink_policies.get(sink_label)
        if sink_policy is None:
            continue

        for source in upstream_sources:
            if source.policy.sensitivity == Sensitivity.SECRET and sink_policy.visibility in {
                SinkVisibility.PUBLIC,
                SinkVisibility.MODEL,
                SinkVisibility.PRIVATE,
            }:
                candidate = _candidate(
                    context,
                    RuleId.SECRET_EXPOSURE,
                    (
                        f'secret source "{source.label}" reaches sink "{sink_label}" '
                        f'at event "{event.id}"'
                    ),
                    related_events=[source.event.id, event.id],
                    remediation="Keep secret data out of model, private, and public sinks.",
                    tool=_tool_name(event),
                    source=source.label,
                    sink=sink_label,
                )
                _append_if_enabled(candidates, candidate)
                continue

            if (
                source.policy.sensitivity in {Sensitivity.PRIVATE, Sensitivity.SECRET}
                and sink_policy.visibility == SinkVisibility.PUBLIC
            ):
                candidate = _candidate(
                    context,
                    RuleId.PRIVATE_TO_PUBLIC_SINK,
                    (
                        f'private source "{source.label}" reaches public sink "{sink_label}" '
                        f'at event "{event.id}"'
                    ),
                    related_events=[source.event.id, event.id],
                    remediation="Route private data only to non-public sinks.",
                    tool=_tool_name(event),
                    source=source.label,
                    sink=sink_label,
                )
                _append_if_enabled(candidates, candidate)

    return candidates


def _untrusted_privileged_action_candidates(
    context: _EvaluationContext,
    event: Event,
    upstream_sources: list[_SourceContext],
) -> list[_CandidateDiagnostic]:
    if not isinstance(event, ToolCallEvent):
        return []

    tool_policy = context.policy.tools.get(event.tool_name)
    if tool_policy is None:
        return []

    is_privileged = (
        tool_policy.risk in {ToolRisk.HIGH, ToolRisk.CRITICAL}
        or tool_policy.approval == ApprovalRequirement.REQUIRED
        or tool_policy.permission == ToolPermission.DENIED
    )
    if not is_privileged:
        return []

    candidates: list[_CandidateDiagnostic] = []
    for source in upstream_sources:
        if source.policy.trust != TrustLevel.UNTRUSTED:
            continue

        candidate = _candidate(
            context,
            RuleId.UNTRUSTED_TO_PRIVILEGED_ACTION,
            (f'untrusted source "{source.label}" influences privileged tool call "{event.id}"'),
            related_events=[source.event.id, event.id],
            remediation="Require trusted mediation before privileged tool actions.",
            tool=event.tool_name,
            source=source.label,
        )
        _append_if_enabled(candidates, candidate)

    return candidates


def _sensitive_final_answer_candidates(
    context: _EvaluationContext,
    event: Event,
    upstream_sources: list[_SourceContext],
) -> list[_CandidateDiagnostic]:
    if not isinstance(event, FinalAnswerEvent):
        return []

    candidates: list[_CandidateDiagnostic] = []
    for source in upstream_sources:
        if source.policy.sensitivity not in {Sensitivity.PRIVATE, Sensitivity.SECRET}:
            continue

        candidate = _candidate(
            context,
            RuleId.SENSITIVE_FINAL_ANSWER,
            f'sensitive source "{source.label}" reaches final answer "{event.id}"',
            related_events=[source.event.id, event.id],
            remediation="Avoid exposing private or secret source data in final answers.",
            source=source.label,
            sink="final_answer",
        )
        _append_if_enabled(candidates, candidate)

    return candidates


def _provenance_candidates(context: _EvaluationContext) -> list[_CandidateDiagnostic]:
    candidates: list[_CandidateDiagnostic] = []
    provenance_pairs = {
        (edge.from_event, edge.to_event)
        for edge in context.trace.edges
        if edge.type == "provenance"
    }

    for event in context.trace.events:
        if not isinstance(event, FinalAnswerEvent):
            continue

        for claim in event.claims:
            if not claim.evidence:
                candidate = _candidate(
                    context,
                    RuleId.UNSUPPORTED_CLAIM,
                    f'claim "{claim.id}" in final answer "{event.id}" has no evidence',
                    related_events=[event.id],
                    remediation="Attach at least one evidence event id to the claim.",
                )
                _append_if_enabled(candidates, candidate)
                continue

            for evidence_id in claim.evidence:
                evidence_event = context.events_by_id.get(evidence_id)
                if evidence_event is None:
                    continue

                if (evidence_id, event.id) not in provenance_pairs:
                    candidate = _candidate(
                        context,
                        RuleId.INVALID_PROVENANCE_REFERENCE,
                        (
                            f'claim "{claim.id}" evidence "{evidence_id}" has no provenance '
                            f'edge to final answer "{event.id}"'
                        ),
                        related_events=[evidence_id, event.id],
                        remediation=(
                            "Add a provenance edge from each evidence event to the final answer."
                        ),
                    )
                    _append_if_enabled(candidates, candidate)

                if evidence_event.sequence > event.sequence:
                    candidate = _candidate(
                        context,
                        RuleId.EVIDENCE_AFTER_CLAIM,
                        (
                            f'claim "{claim.id}" uses evidence "{evidence_id}" that occurs '
                            f'after final answer "{event.id}"'
                        ),
                        related_events=[event.id, evidence_id],
                        remediation="Record evidence before the final answer that cites it.",
                    )
                    _append_if_enabled(candidates, candidate)

    return candidates


@dataclass(frozen=True)
class _SourceContext:
    label: str
    event: Event
    policy: SourcePolicy


def _upstream_source_contexts(
    context: _EvaluationContext,
    event_id: str,
    upstream_event_ids: set[str],
) -> list[_SourceContext]:
    sources: list[_SourceContext] = []

    for event in context.trace.events:
        if event.id == event_id:
            continue
        if event.id not in upstream_event_ids:
            continue

        for source_label in _source_labels(event):
            source_policy = context.source_policies.get(source_label)
            if source_policy is None:
                continue

            sources.append(_SourceContext(label=source_label, event=event, policy=source_policy))

    return sources


def _candidate(
    context: _EvaluationContext,
    rule_id: RuleId,
    message: str,
    *,
    related_events: list[str],
    remediation: str,
    related_edges: list[str] | None = None,
    tool: str | None = None,
    source: str | None = None,
    sink: str | None = None,
) -> _CandidateDiagnostic | None:
    severity = _severity_for_rule(context.plan, rule_id)
    if severity is None:
        return None

    return _CandidateDiagnostic(
        rule_id=rule_id,
        diagnostic=Diagnostic(
            code=_RULE_TO_CODE[rule_id],
            severity=severity,
            message=message,
            related_events=related_events,
            related_edges=related_edges or [],
            path=_diagnostic_path(context, related_events),
            policy_reference=f"{context.policy.policy_id}:{rule_id.value}",
            remediation=remediation,
        ),
        tool=tool,
        source=source,
        sink=sink,
    )


def _diagnostic_path(
    context: _EvaluationContext,
    related_events: list[str],
) -> DiagnosticPath | None:
    if len(related_events) < 2:
        return None
    starts = [(related_events[0], related_events[-1]), (related_events[-1], related_events[0])]
    outgoing: dict[str, list[Edge]] = defaultdict(list)
    for edge in context.trace.edges:
        outgoing[edge.from_event].append(edge)
    for edges in outgoing.values():
        edges.sort(key=lambda edge: (edge.type, edge.id, edge.to_event))

    for start, target in starts:
        queue: list[tuple[str, list[Edge]]] = [(start, [])]
        visited = {start}
        while queue:
            event_id, path_edges = queue.pop(0)
            if event_id == target and path_edges:
                event_ids = [start, *(edge.to_event for edge in path_edges)]
                return DiagnosticPath(
                    nodes=[
                        DiagnosticPathNode(
                            event_id=item,
                            label=_safe_event_label(context.events_by_id[item]),
                        )
                        for item in event_ids
                    ],
                    edges=[
                        DiagnosticPathEdge(edge_id=edge.id, edge_type=edge.type)
                        for edge in path_edges
                    ],
                )
            for edge in outgoing[event_id]:
                if edge.to_event in visited:
                    continue
                visited.add(edge.to_event)
                queue.append((edge.to_event, [*path_edges, edge]))
    return None


def _safe_event_label(event: Event) -> str:
    if isinstance(event, ToolCallEvent):
        return f"tool_call:{event.tool_name}"
    return event.type


def _append_if_enabled(
    candidates: list[_CandidateDiagnostic],
    candidate: _CandidateDiagnostic | None,
) -> None:
    if candidate is not None:
        candidates.append(candidate)


def _severity_for_rule(plan: CompiledPolicyPlan, rule_id: RuleId) -> Severity | None:
    rule = plan.rule(rule_id)
    if rule is None:
        return None
    return _POLICY_TO_DIAGNOSTIC_SEVERITY[rule.severity]


def _is_suppressed_by_exception(policy: Policy, candidate: _CandidateDiagnostic) -> bool:
    return any(
        _exception_matches(candidate, policy_exception) for policy_exception in policy.exceptions
    )


def _exception_matches(
    candidate: _CandidateDiagnostic,
    policy_exception: PolicyException,
) -> bool:
    if candidate.rule_id not in policy_exception.rules:
        return False

    match = policy_exception.match
    if match.tool is not None and match.tool != candidate.tool:
        return False
    if match.source is not None and match.source != candidate.source:
        return False
    if match.sink is not None and match.sink != candidate.sink:
        return False
    if match.event is not None and match.event not in candidate.diagnostic.related_events:
        return False

    return True


def _matches_any_type(value: JsonValue, allowed_types: list[ArgumentType]) -> bool:
    return any(_matches_type(value, allowed_type) for allowed_type in allowed_types)


def _matches_type(value: JsonValue, allowed_type: ArgumentType) -> bool:
    match allowed_type:
        case ArgumentType.NULL:
            return value is None
        case ArgumentType.BOOLEAN:
            return isinstance(value, bool)
        case ArgumentType.INTEGER:
            return isinstance(value, int) and not isinstance(value, bool)
        case ArgumentType.NUMBER:
            return isinstance(value, int | float) and not isinstance(value, bool)
        case ArgumentType.STRING:
            return isinstance(value, str)
        case ArgumentType.ARRAY:
            return isinstance(value, list)
        case ArgumentType.OBJECT:
            return isinstance(value, dict)


def _outgoing_approval_edges(trace: Trace) -> dict[str, list[Edge]]:
    outgoing_edges: dict[str, list[Edge]] = defaultdict(list)

    for edge in trace.edges:
        if edge.type == "approval_for":
            outgoing_edges[edge.from_event].append(edge)

    return outgoing_edges


def _approvals_by_target(trace: Trace) -> dict[str, list[ApprovalEvent]]:
    outgoing_approval_edges = _outgoing_approval_edges(trace)
    approvals_by_target: dict[str, list[ApprovalEvent]] = defaultdict(list)

    for event in trace.events:
        if not isinstance(event, ApprovalEvent):
            continue

        target_ids = _unique_strings(
            [
                event.subject_event,
                *(edge.to_event for edge in outgoing_approval_edges[event.id]),
            ]
        )
        for target_id in target_ids:
            approvals_by_target[target_id].append(event)

    return approvals_by_target


def _upstream_data_flow_events(trace: Trace) -> dict[str, set[str]]:
    incoming_edges: dict[str, list[str]] = defaultdict(list)
    upstream: dict[str, set[str]] = defaultdict(set)

    for edge in trace.edges:
        if edge.type == "data_flow":
            incoming_edges[edge.to_event].append(edge.from_event)

    for event in trace.events:
        visited: set[str] = set()
        stack = list(reversed(incoming_edges[event.id]))

        while stack:
            current_id = stack.pop()
            if current_id in visited:
                continue

            visited.add(current_id)
            stack.extend(reversed(incoming_edges[current_id]))

        upstream[event.id] = visited

    return upstream


def _source_labels(event: Event) -> list[str]:
    return _metadata_labels(event, "source", "sources")


def _sink_labels(event: Event) -> list[str]:
    labels = _metadata_labels(event, "sink", "sinks")

    if isinstance(event, ToolCallEvent) and event.arguments is not None:
        labels.extend(f"{event.tool_name}.{argument_name}" for argument_name in event.arguments)
    if isinstance(event, FinalAnswerEvent):
        labels.append("final_answer")

    return _unique_strings(labels)


def _metadata_labels(event: Event, singular_key: str, plural_key: str) -> list[str]:
    labels: list[str] = []
    singular_value = event.metadata.get(singular_key)
    plural_value = event.metadata.get(plural_key)

    if isinstance(singular_value, str):
        labels.append(singular_value)
    if isinstance(plural_value, list):
        labels.extend(item for item in plural_value if isinstance(item, str))

    return _unique_strings(labels)


def _unique_strings(values: list[str | None]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []

    for value in values:
        if value is None:
            continue
        if value in seen:
            continue
        seen.add(value)
        result.append(value)

    return result


def _tool_name(event: Event) -> str | None:
    if isinstance(event, ToolCallEvent):
        return event.tool_name
    return None
