"""Persistent pytest run artifacts and policy routing."""

from __future__ import annotations

import hashlib
import json
from fnmatch import fnmatchcase
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from agentlint.adapters.openai_agents import import_openai_agents_file
from agentlint.adapters.openai_snapshot import load_openai_snapshot
from agentlint.checking import check_trace
from agentlint.policy import Policy, load_policy
from agentlint.reports import AgentLintReport, FailOn, build_report

RUN_MANIFEST_VERSION = "agentlint.pytest_run.v1"


class PytestRunError(Exception):
    """Raised when pytest run configuration or artifacts are invalid."""


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PolicyRoute(StrictModel):
    """Map matching pytest node IDs to a policy."""

    tests: str | list[str]
    policy: str = Field(min_length=1)

    def patterns(self) -> list[str]:
        return [self.tests] if isinstance(self.tests, str) else self.tests


class PytestRoutingConfig(StrictModel):
    """Repository-level policy routing configuration."""

    version: Literal[1] = 1
    default_policy: str | None = None
    routes: list[PolicyRoute] = Field(default_factory=list)


class RunTraceEntry(StrictModel):
    """One captured trace and the policy selected for it."""

    pytest_node_id: str = Field(min_length=1)
    trace: str = Field(min_length=1)
    policy: str = Field(min_length=1)
    policy_id: str = Field(min_length=1)


class PytestRunManifest(StrictModel):
    """Portable index for a completed pytest capture run."""

    schema_version: Literal["agentlint.pytest_run.v1"] = RUN_MANIFEST_VERSION
    run_id: str = Field(min_length=1)
    traces: list[RunTraceEntry] = Field(default_factory=list)


def load_routing_config(path: str | Path) -> PytestRoutingConfig:
    """Load policy routing from YAML."""
    config_path = Path(path)
    try:
        raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise PytestRunError(f"pytest routing config not found: {config_path}") from exc
    except yaml.YAMLError as exc:
        raise PytestRunError(f"could not parse pytest routing config: {exc}") from exc
    except OSError as exc:
        raise PytestRunError(f"could not read pytest routing config: {exc}") from exc
    try:
        return PytestRoutingConfig.model_validate(raw)
    except ValidationError as exc:
        details = "; ".join(
            ".".join(str(part) for part in error["loc"]) + f": {error['msg']}"
            for error in exc.errors(include_input=False, include_url=False)
        )
        raise PytestRunError(f"invalid pytest routing config: {details}") from exc


def route_policy(node_id: str, config: PytestRoutingConfig, config_dir: Path) -> Path | None:
    """Return the first configured policy matching a pytest node ID."""
    normalized = node_id.replace("\\", "/")
    test_path = normalized.split("::", 1)[0]
    for route in config.routes:
        if any(
            fnmatchcase(normalized, pattern.replace("\\", "/"))
            or fnmatchcase(test_path, pattern.replace("\\", "/"))
            for pattern in route.patterns()
        ):
            return _resolve_policy_path(route.policy, config_dir)
    return None


def default_policy(config: PytestRoutingConfig, config_dir: Path) -> Path | None:
    """Resolve the configured default policy, if present."""
    if config.default_policy:
        return _resolve_policy_path(config.default_policy, config_dir)
    return None


