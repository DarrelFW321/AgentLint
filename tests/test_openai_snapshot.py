import json
from pathlib import Path

import pytest

from agentlint.adapters.openai_snapshot import OpenAISnapshotError, load_openai_snapshot

ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT = ROOT / "examples" / "external" / "openai_agents" / ("function_handoff_guardrail.json")


def test_load_openai_snapshot() -> None:
    snapshot = load_openai_snapshot(SNAPSHOT)

    assert snapshot.trace_id == "trace_openai_support"
    assert len(snapshot.spans) == 7


def test_snapshot_schema_errors_do_not_echo_payload(tmp_path: Path) -> None:
    path = tmp_path / "invalid.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": "agentlint.openai_agents.snapshot.v1",
                "trace_id": "secret-payload",
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(OpenAISnapshotError) as exc_info:
        load_openai_snapshot(path)

    assert "secret-payload" not in str(exc_info.value)
