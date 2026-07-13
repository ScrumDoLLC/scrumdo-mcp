"""Spec proposal lifecycle MCP tool tests.

Uses respx to mock the ScrumDo HTTP API — no real network calls.
"""
from __future__ import annotations

import json

import pytest
import respx
from httpx import Response
from mcp.server.fastmcp import FastMCP

from spryng_mcp.config import Config
from spryng_mcp.tools import spec_proposals

CARD_ID = 201582
CARD_NUMBER = 914

CARD_STUB = {"id": CARD_ID, "number": CARD_NUMBER, "local_id": f"ON-{CARD_NUMBER}"}
LIST_PAGE_STUB = {"items": [CARD_STUB], "next": None}


def _mock_card_resolution() -> None:
    respx.get(Config.project_url("stories/")).mock(
        return_value=Response(200, json=LIST_PAGE_STUB))


def _tool(name: str):
    m = FastMCP("test")
    spec_proposals.register(m)
    return next(t for t in m._tool_manager._tools.values()
                if t.name == name).fn


@pytest.mark.asyncio
@respx.mock
async def test_generate_spec_proposal_posts_selection_and_instructions():
    _mock_card_resolution()
    route = respx.post(
        Config.project_url(f"stories/{CARD_ID}/spec-proposals/generate/")
    ).mock(return_value=Response(202, json={
        "proposal_id": "abc-123", "status": "generating",
        "agent_run_id": 42, "context_hash": "h1", "source_refs": [],
    }))
    result = await _tool("generate_spec_proposal")(
        card_ref="ON-914", instructions="focus on the retry path",
        card_fields=["due_date", "class_of_service"],
    )
    body = json.loads(route.calls.last.request.content)
    assert body == {
        "instructions": "focus on the retry path",
        "selection": {"card_fields": ["due_date", "class_of_service"]},
    }
    # 202 is a success status — the client must not raise, and must return
    # the acceptance body (not drafted content, per the async contract).
    assert result["status"] == "generating"
    assert result["agent_run_id"] == 42


@pytest.mark.asyncio
@respx.mock
async def test_list_spec_proposals():
    _mock_card_resolution()
    respx.get(Config.project_url(f"stories/{CARD_ID}/spec-proposals/")).mock(
        return_value=Response(200, json=[{"public_id": "abc-123",
                                          "status": "pending_review"}]))
    result = await _tool("list_spec_proposals")(card_ref="ON-914")
    assert result == [{"public_id": "abc-123", "status": "pending_review"}]


@pytest.mark.asyncio
@respx.mock
async def test_accept_spec_proposal_sends_empty_body():
    _mock_card_resolution()
    route = respx.post(
        Config.project_url(f"stories/{CARD_ID}/spec-proposals/abc-123/accept/")
    ).mock(return_value=Response(200, json={"content": "# Spec"}))
    await _tool("accept_spec_proposal")(card_ref="ON-914", proposal_id="abc-123")
    assert route.called
    assert json.loads(route.calls.last.request.content) == {}


@pytest.mark.asyncio
@respx.mock
async def test_reject_spec_proposal_does_not_set_request_changes():
    _mock_card_resolution()
    route = respx.post(
        Config.project_url(f"stories/{CARD_ID}/spec-proposals/abc-123/reject/")
    ).mock(return_value=Response(200, json={"status": "rejected"}))
    await _tool("reject_spec_proposal")(
        card_ref="ON-914", proposal_id="abc-123",
        reason="wrong approach", reason_code="wrong_interpretation",
    )
    body = json.loads(route.calls.last.request.content)
    assert body == {"reason": "wrong approach", "reason_code": "wrong_interpretation"}
    assert "request_changes" not in body


