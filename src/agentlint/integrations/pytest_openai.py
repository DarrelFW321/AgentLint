"""Explicit pytest integration for OpenAI Agents capture."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest

from agentlint.integrations.openai_agents import (
    OpenAIAgentsIntegrationError,
    instrument,
    reset_active_pytest_node,
    set_active_pytest_node,
)
from agentlint.integrations.pytest_runs import (
    PytestRunError,
    check_run,
    default_policy,
    load_routing_config,
    route_policy,
    write_latest_pointer,
    write_run_manifest,
)
from agentlint.policy import load_policy
from agentlint.reports import FailOn, render_text_report, report_should_fail


def pytest_addoption(parser: Any) -> None:
    group = parser.getgroup("agentlint")
    group.addoption("--agentlint", action="store_true", help="Capture OpenAI Agents traces.")
    group.addoption("--agentlint-policy", help="Default AgentLint YAML policy file.")
    group.addoption(
        "--agentlint-config",
        help="Policy routing config (default: agentlint.pytest.yaml when present).",
    )
    group.addoption(
        "--agentlint-output",
        help="Run artifact directory (default: .agentlint/runs).",
    )
    group.addoption(
        "--agentlint-fail-on",
        choices=[item.value for item in FailOn],
        default=FailOn.ERROR.value,
    )


def pytest_configure(config: Any) -> None:
    config.addinivalue_line(
        "markers",
        "agentlint(policy=None): select an AgentLint policy for traces captured by this test",
    )
    if not config.getoption("--agentlint"):
        return
    policy_path = config.getoption("--agentlint-policy")
    if policy_path:
        try:
            resolved_policy = _root_relative(config, policy_path)
            load_policy(resolved_policy)
            config._agentlint_cli_policy_path = resolved_policy
        except Exception as exc:
            raise pytest.UsageError(f"could not load AgentLint policy: {exc}") from exc
    config_path_value = config.getoption("--agentlint-config")
    config_path = (
        _root_relative(config, config_path_value)
        if config_path_value
        else Path(config.rootpath) / "agentlint.pytest.yaml"
    )
    if config_path.is_file():
        try:
            config._agentlint_routing = load_routing_config(config_path)
            config._agentlint_routing_dir = config_path.parent
        except PytestRunError as exc:
            raise pytest.UsageError(str(exc)) from exc
    runs_dir_value = config.getoption("--agentlint-output")
    runs_dir = (
        _root_relative(config, runs_dir_value)
        if runs_dir_value
        else Path(config.rootpath) / ".agentlint" / "runs"
    )
    run_id = uuid4().hex
    run_dir = runs_dir / run_id
    config._agentlint_run_id = run_id
    config._agentlint_runs_dir = runs_dir
    config._agentlint_run_dir = run_dir
    config._agentlint_policies_by_node = {}
    config._agentlint_validated_policies = set()
    try:
        config._agentlint_session = instrument(run_dir / "traces", export_mode="local_only")
    except OpenAIAgentsIntegrationError as exc:
        raise pytest.UsageError(str(exc)) from exc


def pytest_runtest_setup(item: Any) -> None:
    if item.config.getoption("--agentlint"):
        policy_path = _policy_for_item(item)
        if policy_path is not None:
            try:
                if policy_path not in item.config._agentlint_validated_policies:
                    load_policy(policy_path)
                    item.config._agentlint_validated_policies.add(policy_path)
            except Exception as exc:
                raise pytest.UsageError(
                    f"could not load AgentLint policy for {item.nodeid}: {exc}"
                ) from exc
            item.config._agentlint_policies_by_node[item.nodeid] = policy_path
        item._agentlint_context_token = set_active_pytest_node(item.nodeid)


def pytest_runtest_teardown(item: Any) -> None:
    token = getattr(item, "_agentlint_context_token", None)
    if token is not None:
        reset_active_pytest_node(token)


def pytest_sessionfinish(session: Any, exitstatus: int) -> None:
    config = session.config
    capture_session = getattr(config, "_agentlint_session", None)
    if capture_session is None:
        return
    paths = capture_session.close()
    if not paths:
        config._agentlint_summary = "error: no OpenAI Agents traces were captured"
        if exitstatus == 0:
            session.exitstatus = 1
        return

    try:
        manifest_path = write_run_manifest(
            run_dir=config._agentlint_run_dir,
            run_id=config._agentlint_run_id,
            snapshots=paths,
            policies_by_node=config._agentlint_policies_by_node,
        )
        write_latest_pointer(config._agentlint_runs_dir, config._agentlint_run_dir)
        report = check_run(
            manifest_path,
            fail_on=FailOn(config.getoption("--agentlint-fail-on")),
        )
    except Exception as exc:
        config._agentlint_summary = f"error: could not check captured run: {exc}"
        if exitstatus == 0:
            session.exitstatus = 1
        return
    config._agentlint_summary = f"run artifacts: {manifest_path}\n" + render_text_report(report)
    if report_should_fail(report) and exitstatus == 0:
        session.exitstatus = 1


def pytest_terminal_summary(terminalreporter: Any, exitstatus: int, config: Any) -> None:
    summary = getattr(config, "_agentlint_summary", None)
    if summary is not None:
        terminalreporter.section("AgentLint OpenAI Agents")
        terminalreporter.write_line(summary)


def _policy_for_item(item: Any) -> Path | None:
    marker = item.get_closest_marker("agentlint")
    if marker is not None and marker.kwargs.get("policy"):
        return _root_relative(item.config, marker.kwargs["policy"])

    routing = getattr(item.config, "_agentlint_routing", None)
    if routing is not None:
        routed = route_policy(item.nodeid, routing, item.config._agentlint_routing_dir)
        if routed is not None:
            return routed

    cli_policy = getattr(item.config, "_agentlint_cli_policy_path", None)
    if cli_policy is not None:
        return cli_policy

    if routing is not None:
        return default_policy(routing, item.config._agentlint_routing_dir)
    return None


def _root_relative(config: Any, value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else Path(config.rootpath) / path
