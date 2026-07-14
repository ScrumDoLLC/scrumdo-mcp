"""Unit tests for the shared-cognition (memory) + notification client paths.

Uses respx to mock the ScrumDo HTTP API — no real network calls.
"""
from __future__ import annotations

import os

import pytest
import respx
from httpx import Response

os.environ.setdefault("SCRUMDO_TOKEN", "test-token")
os.environ.setdefault("SCRUMDO_BASE_URL", "https://app.spryng.io")
os.environ.setdefault("SCRUMDO_ORG", "test-org")
os.environ.setdefault("SCRUMDO_PROJECT", "test-project")

from spryng_mcp.client import SpryngClient  # noqa: E402
from spryng_mcp.config import Config  # noqa: E402


@pytest.fixture(autouse=True)
def _pin_config():
    """Config is a mutable class attribute bag shared across the test run —
    other test modules repoint org/project/run-id. Pin what these URL
    assertions depend on and restore after."""
    saved = (Config.base_url, Config.org, Config.project, Config.agent_run_id,
             Config.loop_id)
    Config.base_url = "https://app.spryng.io"
    Config.org = "test-org"
    Config.project = "test-project"
    Config.agent_run_id = ""
    Config.loop_id = ""
    yield
    (Config.base_url, Config.org, Config.project, Config.agent_run_id,
     Config.loop_id) = saved


BASE = "https://app.spryng.io/api/scrumdo"
PROJ = f"{BASE}/organizations/test-org/projects/test-project"
ORG = f"{BASE}/organizations/test-org"

CARD_ID = 201582
LIST_PAGE = {
    "count": 1, "max_page": 1, "current_page": 1, "next": None,
    "previous": None,
    "items": [{"id": CARD_ID, "number": 914, "summary": "card"}],
}


def _mock_card_resolution(router: respx.MockRouter) -> None:
    router.get(f"{PROJ}/stories/").respond(200, json=LIST_PAGE)


# ── Blackboard + handoff ──────────────────────────────────────────────────────

@pytest.mark.asyncio
@respx.mock
async def test_post_blackboard_note_hits_card_blackboard():
    _mock_card_resolution(respx.mock)
    route = respx.post(f"{PROJ}/stories/{CARD_ID}/blackboard/").respond(
        201, json={"id": 7, "kind": "gotcha", "body": "suite flaky"})
    async with SpryngClient() as c:
        out = await c.post_blackboard_note(
            "ON-914", {"body": "suite flaky", "kind": "gotcha"})
    assert out["id"] == 7
    import json as _json
    sent = _json.loads(route.calls.last.request.content)
    assert sent == {"body": "suite flaky", "kind": "gotcha"}


@pytest.mark.asyncio
@respx.mock
async def test_read_blackboard_and_handoff_brief():
    _mock_card_resolution(respx.mock)
    respx.get(f"{PROJ}/stories/{CARD_ID}/blackboard/").respond(
        200, json=[{"id": 7, "is_live": True}])
    respx.get(f"{PROJ}/stories/{CARD_ID}/handoff-brief/").respond(
        200, json={"event_count": 3, "constraints_added": []})
    async with SpryngClient() as c:
        notes = await c.read_blackboard("ON-914")
        brief = await c.get_handoff_brief("ON-914")
    assert notes[0]["id"] == 7
    assert brief["event_count"] == 3


@pytest.mark.asyncio
@respx.mock
async def test_promote_action_url_and_scope_body():
    _mock_card_resolution(respx.mock)
    route = respx.post(
        f"{PROJ}/stories/{CARD_ID}/blackboard/7/promote/").respond(
        201, json={"entry": {"id": 7}, "claim": {"id": 91}})
    async with SpryngClient() as c:
        out = await c.blackboard_action("ON-914", 7, "promote",
                                        {"scope": "card"})
    assert out["claim"]["id"] == 91
    assert b'"scope":"card"' in route.calls.last.request.content


# ── Saved context (card + room) ───────────────────────────────────────────────

