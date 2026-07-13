"""Card AI Cockpit bridge tool tests (Slice 1).

Uses respx to mock the ScrumDo HTTP API — no real network calls.
Mirrors tests/test_spec_proposal_tools.py.
"""
from __future__ import annotations

import json

import httpx
import pytest
import respx
from httpx import Response
from mcp.server.fastmcp import FastMCP

from spryng_mcp.client import SpryngClient
from spryng_mcp.config import Config
from spryng_mcp.tools import agents, cockpit

CARD_ID = 201582
CARD_NUMBER = 914

CARD_STUB = {"id": CARD_ID, "number": CARD_NUMBER, "local_id": f"ON-{CARD_NUMBER}"}
LIST_PAGE_STUB = {"items": [CARD_STUB], "next": None}

COCKPIT_PAYLOAD = {
    "spec": {"format": "md", "content": "# Spec"},
    "permissions": {"is_agent": False, "can_read": True, "can_write_card": True},
    "available_actions": ["draft_spec", "start_loop"],
    "configured_agents": [{"id": 1, "can_chat": True, "can_execute_spec": False}],
    "runtimes": [{"id": 7, "runtime_type": "claude_code", "is_active": True}],
    "loops": [],
    "agent_runs": [{"id": 42, "state": "completed"}],
    "messages": [{"id": 1, "body_safe": "hello"}],          # large — dropped by default
    "agent_profiles": {"managed": [{"id": 3}]},              # dropped by default
}


def _mock_card_resolution() -> None:
    respx.get(Config.project_url("stories/")).mock(
        return_value=Response(200, json=LIST_PAGE_STUB))


def _tool(module, name: str):
    m = FastMCP("test")
    module.register(m)
    return next(t for t in m._tool_manager._tools.values() if t.name == name).fn


# ── get_card_cockpit_context ────────────────────────────────────────────────

@pytest.mark.asyncio
@respx.mock
async def test_cockpit_context_default_drops_messages_and_profiles():
    _mock_card_resolution()
    respx.get(Config.project_url(f"stories/{CARD_ID}/ai-cockpit/")).mock(
        return_value=Response(200, json=COCKPIT_PAYLOAD))
    result = await _tool(cockpit, "get_card_cockpit_context")(card_ref="ON-914")

    assert result["card_ref"] == "ON-914"
    assert result["story_id"] == CARD_ID
    # Compact default set present…
    for key in ("spec", "permissions", "available_actions",
                "configured_agents", "runtimes", "loops", "agent_runs"):
        assert key in result, key
    # …but the large sections are omitted unless requested.
    assert "messages" not in result
    assert "agent_profiles" not in result


@pytest.mark.asyncio
@respx.mock
async def test_cockpit_context_include_all_returns_everything():
    _mock_card_resolution()
    respx.get(Config.project_url(f"stories/{CARD_ID}/ai-cockpit/")).mock(
        return_value=Response(200, json=COCKPIT_PAYLOAD))
    result = await _tool(cockpit, "get_card_cockpit_context")(
        card_ref="ON-914", include=["all"])
    assert "messages" in result and "agent_profiles" in result


@pytest.mark.asyncio
@respx.mock
async def test_cockpit_context_explicit_include_selects_only_those():
    _mock_card_resolution()
    respx.get(Config.project_url(f"stories/{CARD_ID}/ai-cockpit/")).mock(
        return_value=Response(200, json=COCKPIT_PAYLOAD))
    result = await _tool(cockpit, "get_card_cockpit_context")(
        card_ref="ON-914", include=["spec"])
    assert set(result) == {"card_ref", "story_id", "spec"}


# ── get_effective_governance ────────────────────────────────────────────────

@pytest.mark.asyncio
@respx.mock
async def test_effective_governance_passes_agent_profile_and_returns_catalog():
    _mock_card_resolution()
    catalog = {
        "commands": [
            {"id": "spec.approve", "requires_human": True, "enabled": False,
             "reason": "human_only", "risk_level": "high"},
        ],
        "selected_agent_profile_id": 5,
        "policy_source": {"governance_profile": "default", "version": 3},
    }
    route = respx.get(
        Config.project_url(f"stories/{CARD_ID}/agent-commands/")
    ).mock(return_value=Response(200, json=catalog))
    result = await _tool(cockpit, "get_effective_governance")(
        card_ref="ON-914", agent_profile_id=5)

    assert route.calls.last.request.url.params["agent_profile_id"] == "5"
    assert result["policy_source"]["version"] == 3
    assert result["commands"][0]["id"] == "spec.approve"


# ── get_mcp_capabilities (network-free) ─────────────────────────────────────

