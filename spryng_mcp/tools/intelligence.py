"""Phase G (BOARD_AI_AGENTS_UNIFIED_SPEC §10) — AI intelligence tools.

Four MCP tools:
- check_spec_drift: trigger / fetch the drift report for a card's latest PR.
- verify_behavior_contract: trigger / fetch the verification report.
- get_spec_complexity: read the deterministic complexity score (G.4).
- get_velocity_forecast: combine complexity + iteration history.
"""
from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from ..client import SpryngClient
from ..config import Config


def register(mcp: FastMCP) -> None:

    @mcp.tool()
    async def check_spec_drift(card_ref: str) -> dict:
        """Run the drift check on the card's latest PR + return the report.

        Per spec §G.1 + D5 this normally runs automatically at AgentRun
        completion. This tool exists for explicit re-runs (e.g. after
        the spec is edited mid-flight).
        """
        async with SpryngClient() as c:
            story_id = await c._resolve_card_id(card_ref)
            return await c.post(
                Config.project_url(f'stories/{story_id}/ai/drift/'), {},
            )

    @mcp.tool()
    async def verify_behavior_contract(card_ref: str) -> dict:
        """Run the behavior-verification check + return the report.

        Per spec §G.2 + D5: the run's "tests passed" claim flows
        through here, never from the agent's self-reported evidence.
        """
        async with SpryngClient() as c:
            story_id = await c._resolve_card_id(card_ref)
            return await c.post(
                Config.project_url(f'stories/{story_id}/ai/verify/'), {},
            )

    @mcp.tool()
    async def get_spec_complexity(card_ref: str) -> dict:
        """Return the deterministic (no-LLM) complexity score + breakdown.

        Spec §G.4: recomputed on every spec save; cheap to read.
        """
        async with SpryngClient() as c:
            story_id = await c._resolve_card_id(card_ref)
            data = await c.get(
                Config.project_url(f'stories/{story_id}/spec/'),
            )
        return {
            'complexity_score': data.get('complexity_score', 0),
            'complexity_breakdown': data.get('complexity_breakdown', {}),
        }

    @mcp.tool()
    async def get_velocity_forecast(card_ref: str) -> dict:
        """Predicted cycle-time band for a card at its current complexity.

        Backed by the iteration history of the project (spec §G.4).
        Returns `{low_days, high_days, r2, baseline}`.
        """
        async with SpryngClient() as c:
            story_id = await c._resolve_card_id(card_ref)
            return await c.get(
                Config.project_url(f'stories/{story_id}/ai/forecast/'),
            )
