"""Unit tests for spryng_mcp tools.

Uses respx to mock the ScrumDo HTTP API — no real network calls.
Run with: pytest mcp/tests/ -v
"""
from __future__ import annotations

import json
import os

import pytest
import respx
from httpx import Response

# Set a dummy token so Config.validate() doesn't raise during import
os.environ.setdefault("SCRUMDO_TOKEN", "test-token")
os.environ.setdefault("SCRUMDO_BASE_URL", "https://app.spryng.io")
os.environ.setdefault("SCRUMDO_ORG", "test-org")
os.environ.setdefault("SCRUMDO_PROJECT", "test-project")

from spryng_mcp.client import SpryngClient
from spryng_mcp.config import Config
from spryng_mcp.tools.activity import _parse_comment, _build_comment


# ── Fixtures ───────────────────────────────────────────────────────────────────

CARD_ID = 201582
CARD_NUMBER = 914  # the local_id / human-readable project sequence number

CARD_STUB = {
    "id": CARD_ID,
    "number": CARD_NUMBER,       # used by _resolve_card_id to match "ON-914"
    "local_id": "ON-914",
    "summary": "ScrumDo MCP Server",
    "points": 5,
    "cell": None,
    "assignees": [],
    "labels": [],
    "extra_fields": {"5303": "mcp-server", "5433": ""},
    "description": "",
}

# Paginated list response that _resolve_card_id will scan
LIST_PAGE_STUB = {
    "count": 1,
    "max_page": 1,
    "current_page": 1,
    "next": None,
    "previous": None,
    "items": [CARD_STUB],
}

TASK_STUB = {"id": 1, "description": "Wire up FastMCP", "complete": False, "assignee": None}

COMMENT_STUB = {"id": 99, "comment": "Hello world", "author": "rdy"}


def _mock_card_resolution() -> None:
    """Register the respx mock for _resolve_card_id's list-scan call."""
    respx.get(Config.project_url("stories/")).mock(
        return_value=Response(200, json=LIST_PAGE_STUB)
    )


# ── Client tests ───────────────────────────────────────────────────────────────

@respx.mock
@pytest.mark.asyncio
async def test_get_card_returns_card():
    _mock_card_resolution()
    respx.get(Config.project_url(f"stories/{CARD_ID}/")).mock(
        return_value=Response(200, json=CARD_STUB)
    )
    async with SpryngClient() as c:
        card = await c.get_card("ON-914")
    assert card["number"] == CARD_NUMBER
    assert card["summary"] == "ScrumDo MCP Server"


@respx.mock
@pytest.mark.asyncio
async def test_create_card_posts_body():
    respx.post(Config.project_url("stories/")).mock(
        return_value=Response(201, json={**CARD_STUB, "number": 915, "local_id": "ON-915"})
    )
    async with SpryngClient() as c:
        card = await c.create_card({"summary": "New card", "points": 3})
    assert card["number"] == 915


@respx.mock
@pytest.mark.asyncio
async def test_update_card_patches():
    _mock_card_resolution()
    respx.patch(Config.project_url(f"stories/{CARD_ID}/")).mock(
        return_value=Response(200, json={**CARD_STUB, "summary": "Updated"})
    )
    async with SpryngClient() as c:
        card = await c.update_card("ON-914", {"summary": "Updated"})
    assert card["summary"] == "Updated"


@respx.mock
@pytest.mark.asyncio
async def test_list_tasks():
    _mock_card_resolution()
    respx.get(Config.project_url(f"stories/{CARD_ID}/tasks/")).mock(
        return_value=Response(200, json=[TASK_STUB])
    )
    async with SpryngClient() as c:
        tasks = await c.list_tasks("ON-914")
    assert len(tasks) == 1
    assert tasks[0]["description"] == "Wire up FastMCP"


@respx.mock
@pytest.mark.asyncio
async def test_add_comment():
    respx.post(Config.api("comments/story/")).mock(
        return_value=Response(201, json={"id": 100, "comment": "Hello", "author": "bot"})
    )
    async with SpryngClient() as c:
        result = await c.add_comment(CARD_ID, "Hello")
    assert result["id"] == 100


