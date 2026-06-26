"""Loop / verification MCP tool tests.

Covers the "Better MCP Support for Agents" §1 surface: run_verifier, the
enriched start_verification_loop, log_loop_step's result + the SPRYNG_LOOP_ID
env default. Uses respx to mock the ScrumDo HTTP API — no real network calls.
"""
from __future__ import annotations

import json

import pytest
import respx
from httpx import Response
from mcp.server.fastmcp import FastMCP

from spryng_mcp.config import Config
from spryng_mcp.tools import loops


def _tool(name: str):
    """Register the loop tools on a throwaway server and return the tool fn."""
    m = FastMCP("test")
    loops.register(m)
    return next(t for t in m._tool_manager._tools.values()
                if t.name == name).fn


# ── pure helpers ─────────────────────────────────────────────────────────────

def test_verifier_req_mapping():
    assert loops._verifier_req("different") == "different_agent"
    assert loops._verifier_req("same") == "same_agent"
    assert loops._verifier_req("human") == "human_only"
    assert loops._verifier_req("claude") == "different_agent"  # named ⇒ different
    assert loops._verifier_req("different_agent") == "different_agent"  # passthrough


def test_resolve_loop_id_uses_env(monkeypatch):
    monkeypatch.setattr(Config, "loop_id", "77", raising=False)
    assert loops._resolve_loop_id(None) == 77      # falls back to SPRYNG_LOOP_ID
    assert loops._resolve_loop_id(5) == 5          # explicit wins
    monkeypatch.setattr(Config, "loop_id", "", raising=False)
    with pytest.raises(ValueError):
        loops._resolve_loop_id(None)               # neither → clear error


# ── HTTP-backed tools ────────────────────────────────────────────────────────

@pytest.mark.asyncio
@respx.mock
async def test_run_verifier_posts_to_verify_spec():
    route = respx.post(Config.org_url("agent-runs/verify-spec/")).mock(
        return_value=Response(200, json={"id": 1}))
    await _tool("run_verifier")(
        card_ref="ON-914", maker_changes="edited foo.py (+10/-2)",
        verifier_prompt="be adversarial")
    body = json.loads(route.calls.last.request.content)
    assert body == {"card_ref": "ON-914",
                    "maker_changes": "edited foo.py (+10/-2)",
                    "verifier_prompt": "be adversarial"}


@pytest.mark.asyncio
@respx.mock
async def test_start_verification_loop_inline_config():
    route = respx.post(Config.org_url("agent-loops/")).mock(
        return_value=Response(200, json={"id": 1}))
    await _tool("start_verification_loop")(
        card_ref="ON-914", max_turns=8, verifier_agent="different",
        proof_requirements=["tests", "spec_match"])
    body = json.loads(route.calls.last.request.content)
    assert body["max_iterations"] == 8
    assert body["verifier_requirement"] == "different_agent"
    assert body["proof_requirements"] == ["tests", "spec_match"]


@pytest.mark.asyncio
@respx.mock
async def test_log_loop_step_result_and_env_default(monkeypatch):
    monkeypatch.setattr(Config, "loop_id", "42", raising=False)
    route = respx.post(Config.org_url("agent-loops/42/steps/")).mock(
        return_value=Response(200, json={"ok": True}))
    # No loop_id passed — resolves from SPRYNG_LOOP_ID (the in-loop case the
    # seeded maker prompts rely on).
    await _tool("log_loop_step")(
        action="make_change", detail="did it", result="PASS")
    body = json.loads(route.calls.last.request.content)
    assert body["action"] == "make_change"
    assert body["result"] == "PASS"
    assert route.called


@pytest.mark.asyncio
@respx.mock
async def test_attach_evidence_env_default(monkeypatch):
    monkeypatch.setattr(Config, "loop_id", "42", raising=False)
    route = respx.post(Config.org_url("agent-loops/42/evidence/")).mock(
        return_value=Response(200, json={"accumulated_evidence": []}))
    await _tool("attach_evidence")(artifacts={"tests": "green"})
    assert route.called
    body = json.loads(route.calls.last.request.content)
    assert body == {"artifacts": {"tests": "green"}}