def write_run_manifest(
    *,
    run_dir: Path,
    run_id: str,
    snapshots: list[Path],
    policies_by_node: dict[str, Path],
) -> Path:
    """Copy selected policies and write a portable manifest."""
    entries: list[RunTraceEntry] = []
    copied_policies: dict[Path, tuple[Path, Policy]] = {}
    for snapshot_path in sorted(snapshots):
        snapshot = load_openai_snapshot(snapshot_path)
        node_id = snapshot.metadata.get("pytest_node_id")
        if not isinstance(node_id, str) or not node_id:
            raise PytestRunError(f"captured trace has no pytest node id: {snapshot_path.name}")
        policy_path = policies_by_node.get(node_id)
        if policy_path is None:
            raise PytestRunError(f"no AgentLint policy matched pytest test: {node_id}")
        resolved_policy = policy_path.resolve()
        copied = copied_policies.get(resolved_policy)
        if copied is None:
            policy = load_policy(resolved_policy)
            contents = resolved_policy.read_bytes()
            digest = hashlib.sha256(contents).hexdigest()[:12]
            safe_id = _safe_name(policy.policy_id)
            target = run_dir / "policies" / f"{safe_id}-{digest}.yaml"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(contents)
            copied = (target, policy)
            copied_policies[resolved_policy] = copied
        copied_path, policy = copied
        entries.append(
            RunTraceEntry(
                pytest_node_id=node_id,
                trace=_relative_path(snapshot_path, run_dir),
                policy=_relative_path(copied_path, run_dir),
                policy_id=policy.policy_id,
            )
        )
    manifest = PytestRunManifest(run_id=run_id, traces=entries)
    manifest_path = run_dir / "manifest.json"
    manifest_path.write_text(manifest.model_dump_json(indent=2), encoding="utf-8")
    return manifest_path


def load_run_manifest(path: str | Path) -> tuple[Path, PytestRunManifest]:
    """Load a manifest from a run directory or manifest path."""
    requested = Path(path)
    manifest_path = requested / "manifest.json" if requested.is_dir() else requested
    try:
        raw = json.loads(manifest_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise PytestRunError(f"pytest run manifest not found: {manifest_path}") from exc
    except json.JSONDecodeError as exc:
        raise PytestRunError(
            f"malformed pytest run manifest at line {exc.lineno}, column {exc.colno}"
        ) from exc
    except OSError as exc:
        raise PytestRunError(f"could not read pytest run manifest: {exc}") from exc
    if isinstance(raw, dict) and "manifest" in raw and "schema_version" not in raw:
        pointer_target = raw.get("manifest")
        if not isinstance(pointer_target, str) or not pointer_target:
            raise PytestRunError(f"invalid pytest run pointer: {manifest_path}")
        target = _contained_path(manifest_path.parent, pointer_target)
        return load_run_manifest(target)
    try:
        manifest = PytestRunManifest.model_validate(raw)
    except ValidationError as exc:
        raise PytestRunError("invalid pytest run manifest") from exc
    return manifest_path, manifest


def check_run(path: str | Path, *, fail_on: FailOn = FailOn.ERROR) -> AgentLintReport:
    """Check every trace in a persisted pytest run with its selected policy."""
    manifest_path, manifest = load_run_manifest(path)
    run_dir = manifest_path.parent
    results = []
    for entry in manifest.traces:
        trace_path = _contained_path(run_dir, entry.trace)
        policy_path = _contained_path(run_dir, entry.policy)
        imported = import_openai_agents_file(trace_path)
        policy = load_policy(policy_path)
        results.append(check_trace(imported.trace, policy=policy, trace_path=str(trace_path)))
    return build_report(results, fail_on=fail_on)


def write_latest_pointer(runs_dir: Path, run_dir: Path) -> Path:
    """Point to the most recently completed run without copying its artifacts."""
    pointer = runs_dir / "latest.json"
    pointer.write_text(
        json.dumps({"run": run_dir.name, "manifest": f"{run_dir.name}/manifest.json"}, indent=2),
        encoding="utf-8",
    )
    return pointer


def _resolve_policy_path(value: str, base_dir: Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else base_dir / path


def _relative_path(path: Path, base: Path) -> str:
    return path.resolve().relative_to(base.resolve()).as_posix()


def _contained_path(base: Path, relative: str) -> Path:
    target = (base / relative).resolve()
    try:
        target.relative_to(base.resolve())
    except ValueError as exc:
        raise PytestRunError(f"run artifact path leaves the run directory: {relative}") from exc
    return target


def _safe_name(value: str) -> str:
    return "".join(
        character if character.isalnum() or character in "-_" else "_" for character in value
    )
