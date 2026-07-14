"""Explicit pytest integration for OpenAI Agents capture."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest

from agentlint.adapters.openai_agents import import_openai_agents_file
from agentlint.checking import check_trace
from agentlint.integrations.openai_agents import (
    OpenAIAgentsIntegrationError,
    instrument,
    reset_active_pytest_node,
    set_active_pytest_node,
)
from agentlint.policy import load_policy
from agentlint.reports import FailOn, build_report, render_text_report, report_should_fail


def pytest_addoption(parser: Any) -> None:
    group = parser.getgroup("agentlint")
    group.addoption("--agentlint", action="store_true", help="Capture OpenAI Agents traces.")
    group.addoption("--agentlint-policy", help="AgentLint YAML policy file.")
    group.addoption(
        "--agentlint-fail-on",
        choices=[item.value for item in FailOn],
        default=FailOn.ERROR.value,
    )


def pytest_configure(config: Any) -> None:
    if not config.getoption("--agentlint"):
        return
    policy_path = config.getoption("--agentlint-policy")
    if policy_path:
        try:
            config._agentlint_policy = load_policy(policy_path)
        except Exception as exc:
            raise pytest.UsageError(f"could not load AgentLint policy: {exc}") from exc
    output_dir = Path(config.rootpath) / ".agentlint" / "pytest-openai" / uuid4().hex
    try:
        config._agentlint_session = instrument(output_dir, export_mode="local_only")
    except OpenAIAgentsIntegrationError as exc:
        raise pytest.UsageError(str(exc)) from exc


def pytest_runtest_setup(item: Any) -> None:
    if item.config.getoption("--agentlint"):
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

    policy = getattr(config, "_agentlint_policy", None)
    results = []
    for path in paths:
        imported = import_openai_agents_file(path)
        results.append(check_trace(imported.trace, policy=policy, trace_path=str(path)))
    report = build_report(results, fail_on=FailOn(config.getoption("--agentlint-fail-on")))
    config._agentlint_summary = render_text_report(report)
    if report_should_fail(report) and exitstatus == 0:
        session.exitstatus = 1


def pytest_terminal_summary(terminalreporter: Any, exitstatus: int, config: Any) -> None:
    summary = getattr(config, "_agentlint_summary", None)
    if summary is not None:
        terminalreporter.section("AgentLint OpenAI Agents")
        terminalreporter.write_line(summary)
