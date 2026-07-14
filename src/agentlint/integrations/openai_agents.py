"""Local capture integration for the OpenAI Agents SDK."""

from __future__ import annotations

import json
import threading
from contextvars import ContextVar
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any, Literal
from uuid import uuid4

from agentlint.adapters.openai_snapshot import OpenAISpanSnapshot, OpenAITraceSnapshot

SUPPORTED_OPENAI_AGENTS_MINOR = (0, 18)
_active_pytest_node: ContextVar[str | None] = ContextVar(
    "agentlint_openai_pytest_node", default=None
)
_instrumented_session: OpenAICaptureSession | None = None


class OpenAIAgentsIntegrationError(Exception):
    """Raised when OpenAI Agents capture cannot be activated."""


class AgentLintTraceProcessor:
    """Thread-safe SDK tracing processor that persists local snapshots."""

    def __init__(self, output_dir: str | Path) -> None:
        self.output_dir = Path(output_dir)
        self._lock = threading.RLock()
        self._traces: dict[str, dict[str, Any]] = {}
        self._closed = False

    def on_trace_start(self, trace: Any) -> None:
        with self._lock:
            if self._closed:
                return
            exported = _safe_export(trace)
            trace_id = str(getattr(trace, "trace_id", exported.get("id", "")))
            metadata = exported.get("metadata")
            safe_metadata = metadata if isinstance(metadata, dict) else {}
            node_id = _active_pytest_node.get()
            if node_id:
                safe_metadata = {**safe_metadata, "pytest_node_id": node_id}
            self._traces[trace_id] = {
                "trace_id": trace_id,
                "workflow_name": str(
                    getattr(trace, "name", exported.get("workflow_name", "Agent workflow"))
                ),
                "group_id": _optional_string(exported.get("group_id")),
                "metadata": safe_metadata,
                "spans": [],
                "capture_incidents": [],
            }

    def on_trace_end(self, trace: Any) -> None:
        trace_id = str(getattr(trace, "trace_id", ""))
        with self._lock:
            if trace_id not in self._traces:
                self.on_trace_start(trace)
            self._persist(trace_id)

    def on_span_start(self, span: Any) -> None:
        return None

    def on_span_end(self, span: Any) -> None:
        trace_id = str(getattr(span, "trace_id", ""))
        with self._lock:
            trace_data = self._traces.get(trace_id)
            if trace_data is None:
                trace_data = {
                    "trace_id": trace_id,
                    "workflow_name": "Agent workflow",
                    "group_id": None,
                    "metadata": {},
                    "spans": [],
                    "capture_incidents": ["SPAN_RECEIVED_BEFORE_TRACE"],
                }
                self._traces[trace_id] = trace_data
            try:
                span_data = _safe_export(getattr(span, "span_data", None))
                span_type = str(span_data.pop("type", "unknown"))
                trace_data["spans"].append(
                    OpenAISpanSnapshot(
                        trace_id=trace_id,
                        span_id=str(getattr(span, "span_id", "")),
                        parent_id=_optional_string(getattr(span, "parent_id", None)),
                        started_at=_optional_string(getattr(span, "started_at", None)),
                        ended_at=_optional_string(getattr(span, "ended_at", None)),
                        has_error=getattr(span, "error", None) is not None,
                        span_type=span_type,
                        span_data=_json_safe_mapping(span_data),
                    )
                )
            except Exception:
                trace_data["capture_incidents"].append("SPAN_SNAPSHOT_FAILED")

    def shutdown(self) -> None:
        with self._lock:
            if self._closed:
                return
            self.force_flush()
            self._closed = True

    def force_flush(self) -> None:
        with self._lock:
            for trace_id in list(self._traces):
                self._persist(trace_id)

    def snapshot_paths(self) -> list[Path]:
        if not self.output_dir.exists():
            return []
        return sorted(self.output_dir.glob("*.openai-agents.json"))

    def record_explicit_span(
        self,
        trace_id: str,
        *,
        span_id: str,
        span_type: str,
        span_data: dict[str, Any],
    ) -> None:
        """Record application-provided semantics omitted by SDK tracing."""
        with self._lock:
            trace_data = self._traces.get(trace_id)
            if trace_data is None:
                raise OpenAIAgentsIntegrationError(f"unknown captured trace id: {trace_id}")
            trace_data["spans"].append(
                OpenAISpanSnapshot(
                    trace_id=trace_id,
                    span_id=span_id,
                    span_type=span_type,
                    span_data=_json_safe_mapping(span_data),
                )
            )
            self._persist(trace_id)

    def _persist(self, trace_id: str) -> None:
        data = self._traces.get(trace_id)
        if data is None or not trace_id:
            return
        snapshot = OpenAITraceSnapshot(
            **data,
            sdk_version=_installed_sdk_version(required=False),
        )
        self.output_dir.mkdir(parents=True, exist_ok=True)
        target = self.output_dir / f"{_safe_filename(trace_id)}.openai-agents.json"
        temporary = target.with_suffix(target.suffix + ".tmp")
        temporary.write_text(snapshot.model_dump_json(indent=2), encoding="utf-8")
        temporary.replace(target)