@respx.mock
@pytest.mark.asyncio
async def test_set_custom_field_preserves_existing():
    """set_custom_field should merge new value into existing extra_fields."""
    existing = {**CARD_STUB, "extra_fields": {"5303": "existing-value", "5433": "old-pr"}}
    _mock_card_resolution()
    respx.get(Config.project_url(f"stories/{CARD_ID}/")).mock(
        return_value=Response(200, json=existing)
    )
    patch_req = respx.patch(Config.project_url(f"stories/{CARD_ID}/")).mock(
        return_value=Response(200, json=existing)
    )
    async with SpryngClient() as c:
        await c.set_custom_field("ON-914", 5433, "new-pr-url")
    sent = json.loads(patch_req.calls[0].request.content)
    assert sent["extra_fields"]["5303"] == "existing-value"  # preserved
    assert sent["extra_fields"]["5433"] == "new-pr-url"       # updated


@respx.mock
@pytest.mark.asyncio
async def test_resolve_card_id_caches():
    """Second call for the same ref must not issue another list request."""
    _mock_card_resolution()
    respx.get(Config.project_url(f"stories/{CARD_ID}/")).mock(
        return_value=Response(200, json=CARD_STUB)
    )
    async with SpryngClient() as c:
        id1 = await c._resolve_card_id("ON-914")
        id2 = await c._resolve_card_id("ON-914")  # should hit cache
    assert id1 == id2 == CARD_ID
    # list endpoint should have been called exactly once (cache hit on 2nd call)
    list_calls = [
        call for call in respx.calls
        if "stories/" in str(call.request.url) and "page" in str(call.request.url.params)
    ]
    assert len(list_calls) == 1, f"Expected 1 list call, got {len(list_calls)}"


# ── Activity log tests ─────────────────────────────────────────────────────────

def test_build_and_parse_roundtrip():
    entry = {
        "timestamp": "2026-04-04T12:00:00+00:00",
        "card_ref": "ON-914",
        "action": "deployed",
        "detail": "Deployed to stage",
        "agent": "claude-code",
        "user": "rdy",
        "environment": "stage",
        "milestone": "v1.0",
        "task_ref": "",
    }
    comment_body = _build_comment(entry)
    # Should be human-readable
    assert "deployed" in comment_body
    assert "claude-code" in comment_body
    assert "stage" in comment_body

    # Should round-trip through parse
    parsed = _parse_comment({"comment": comment_body, "id": 1, "author": "bot"})
    assert parsed is not None
    assert parsed["action"] == "deployed"
    assert parsed["agent"] == "claude-code"
    assert parsed["environment"] == "stage"
    assert parsed["milestone"] == "v1.0"
    assert parsed["_comment_id"] == 1


def test_parse_plain_comment_returns_none():
    plain = {"comment": "Just a regular comment with no activity data.", "id": 2}
    assert _parse_comment(plain) is None


def test_parse_malformed_json_returns_none():
    from spryng_mcp.tools.activity import _PREFIX
    bad = {"comment": f"text\n{_PREFIX}\nnot-valid-json", "id": 3}
    assert _parse_comment(bad) is None


@respx.mock
@pytest.mark.asyncio
async def test_get_activity_log_filters_by_agent():
    from spryng_mcp.tools.activity import _build_comment, _PREFIX

    entry_a = {
        "timestamp": "2026-04-04T10:00:00+00:00", "card_ref": "ON-914",
        "action": "start", "detail": "", "agent": "claude-code",
        "user": "", "environment": "stage", "milestone": "", "task_ref": "",
    }
    entry_b = {
        "timestamp": "2026-04-04T11:00:00+00:00", "card_ref": "ON-914",
        "action": "review", "detail": "", "agent": "codex",
        "user": "", "environment": "stage", "milestone": "", "task_ref": "",
    }

    comments = [
        {"id": 1, "comment": _build_comment(entry_a), "author": "claude-code"},
        {"id": 2, "comment": _build_comment(entry_b), "author": "codex"},
        {"id": 3, "comment": "plain comment — should be ignored", "author": "rdy"},
    ]

    _mock_card_resolution()
    respx.get(Config.project_url(f"stories/{CARD_ID}/")).mock(
        return_value=Response(200, json=CARD_STUB)
    )
    respx.get(Config.api("comments/story/")).mock(
        return_value=Response(200, json=comments)
    )

    from spryng_mcp.tools.activity import register
    from mcp.server.fastmcp import FastMCP
    test_mcp = FastMCP("test")
    register(test_mcp)

    # Call the tool function directly via the registered tool
    tool_fn = next(t for t in test_mcp._tool_manager._tools.values() if t.name == "get_activity_log")
    result = await tool_fn.fn(card_ref="ON-914", agent="claude-code")

    assert len(result) == 1
    assert result[0]["agent"] == "claude-code"
    assert result[0]["action"] == "start"
