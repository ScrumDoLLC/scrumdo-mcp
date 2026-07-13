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
        """Return the connected principal's identity, token mode, and active run.

        Call this FIRST at session start. Works for BOTH an agent token and an
        ordinary org/human token: the ``agents/whoami/`` endpoint 404s when the
        caller is not an agent, which this tool treats as an org/human principal
        rather than an error.

        Added fields (AI_COCKPIT_BRIDGE_SPEC.md §5):
          - ``token_mode``: 'run_scoped' (SPRYNG_AGENT_RUN_ID set) | 'agent'
            (an agent token) | 'org_or_human' (a plain org/human token).
          - ``organization`` / ``project``: the configured default context.
          - ``run_context``: {agent_run_id, loop_id} currently propagated on writes.
          - ``writes_permitted``: whether a token is configured at all. NOTE: the
            human-only cockpit actions (chat, draft-from-card, execute-task, loop
            start/steer, proposal accept/reject) additionally require a
            NON-run-scoped token — a run-scoped token is treated as an agent and
            refused. Final authority is the server governance check
            (get_effective_governance).

        Use ``current_run_id`` (when non-null) in the ``X-Spryng-Agent-Run`` header
        on subsequent agent writes — the gateway enforces this for run-scoped
        sub-tokens (spec §13.2).
        """
        import httpx

        run_id = (Config.agent_run_id or '').strip()
        loop_id = (Config.loop_id or '').strip()
        async with SpryngClient() as c:
            try:
                data = await c.get(Config.org_url('agents/whoami/'))
                is_agent = True
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code == 404:
                    # Not an agent — an ordinary org/human API token.
                    data = {'is_agent': False}
                    is_agent = False
                else:
                    raise
            current_run_id = c.agent_run_id or None

        if not isinstance(data, dict):
            data = {'whoami': data}
        data.setdefault('is_agent', is_agent)
        data['current_run_id'] = current_run_id
        data['token_mode'] = (
            'run_scoped' if run_id else ('agent' if is_agent else 'org_or_human')
        )
        data['organization'] = Config.org or None
        data['project'] = Config.project or None
        data['run_context'] = {
            'agent_run_id': run_id or None,
            'loop_id': loop_id or None,
        }
        data['writes_permitted'] = bool(Config.token)
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