class OpenAICaptureSession:
    """Handle for an installed AgentLint SDK tracing processor."""

    def __init__(self, processor: AgentLintTraceProcessor) -> None:
        self.processor = processor
        self._closed = False

    def flush(self) -> list[Path]:
        if self._closed:
            return self.processor.snapshot_paths()
        try:
            from agents import flush_traces

            flush_traces()
        except ImportError as exc:
            raise OpenAIAgentsIntegrationError("openai-agents is not installed") from exc
        self.processor.force_flush()
        return self.processor.snapshot_paths()

    def close(self) -> list[Path]:
        if not self._closed:
            paths = self.flush()
            self.processor.shutdown()
            self._closed = True
            return paths
        return self.processor.snapshot_paths()

    def record_result(self, trace_id: str, result: Any) -> None:
        """Record an authoritative final output from an SDK RunResult."""
        output = getattr(result, "final_output", None)
        if output is None:
            raise OpenAIAgentsIntegrationError("run result has no final_output")
        self.processor.record_explicit_span(
            trace_id,
            span_id=f"agentlint_final_{_safe_filename(trace_id)}",
            span_type="agentlint_final_answer",
            span_data={"content": str(output)},
        )

    def record_approval(
        self,
        trace_id: str,
        subject_event: str,
        *,
        decision: Literal["approved", "denied"],
    ) -> None:
        """Record an explicit application approval decision."""
        self.processor.record_explicit_span(
            trace_id,
            span_id=f"agentlint_approval_{subject_event}",
            span_type="agentlint_approval",
            span_data={"decision": decision, "subject_event": subject_event},
        )

    def record_current_approval(self, *, decision: Literal["approved", "denied"]) -> None:
        """Record a decision for the active SDK function span."""
        trace_id, span_id = _active_trace_and_span(require_span=True)
        self.record_approval(trace_id, span_id, decision=decision)

    def record_source(
        self,
        trace_id: str,
        *,
        name: str,
        sensitivity: str | None = None,
        trust: str | None = None,
    ) -> str:
        """Record a symbolic source boundary without persisting its value."""
        event_id = f"agentlint_source_{uuid4().hex}"
        self.processor.record_explicit_span(
            trace_id,
            span_id=event_id,
            span_type="agentlint_source",
            span_data={"name": name, "sensitivity": sensitivity, "trust": trust},
        )
        return event_id

    def record_current_source(
        self,
        *,
        name: str,
        sensitivity: str | None = None,
        trust: str | None = None,
    ) -> str:
        """Record a symbolic source in the active SDK trace."""
        trace_id, _ = _active_trace_and_span(require_span=False)
        return self.record_source(
            trace_id,
            name=name,
            sensitivity=sensitivity,
            trust=trust,
        )

    def record_sink(
        self,
        trace_id: str,
        *,
        name: str,
        target_event: str,
        source_events: list[str],
        visibility: str | None = None,
    ) -> str:
        """Declare source-to-sink flow using labels and event identifiers only."""
        span_id = f"agentlint_sink_{uuid4().hex}"
        self.processor.record_explicit_span(
            trace_id,
            span_id=span_id,
            span_type="agentlint_sink",
            span_data={
                "name": name,
                "target_event": target_event,
                "source_events": source_events,
                "visibility": visibility,
            },
        )
        return span_id

    def record_current_sink(
        self,
        *,
        name: str,
        source_events: list[str],
        visibility: str | None = None,
    ) -> str:
        """Declare flow into the active SDK function span."""
        trace_id, span_id = _active_trace_and_span(require_span=True)
        return self.record_sink(
            trace_id,
            name=name,
            target_event=span_id,
            source_events=source_events,
            visibility=visibility,
        )