@pytest.mark.asyncio
@respx.mock
async def test_request_spec_proposal_changes_sets_request_changes_true():
    """The key correctness property: this hits the SAME /reject/ endpoint as
    reject_spec_proposal, distinguished only by request_changes=True — if this
    flag were ever dropped, a 'request changes' call would silently become an
    outright reject."""
    _mock_card_resolution()
    route = respx.post(
        Config.project_url(f"stories/{CARD_ID}/spec-proposals/abc-123/reject/")
    ).mock(return_value=Response(200, json={"status": "revision_requested"}))
    await _tool("request_spec_proposal_changes")(
        card_ref="ON-914", proposal_id="abc-123", reason="tighten scope",
    )
    body = json.loads(route.calls.last.request.content)
    assert body["request_changes"] is True
    assert body["reason"] == "tighten scope"


@pytest.mark.asyncio
@respx.mock
async def test_revise_spec_proposal_posts_to_revise_not_reject():
    _mock_card_resolution()
    route = respx.post(
        Config.project_url(f"stories/{CARD_ID}/spec-proposals/abc-123/revise/")
    ).mock(return_value=Response(202, json={
        "proposal_id": "def-456", "previous_proposal_id": "abc-123",
        "status": "generating", "agent_run_id": 43,
    }))
    result = await _tool("revise_spec_proposal")(
        card_ref="ON-914", proposal_id="abc-123", repo_full_name="acme/widgets",
    )
    body = json.loads(route.calls.last.request.content)
    assert body == {"repo_full_name": "acme/widgets"}
    assert result["previous_proposal_id"] == "abc-123"


# ── Slice 3b: MCP Workbench confirm_token gate ──────────────────────────────

PROPOSAL_UUID = "abc-123"


@pytest.mark.asyncio
@respx.mock
async def test_accept_forwards_confirm_token_and_runs_as_human(monkeypatch):
    # A run id in the env must NOT ride on this human-only decision.
    monkeypatch.setattr(Config, "agent_run_id", "run-99")
    _mock_card_resolution()
    route = respx.post(
        Config.project_url(f"stories/{CARD_ID}/spec-proposals/{PROPOSAL_UUID}/accept/")
    ).mock(return_value=Response(200, json={"status": "accepted"}))
    await _tool("accept_spec_proposal")(
        card_ref="ON-914", proposal_id=PROPOSAL_UUID, confirm_token="ct-1")

    assert json.loads(route.calls.last.request.content) == {"confirm_token": "ct-1"}
    assert "x-spryng-agent-run" not in route.calls.last.request.headers


@pytest.mark.asyncio
@respx.mock
async def test_preview_spec_decision_posts_action_and_returns_token():
    route = respx.post(
        Config.org_url(f"workbench/proposals/{PROPOSAL_UUID}/preview-decision/")
    ).mock(return_value=Response(200, json={
        "action": "accept", "confirm_token": "ct-xyz",
        "expires_in_seconds": 600, "gate": {"stale": False}}))
    result = await _tool("preview_spec_decision")(
        proposal_id=PROPOSAL_UUID, action="accept")

    assert json.loads(route.calls.last.request.content) == {"action": "accept"}
    assert result["confirm_token"] == "ct-xyz"


@pytest.mark.asyncio
@respx.mock
async def test_get_decision_inbox():
    respx.get(Config.org_url("decision-inbox/")).mock(
        return_value=Response(200, json={"items": [{"proposal_id": PROPOSAL_UUID}]}))
    result = await _tool("get_decision_inbox")()
    assert result["items"][0]["proposal_id"] == PROPOSAL_UUID


@pytest.mark.asyncio
@respx.mock
async def test_attest_spec_understood_posts_empty_body():
    route = respx.post(
        Config.org_url(f"workbench/proposals/{PROPOSAL_UUID}/understood/")
    ).mock(return_value=Response(200, json={"understood": True}))
    result = await _tool("attest_spec_understood")(proposal_id=PROPOSAL_UUID)
    assert json.loads(route.calls.last.request.content) == {}
    assert result["understood"] is True
