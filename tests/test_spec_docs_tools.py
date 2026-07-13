"""Multi-document spec tools (Card AI Cockpit v2 Phase 1).

list_card_spec_documents / set_card_spec_document / restore_spec_version.
respx-mocked, no network.
"""
from __future__ import annotations

import json

import pytest
import respx
from httpx import Response
from mcp.server.fastmcp import FastMCP

from spryng_mcp.config import Config
from spryng_mcp.tools import spec

CARD_ID = 201582
CARD_STUB = {"id": CARD_ID, "number": 914, "local_id": "ON-914"}
LIST_PAGE_STUB = {"items": [CARD_STUB], "next": None}


def _mock_card_resolution() -> None:
    respx.get(Config.project_url("stories/")).mock(
        return_value=Response(200, json=LIST_PAGE_STUB))


def _tool(name: str):
    m = FastMCP("test")
    spec.register(m)
    return next(t for t in m._tool_manager._tools.values() if t.name == name).fn


@pytest.mark.asyncio
@respx.mock
async def test_list_card_spec_documents():
    _mock_card_resolution()
    respx.get(Config.project_url(f"stories/{CARD_ID}/spec/docs/")).mock(
        return_value=Response(200, json={"docs": [
            {"doc_type": "requirements", "has_content": True},
            {"doc_type": "design", "has_content": False}]}))
    result = await _tool("list_card_spec_documents")(card_ref="ON-914")
    assert [d["doc_type"] for d in result["docs"]] == ["requirements", "design"]


@pytest.mark.asyncio
@respx.mock
async def test_set_card_spec_document_posts_doc_type_and_is_run_attributed(monkeypatch):
    # Doc write is the agent-writable path (like set_card_spec): an assigned
    # agent's run header rides on it so the write is run-attributed.
    monkeypatch.setattr(Config, "agent_run_id", "run-99")
    _mock_card_resolution()
    route = respx.post(Config.project_url(f"stories/{CARD_ID}/spec/docs/")).mock(
        return_value=Response(200, json={"doc_type": "design", "version": 4}))
    result = await _tool("set_card_spec_document")(
        card_ref="ON-914", doc_type="design", content="# Design", fmt="md")

    assert json.loads(route.calls.last.request.content) == {
        "doc_type": "design", "content": "# Design", "format": "md"}
    assert route.calls.last.request.headers.get("x-spryng-agent-run") == "run-99"
    assert result["version"] == 4


@pytest.mark.asyncio
@respx.mock
async def test_restore_spec_version_posts_doc_type_and_number_as_human(monkeypatch):
    monkeypatch.setattr(Config, "agent_run_id", "run-99")
    _mock_card_resolution()
    route = respx.post(
        Config.project_url(f"stories/{CARD_ID}/spec/versions/restore/")
    ).mock(return_value=Response(200, json={"version_number": 7, "restored": True}))
    result = await _tool("restore_spec_version")(
        card_ref="ON-914", version_number=3, doc_type="requirements")

    assert json.loads(route.calls.last.request.content) == {
        "doc_type": "requirements", "version_number": 3}
    assert "x-spryng-agent-run" not in route.calls.last.request.headers
    assert result["restored"] is True
