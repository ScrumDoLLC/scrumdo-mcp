"""Phase 0 (BOARD_AI_AGENTS_UNIFIED_SPEC §3a.4) — verify the
`X-Spryng-Agent-Run` header rides on outbound writes when set."""
from __future__ import annotations

import respx
from httpx import Response

from spryng_mcp.client import SpryngClient
from spryng_mcp.config import Config


@respx.mock
async def test_header_present_when_run_id_set(monkeypatch):
    monkeypatch.setattr(Config, "agent_run_id", "")

    captured: list[dict] = []

    def _record(request):
        captured.append(dict(request.headers))
        return Response(200, json={"ok": True})

    # Mock the URL the client actually resolves from Config (org/project
    # come from the env/.env), not a hardcoded test-org/test-project.
    respx.get(Config.project_url("stories/")).mock(side_effect=_record)

    async with SpryngClient(agent_run_id="run-42") as c:
        await c.list_cards(page=1, limit=10)

    assert any(
        h.get("x-spryng-agent-run") == "run-42" for h in captured
    ), "X-Spryng-Agent-Run header missing from outbound request"


@respx.mock
async def test_header_absent_when_no_run_id(monkeypatch):
    monkeypatch.setattr(Config, "agent_run_id", "")

    captured: list[dict] = []

    def _record(request):
        captured.append(dict(request.headers))
        return Response(200, json={"ok": True})

    # Mock the URL the client actually resolves from Config (org/project
    # come from the env/.env), not a hardcoded test-org/test-project.
    respx.get(Config.project_url("stories/")).mock(side_effect=_record)

    async with SpryngClient() as c:
        await c.list_cards(page=1, limit=10)

    assert not any(
        "x-spryng-agent-run" in h for h in captured
    ), "X-Spryng-Agent-Run header should not be present without a run id"


@respx.mock
async def test_header_from_env_var(monkeypatch):
    monkeypatch.setattr(Config, "agent_run_id", "env-run-99")

    captured: list[dict] = []

    def _record(request):
        captured.append(dict(request.headers))
        return Response(200, json={"ok": True})

    # Mock the URL the client actually resolves from Config (org/project
    # come from the env/.env), not a hardcoded test-org/test-project.
    respx.get(Config.project_url("stories/")).mock(side_effect=_record)

    async with SpryngClient() as c:
        await c.list_cards(page=1, limit=10)

    assert any(
        h.get("x-spryng-agent-run") == "env-run-99" for h in captured
    )
