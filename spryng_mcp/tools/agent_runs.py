"""Phase E (BOARD_AI_AGENTS_UNIFIED_SPEC §E.7) — AgentRun MCP tools.

Six tools wrapping the dispatcher's REST surface.
"""
from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from ..client import SpryngClient
from ..config import Config


def register(mcp: FastMCP) -> None:

    @mcp.tool()
    async def start_agent_run(
        card_ref: str,
        agent_id: int | None = None,
    ) -> dict:
        """Open a new AgentRun on a card in `queued` state.

        Returns 409 with `already_active_run_id` if a run is in-flight.

        Args:
            card_ref: 'ON-914'-style reference.
            agent_id: User id of the agent identity to run. Defaults to
                      the (single) active agent currently assigned to
                      the card.
        """
        body: dict = {'card_ref': card_ref}
        if agent_id is not None:
            body['agent_id'] = agent_id
        async with SpryngClient() as c:
            return await c.post(Config.org_url('agent-runs/'), body)

    @mcp.tool()
    async def cancel_agent_run(run_id: int, reason: str = '') -> dict:
        """Cancel an in-flight run.

        Spec §E.9 #4: the dispatcher flips state to `cancelled`
        immediately; the runtime acknowledges on its next progress
        report.
        """
        async with SpryngClient() as c:
            return await c.post(
                Config.org_url(f'agent-runs/{run_id}/cancel/'),
                {'reason': reason},
            )

    @mcp.tool()
    async def approve_agent_plan(run_id: int) -> dict:
        """Approve a run's plan; transitions awaiting_approval → executing.

        Agents cannot approve their own plans (spec §F.2); the backend
        enforces this with 403.
        """
        async with SpryngClient() as c:
            return await c.post(
                Config.org_url(f'agent-runs/{run_id}/approve/'), {},
            )

    @mcp.tool()
    async def get_agent_run(run_id: int) -> dict:
        """Fetch one AgentRun row by id."""
        async with SpryngClient() as c:
            return await c.get(Config.org_url(f'agent-runs/{run_id}/'))

    @mcp.tool()
    async def list_agent_runs(
        card_id: int | None = None,
        agent_id: int | None = None,
        state: str | None = None,
    ) -> list[dict]:
        """List AgentRuns scoped to the current org.

        Args:
            card_id: filter to one card.
            agent_id: filter to one agent.
            state: filter to one state (queued|planning|awaiting_approval|
                   executing|completed|failed|cancelled).
        """
        params: dict = {}
        if card_id is not None:
            params['card_id'] = card_id
        if agent_id is not None:
            params['agent_id'] = agent_id
        if state:
            params['state'] = state
        async with SpryngClient() as c:
            return await c.get(Config.org_url('agent-runs/'), **params)

    @mcp.tool()
    async def report_agent_progress(
        run_id: int,
        state: str,
        plan: str = '',
        evidence: dict | None = None,
        outcome: str = '',
        error: str = '',
        cost_cents_delta: int = 0,
        primary_pr_link_id: int | None = None,
    ) -> dict:
        """Drive the AgentRun state machine forward.

        This is the ONLY way the agent runtime moves state (spec §E.7).
        Body shape is state-dependent:
        - planning      : expects `plan`.
        - executing     : accepts `evidence` updates.
        - completed     : expects `outcome` + `primary_pr_link_id`.

        Args:
            run_id: AgentRun id.
            state: target state.
            plan: markdown plan body (set on planning → awaiting_approval).
            evidence: dict merged into AgentRun.evidence.
            outcome: free-text outcome string (set on completed).
            error: error string (set on failed).
            cost_cents_delta: accumulate cost.
            primary_pr_link_id: StoryGitHubLink id when the agent opens a PR.
        """
        body: dict = {'state': state}
        if plan:
            body['plan'] = plan
        if evidence is not None:
            body['evidence'] = evidence
        if outcome:
            body['outcome'] = outcome
        if error:
            body['error'] = error
        if cost_cents_delta:
            body['cost_cents_delta'] = cost_cents_delta
        if primary_pr_link_id is not None:
            body['primary_pr_link_id'] = primary_pr_link_id

        async with SpryngClient() as c:
            return await c.post(
                Config.org_url(f'agent-runs/{run_id}/progress/'), body,
            )