def instrument(
    output_dir: str | Path = ".agentlint/openai-agents",
    *,
    export_mode: Literal["additive", "local_only"] = "additive",
) -> OpenAICaptureSession:
    """Register AgentLint capture once in the current Python process."""
    global _instrumented_session
    if _instrumented_session is not None:
        return _instrumented_session

    _installed_sdk_version(required=True)
    try:
        from agents import add_trace_processor, set_trace_processors
    except ImportError as exc:
        raise OpenAIAgentsIntegrationError(
            'openai-agents is required; install "agentlint-trace[openai-agents]"'
        ) from exc

    processor = AgentLintTraceProcessor(output_dir)
    if export_mode == "local_only":
        set_trace_processors([processor])
    else:
        add_trace_processor(processor)
    _instrumented_session = OpenAICaptureSession(processor)
    return _instrumented_session


def set_active_pytest_node(node_id: str | None):
    """Set test association for traces started in the current context."""
    return _active_pytest_node.set(node_id)


def reset_active_pytest_node(token: Any) -> None:
    """Restore the prior test association context."""
    _active_pytest_node.reset(token)


def _installed_sdk_version(*, required: bool) -> str | None:
    try:
        installed = version("openai-agents")
    except PackageNotFoundError as exc:
        if required:
            raise OpenAIAgentsIntegrationError(
                'openai-agents is required; install "agentlint-trace[openai-agents]"'
            ) from exc
        return None
    components = installed.split(".")
    try:
        minor = (int(components[0]), int(components[1]))
    except (IndexError, ValueError) as exc:
        raise OpenAIAgentsIntegrationError(
            f"could not interpret openai-agents version {installed}"
        ) from exc
    if minor != SUPPORTED_OPENAI_AGENTS_MINOR:
        raise OpenAIAgentsIntegrationError(
            f"unsupported openai-agents version {installed}; expected >=0.18,<0.19"
        )
    return installed


def _safe_export(value: Any) -> dict[str, Any]:
    if value is None or not hasattr(value, "export"):
        return {}
    exported = value.export()
    return exported if isinstance(exported, dict) else {}


def _json_safe_mapping(value: dict[str, Any]) -> dict[str, Any]:
    try:
        return json.loads(json.dumps(value, default=str))
    except (TypeError, ValueError):
        return {}


def _optional_string(value: Any) -> str | None:
    return value if isinstance(value, str) and value else None


def _safe_filename(value: str) -> str:
    sanitized = "".join(
        character if character.isalnum() or character in "-_" else "_" for character in value
    )
    return sanitized[:120] or "trace"


def _active_trace_and_span(*, require_span: bool) -> tuple[str, str]:
    try:
        from agents.tracing import get_current_span, get_current_trace
    except ImportError as exc:
        raise OpenAIAgentsIntegrationError("openai-agents is not installed") from exc

    trace = get_current_trace()
    span = get_current_span()
    trace_id = getattr(trace, "trace_id", None)
    span_id = getattr(span, "span_id", None)
    if not isinstance(trace_id, str) or not trace_id:
        raise OpenAIAgentsIntegrationError(
            "no active OpenAI Agents trace; call this helper during a traced agent run"
        )
    if require_span and (not isinstance(span_id, str) or not span_id):
        raise OpenAIAgentsIntegrationError(
            "no active OpenAI Agents span; call this helper inside the relevant function tool"
        )
    return trace_id, span_id if isinstance(span_id, str) else ""
