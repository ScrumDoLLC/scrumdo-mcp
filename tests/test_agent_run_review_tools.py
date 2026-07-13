"""Slice 3 — human-only agent-run review wrappers.

accept_proof / request_agent_replan / execute_task, and the hardened
approve_agent_plan. All run as a human principal (no run header on the write).
respx-mocked, no network.
"""
from __future__ import annotations

import json

import pytest
import respx
from httpx import Response
from mcp.server.fastmcp import FastMCP

from spryng_mcp.config import Config
from spryng_mcp.tools import agent_runs


def _tool(name: str):
    m = FastMCP("test")
    agent_runs.register(m)
    return next(t for t in m._tool_manager._tools.values() if t.name == name).fn


@pytest.mark.asyncio
@respx.mock
async def test_accept_proof_posts_review_session_as_human(monkeypatch):
    # A run id in the env must NOT ride on this human-only write.
    monkeypatch.setattr(Config, "agent_run_id", "run-99")
    route = respx.post(Config.org_url("agent-runs/55/accept-proof/")).mock(
        return_value=Response(200, json={"id": 55, "proof_accepted_by_id": 1}))
    result = await _tool("accept_proof")(run_id=55, review_session_id="sess-1")

    assert json.loads(route.calls.last.request.content) == {
        "review_session_id": "sess-1"}
    assert "x-spryng-agent-run" not in route.calls.last.request.headers
    assert result["id"] == 55


@pytest.mark.asyncio
@respx.mock
async def test_accept_proof_omits_session_when_absent():
    route = respx.post(Config.org_url("agent-runs/55/accept-proof/")).mock(
        return_value=Response(200, json={"id": 55}))
    await _tool("accept_proof")(run_id=55)
    assert json.loads(route.calls.last.request.content) == {}


@pytest.mark.asyncio
@respx.mock
async def test_request_agent_replan_posts_comment_returns_child():
    route = respx.post(Config.org_url("agent-runs/55/replan/")).mock(
        return_value=Response(201, json={"id": 56, "parent_run_id": 55}))
    result = await _tool("request_agent_replan")(
        run_id=55, comment="tighten the retry test")

    assert json.loads(route.calls.last.request.content) == {
        "comment": "tighten the retry test"}
    assert result["parent_run_id"] == 55


@pytest.mark.asyncio
@respx.mock
async def test_execute_task_posts_task_and_agent():
    route = respx.post(Config.org_url("agent-runs/execute-task/")).mock(
        return_value=Response(201, json={
            "run": {"id": 9}, "task_id": 3, "execution": {}}))
    result = await _tool("execute_task")(task_id=3, agent_id=8)

    assert json.loads(route.calls.last.request.content) == {
        "task_id": 3, "agent_id": 8}
    assert result["task_id"] == 3


@pytest.mark.asyncio
@respx.mock
async def test_approve_agent_plan_runs_as_human(monkeypatch):
    monkeypatch.setattr(Config, "agent_run_id", "run-99")
    route = respx.post(Config.org_url("agent-runs/55/approve/")).mock(
        return_value=Response(200, json={"id": 55, "state": "executing"}))
    await _tool("approve_agent_plan")(run_id=55)
    # Hardened: approve is human-only, so the run header must be suppressed.
    assert "x-spryng-agent-run" not in route.calls.last.request.headers
