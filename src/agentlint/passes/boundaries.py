"""Apply policy-declared source and sink labels to observed tool boundaries."""

from __future__ import annotations

from agentlint.ir.v1 import JsonValue, ToolCallEvent, ToolResultEvent, Trace
from agentlint.policy import Policy


def apply_policy_boundaries(trace: Trace, policy: Policy) -> Trace:
    """Return a labeled trace without manufacturing any data-flow edge."""
    enriched = trace.model_copy(deep=True)
    for event in enriched.events:
        if isinstance(event, ToolResultEvent):
            tool = policy.tools.get(event.tool_name)
            if tool is not None and tool.result is not None:
                event.metadata = _append_label(event.metadata, "sources", tool.result.source)
        elif isinstance(event, ToolCallEvent) and event.arguments is not None:
            tool = policy.tools.get(event.tool_name)
            if tool is None:
                continue
            for argument_name, argument_policy in tool.arguments.items():
                if argument_name not in event.arguments or argument_policy.sink is None:
                    continue
                event.metadata = _append_label(event.metadata, "sinks", argument_policy.sink)
    return enriched


def _append_label(metadata: dict[str, JsonValue], key: str, label: str) -> dict[str, JsonValue]:
    updated = dict(metadata)
    existing = updated.get(key)
    labels = (
        [item for item in existing if isinstance(item, str)] if isinstance(existing, list) else []
    )
    if label not in labels:
        labels.append(label)
    updated[key] = labels
    return updated