@pytest.mark.asyncio
async def test_mcp_capabilities_lists_tools_and_config():
    result = await _tool(cockpit, "get_mcp_capabilities")()
    assert result["config"]["base_url"] == Config.base_url
    names = {t["name"] for t in result["tools"]}
    # The registry it enumerates is the FastMCP it was registered on (cockpit only).
    assert {"get_card_cockpit_context", "get_effective_governance",
            "get_mcp_capabilities"} <= names
    assert result["tool_count"] == len(result["tools"]) >= 3


# ── get_agent_identity hardening ────────────────────────────────────────────

@pytest.mark.asyncio
@respx.mock
async def test_agent_identity_agent_token():
    respx.get(Config.org_url("agents/whoami/")).mock(
        return_value=Response(200, json={
            "is_agent": True, "username": "codex-bot", "scopes": ["read", "write"]}))
    result = await _tool(agents, "get_agent_identity")()
    assert result["is_agent"] is True
    assert result["token_mode"] in ("agent", "run_scoped")
    assert result["organization"] == (Config.org or None)
    assert "run_context" in result and "writes_permitted" in result


@pytest.mark.asyncio
@respx.mock
async def test_agent_identity_human_token_whoami_404_is_graceful():
    respx.get(Config.org_url("agents/whoami/")).mock(
        return_value=Response(404, json={"detail": "not an agent"}))
    result = await _tool(agents, "get_agent_identity")()
    # A plain org/human token must not raise — it resolves to a human principal.
    assert result["is_agent"] is False
    assert result["token_mode"] == "org_or_human"
    assert result["current_run_id"] is None


# ── Slice 2: human-principal client mode + attribution ──────────────────────

@pytest.mark.asyncio
async def test_human_principal_suppresses_run_and_loop_headers(monkeypatch):
    monkeypatch.setattr(Config, "agent_run_id", "run-99")
    monkeypatch.setattr(Config, "loop_id", "loop-7")
    # Default client propagates the run/loop headers…
    async with SpryngClient() as default:
        assert default._http.headers.get("x-spryng-agent-run") == "run-99"
        assert default._http.headers.get("x-spryng-loop") == "loop-7"
    # …human-principal client drops them so assert_human_actor accepts the caller.
    async with SpryngClient(human_principal=True) as human:
        assert "x-spryng-agent-run" not in human._http.headers
        assert "x-spryng-loop" not in human._http.headers
        assert human.human_principal is True
        # Attribution rides on every request regardless of mode.
        assert human._http.headers.get("x-spryng-source") == "mcp"
        assert human._http.headers.get("x-spryng-client")


# ── send_cockpit_chat / draft_spec_from_card ────────────────────────────────

@pytest.mark.asyncio
@respx.mock
async def test_send_cockpit_chat_posts_message_as_human(monkeypatch):
    # Even with a run id in the env, the chat write must go out WITHOUT the run
    # header (proving it uses the human-principal client).
    monkeypatch.setattr(Config, "agent_run_id", "run-99")
    _mock_card_resolution()
    route = respx.post(
        Config.project_url(f"stories/{CARD_ID}/ai-cockpit/")
    ).mock(return_value=Response(201, json={"message": {"id": 5}, "chat_run_id": 77}))
    result = await _tool(cockpit, "send_cockpit_chat")(
        card_ref="ON-914", message="please review", agent_profile_id=3)

    body = json.loads(route.calls.last.request.content)
    assert body == {"action": "message", "body": "please review",
                    "agent_profile_id": 3}
    assert "x-spryng-agent-run" not in route.calls.last.request.headers
    assert route.calls.last.request.headers.get("x-spryng-source") == "mcp"
    assert result["chat_run_id"] == 77


@pytest.mark.asyncio
@respx.mock
async def test_draft_spec_from_card_posts_action_doc_type_and_fields():
    _mock_card_resolution()
    route = respx.post(
        Config.project_url(f"stories/{CARD_ID}/ai-cockpit/")
    ).mock(return_value=Response(201, json={
        "run": {"id": 9, "kind": "draft_spec"},
        "proposal": {"id": "p-1", "status": "generating"},
        "runner_readiness": {"ready": True}}))
    result = await _tool(cockpit, "draft_spec_from_card")(
        card_ref="ON-914", doc_type="design",
        instructions="cover the retry path", card_fields=["class_of_service"])

    body = json.loads(route.calls.last.request.content)
    assert body == {
        "action": "draft_spec_from_card", "doc_type": "design",
        "instructions": "cover the retry path",
        "card_fields": ["class_of_service"],
    }
    assert result["proposal"]["status"] == "generating"
