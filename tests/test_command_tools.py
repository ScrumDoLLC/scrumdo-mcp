"""Governed cockpit command coverage tools.

invoke_cockpit_command + research_card / run_card_tests / tasks_from_spec /
get_card_memory / clear_card_memory. respx-mocked, no network.
"""
from __future__ import annotations

import json

import pytest
import respx
from httpx import Response
from mcp.server.fastmcp import FastMCP

from spryng_mcp.config import Config
from spryng_mcp.tools import commands

CARD_ID = 201582
CARD_STUB = {"id": CARD_ID, "number": 914, "local_id": "ON-914"}
LIST_PAGE_STUB = {"items": [CARD_STUB], "next": None}


def _mock_card_resolution() -> None:
    respx.get(Config.project_url("stories/")).mock(
        return_value=Response(200, json=LIST_PAGE_STUB))


def _tool(name: str):
    m = FastMCP("test")
    commands.register(m)
    return next(t for t in m._tool_manager._tools.values() if t.name == name).fn


@pytest.mark.asyncio
@respx.mock
async def test_invoke_cockpit_command_posts_and_runs_as_human(monkeypatch):
    monkeypatch.setattr(Config, "agent_run_id", "run-99")
    _mock_card_resolution()
    route = respx.post(
        Config.project_url(f"stories/{CARD_ID}/agent-commands/invoke/")
    ).mock(return_value=Response(200, json={
        "status": "queued", "dispatch_kind": "skill_chat",
        "command_id": "skill.qa-checklist", "run_id": 7}))
    result = await _tool("invoke_cockpit_command")(
        card_ref="ON-914", command_id="skill.qa-checklist",
        args={"slug": "qa-checklist"}, agent_profile_id=28)

    assert json.loads(route.calls.last.request.content) == {
        "command_id": "skill.qa-checklist",
        "args": {"slug": "qa-checklist"}, "agent_profile_id": 28}
    assert "x-spryng-agent-run" not in route.calls.last.request.headers
    assert result["run_id"] == 7


@pytest.mark.asyncio
@respx.mock
async def test_research_card_posts_brief():
    _mock_card_resolution()
    route = respx.post(Config.org_url("agent-runs/research/")).mock(
        return_value=Response(201, json={"run": {"id": 9, "kind": "research"}}))
    await _tool("research_card")(card_ref="ON-914", brief="find the retry edge cases")
    assert json.loads(route.calls.last.request.content) == {
        "card_id": CARD_ID, "brief": "find the retry edge cases"}


@pytest.mark.asyncio
@respx.mock
async def test_run_card_tests_posts_command():
    _mock_card_resolution()
    route = respx.post(Config.org_url("agent-runs/test-run/")).mock(
        return_value=Response(201, json={"run": {"id": 10, "kind": "test_run"}}))
    await _tool("run_card_tests")(card_ref="ON-914", test_command="pytest -q")
    assert json.loads(route.calls.last.request.content) == {
        "card_id": CARD_ID, "test_command": "pytest -q"}


@pytest.mark.asyncio
@respx.mock
async def test_tasks_from_spec_posts_spec_ref():
    _mock_card_resolution()
    route = respx.post(Config.org_url("agent-runs/tasks-from-spec/")).mock(
        return_value=Response(201, json={"run": {"id": 11}}))
    await _tool("tasks_from_spec")(
        card_ref="ON-914", spec_ref="@spec://requirements")
    assert json.loads(route.calls.last.request.content) == {
        "card_id": CARD_ID, "spec_ref": "@spec://requirements"}


@pytest.mark.asyncio
@respx.mock
async def test_get_card_memory_reads():
    _mock_card_resolution()
    respx.get(Config.project_url(f"stories/{CARD_ID}/memory/")).mock(
        return_value=Response(200, json={"entries": [], "count": 0}))
    result = await _tool("get_card_memory")(card_ref="ON-914")
    assert result["count"] == 0


@pytest.mark.asyncio
@respx.mock
async def test_clear_card_memory_posts_as_human(monkeypatch):
    monkeypatch.setattr(Config, "agent_run_id", "run-99")
    _mock_card_resolution()
    route = respx.post(Config.project_url(f"stories/{CARD_ID}/memory/clear/")).mock(
        return_value=Response(200, json={"cleared": True}))
    result = await _tool("clear_card_memory")(card_ref="ON-914")
    assert json.loads(route.calls.last.request.content) == {}
    assert "x-spryng-agent-run" not in route.calls.last.request.headers
    assert result["cleared"] is True
