"""Phase A (BOARD_AI_AGENTS_UNIFIED_SPEC §A.5) — agent identity tools.

Adds two MCP tools:

- ``get_agent_identity`` (mandatory at session start per spec §13.4 #1):
  returns the connected agent's own identity, scopes, and the active
  AgentRun id when a run is in flight.

- ``list_agent_accounts``: enumerate registered agents on the org so a
  human (or another agent) can discover available identities.
"""
from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from ..client import SpryngClient
from ..config import Config


def register(mcp: FastMCP) -> None:

    @mcp.tool()
    async def get_agent_identity() -> dict:
        """Return the connected agent's identity + active run, if any.

        Call this FIRST at session start. Use the returned
        ``current_run_id`` (when non-null) in the ``X-Spryng-Agent-Run``
        header on every subsequent write — the gateway enforces this for
        run-scoped sub-tokens (spec §13.2).
        """
        async with SpryngClient() as c:
            data = await c.get(Config.org_url('agents/whoami/'))
        # Surface the locally-known active AgentRun id so the caller
        # doesn't have to thread it through env separately.
        data['current_run_id'] = c.agent_run_id or None
        return data

    @mcp.tool()
    async def list_agent_accounts(active_only: bool = True) -> list[dict]:
        """List agent identities registered on the current organisation.

        Args:
            active_only: When True (default), filter to is_active agents.
        """
        async with SpryngClient() as c:
            agents = await c.get(Config.org_url('agents/'))
        if isinstance(agents, dict):
            agents = agents.get('agents', [])
        if active_only:
            agents = [a for a in agents if a.get('is_active', True)]
        return agents