@pytest.mark.asyncio
@respx.mock
async def test_room_context_roundtrip_and_curation():
    respx.get(f"{PROJ}/memory/").respond(200, json=[{"id": 1}])
    add = respx.post(f"{PROJ}/memory/").respond(201, json={"id": 2})
    approve = respx.post(f"{PROJ}/memory/2/approve/").respond(
        200, json={"id": 2, "is_approved": True})
    distill = respx.post(f"{PROJ}/memory/distill/").respond(
        200, json={"reports": []})
    async with SpryngClient() as c:
        assert (await c.get_room_context())[0]["id"] == 1
        assert (await c.add_room_context({"title": "t", "body": "b",
                                          "kind": "convention",
                                          "scope": "room"}))["id"] == 2
        assert (await c.room_context_action(2, "approve"))["is_approved"]
        assert (await c.run_distiller())["reports"] == []
    assert add.called and approve.called and distill.called


@pytest.mark.asyncio
@respx.mock
async def test_dispute_resolve_body_shapes():
    respx.get(f"{PROJ}/disputes/").respond(200, json=[{"id": 5,
                                                       "status": "open"}])
    route = respx.post(f"{PROJ}/disputes/5/resolve/").respond(
        200, json={"id": 5, "status": "resolved"})
    async with SpryngClient() as c:
        assert (await c.list_memory_disputes())[0]["id"] == 5
        await c.resolve_memory_dispute(5, winner_id=11)   # pick a winner
        await c.resolve_memory_dispute(5)                 # dismiss
    first, second = route.calls[0].request, route.calls[1].request
    assert b'"winner_id":11' in first.content
    assert second.content in (b"{}", b"")


# ── Notifications ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
@respx.mock
async def test_notifications_list_params_and_actions():
    lst = respx.get(f"{ORG}/notifications/messages/").respond(
        200, json={"results": [{"id": 3}], "count": 1})
    respx.get(f"{ORG}/notifications/messages/counts/").respond(
        200, json={"unread": 1})
    ack = respx.post(f"{ORG}/notifications/messages/3/acknowledge/").respond(
        200, json={"id": 3, "status": "acknowledged"})
    mar = respx.post(f"{ORG}/notifications/messages/mark-all-read/").respond(
        200, json={"updated": 1})
    async with SpryngClient() as c:
        out = await c.list_notifications(status="unread", limit=10)
        counts = await c.notification_counts()
        await c.notification_action(3, "acknowledge")
        await c.mark_all_notifications_read()
    assert out["count"] == 1 and counts["unread"] == 1
    assert ack.called and mar.called
    q = dict(lst.calls.last.request.url.params)
    assert q["status"] == "unread" and q["limit"] == "10"


# ── Wait channel + number fast-path resolution ────────────────────────────────

@pytest.mark.asyncio
@respx.mock
async def test_wait_for_notifications_params_and_cursor():
    route = respx.get(f"{ORG}/notifications/messages/wait/").respond(
        200, json={"results": [{"id": 9}], "count": 1, "cursor": 9})
    async with SpryngClient() as c:
        out = await c.wait_for_notifications(after=4, timeout_s=7)
    assert out["cursor"] == 9
    q = dict(route.calls.last.request.url.params)
    assert q["after"] == "4" and q["timeout"] == "7"


@pytest.mark.asyncio
@respx.mock
async def test_resolve_number_fast_path_single_request():
    route = respx.get(f"{PROJ}/stories/").respond(200, json={
        "count": 1, "next": None, "items": [{"id": CARD_ID, "number": 914}]})
    async with SpryngClient() as c:
        assert await c._resolve_card_id("ON-914") == CARD_ID
    assert len(route.calls) == 1
    assert dict(route.calls.last.request.url.params)["number"] == "914"


@pytest.mark.asyncio
@respx.mock
async def test_resolve_falls_back_when_number_param_ignored():
    # Old backend: the number param is ignored; page 1 lacks the card, page 2
    # has it. Call 1 = fast path (miss), calls 2-3 = the pagination walk.
    pages = [
        {"count": 2, "next": "p2", "items": [{"id": 1, "number": 1}]},
        {"count": 2, "next": "p2", "items": [{"id": 1, "number": 1}]},
        {"count": 2, "next": None, "items": [{"id": CARD_ID, "number": 914}]},
    ]
    route = respx.get(f"{PROJ}/stories/")
    route.side_effect = [Response(200, json=p) for p in pages]
    async with SpryngClient() as c:
        assert await c._resolve_card_id("ON-914") == CARD_ID
    assert len(route.calls) == 3
