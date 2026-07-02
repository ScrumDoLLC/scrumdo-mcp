"""Spec proposal lifecycle — MCP tools (BOARD_AI_AGENTS_UNIFIED_SPEC §5.6 +
Phase B card spec tools in spec.py).

`spec.py` reads/writes the ACCEPTED spec directly — the legitimate "human
edits the spec themselves" path. This module is the complementary path: ask
an agent to draft a proposal, then review it through accept / reject /
request-changes / revise, without ever writing StorySpec directly. Proposals
are inert until a human accepts one (never an agent — every write handler
here rejects an agent-flagged caller with 403, mirrored client-side by
raising early with a clear message rather than letting the API 403).

There is no separate "revise" endpoint distinct from reject — the backend's
`/reject/` handler takes an outcome-determining `request_changes` flag: unset
rejects the proposal outright, set marks it `revision_requested` instead.
`revise_spec_proposal` is a third, separate step: it dispatches the actual
re-draft (only valid after request_spec_proposal_changes), mirroring
`generate_spec_proposal`'s async/202 contract.
"""
from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from ..client import SpryngClient
from ..config import Config


def register(mcp: FastMCP) -> None:

    @mcp.tool()
    async def generate_spec_proposal(
        card_ref: str,
        agent_id: int | None = None,
        instructions: str = "",
        repo_full_name: str = "",
        card_fields: list[str] | None = None,
    ) -> dict:
        """Ask an agent to draft a new spec proposal for a card.

        Only a human principal may call this — an agent run-token is
        rejected (agents draft when dispatched, they don't self-trigger
        drafting). The draft itself happens asynchronously: this returns
        202-shaped acceptance (`proposal_id`, `agent_run_id`), not the drafted
        content. Poll list_spec_proposals(card_ref) or get_agent_run(run_id)
        (agent_runs.py) until the proposal leaves `generating` state, then
        review it with accept_spec_proposal / reject_spec_proposal /
        request_spec_proposal_changes.

        A card caps at 5 concurrently-active proposals — accept, reject, or
        wait for one to finish generating before drafting another.

        Args:
            card_ref: 'ON-914'-style card reference.
            agent_id: Which agent identity drafts. Defaults to the card's
                (single) active assigned agent.
            instructions: Free-text guidance for this draft (kept on the
                run's evidence, capped ~4000 chars).
            repo_full_name: 'owner/name' — which connected repo to ground the
                draft in, when the board has several.
            card_fields: Specific card field names to spotlight in the
                agent's context, when you don't want the full card.
        """
        body: dict = {}
        if agent_id is not None:
            body["agent_id"] = agent_id
        if instructions:
            body["instructions"] = instructions
        if repo_full_name:
            body["repo_full_name"] = repo_full_name
        if card_fields:
            body["selection"] = {"card_fields": list(card_fields)}
        async with SpryngClient() as c:
            story_id = await c._resolve_card_id(card_ref)
            return await c.post(
                Config.project_url(
                    f"stories/{story_id}/spec-proposals/generate/"),
                body,
            )

    @mcp.tool()
    async def list_spec_proposals(card_ref: str) -> list[dict]:
        """List a card's active + recent spec proposals (newest first, capped
        at 50), each with its status (generating|pending_review|accepted|
        rejected|revision_requested), agent, and context provenance."""
        async with SpryngClient() as c:
            story_id = await c._resolve_card_id(card_ref)
            return await c.get(
                Config.project_url(f"stories/{story_id}/spec-proposals/"))

    @mcp.tool()
    async def accept_spec_proposal(card_ref: str, proposal_id: str) -> dict:
        """Accept a pending proposal into the human-owned card spec.

        Only a human principal may call this — an agent run-token is
        rejected. This is the ONLY path that writes agent-drafted content
        into the accepted spec; it is also the trigger — if the card's room
        has a runnable execution profile, accepting can dispatch an
        execution run against the newly-accepted spec.

        Args:
            card_ref: 'ON-914'-style card reference.
            proposal_id: The proposal's public_id (UUID), from
                generate_spec_proposal or list_spec_proposals.
        """
        async with SpryngClient() as c:
            story_id = await c._resolve_card_id(card_ref)
            return await c.post(
                Config.project_url(
                    f"stories/{story_id}/spec-proposals/"
                    f"{proposal_id}/accept/"),
                {},
            )

    @mcp.tool()
    async def reject_spec_proposal(
        card_ref: str,
        proposal_id: str,
        reason: str = "",
        reason_code: str = "",
    ) -> dict:
        """Reject a proposal outright — the card spec is left unchanged.

        Only a human principal may call this. For "close but needs changes"
        instead of an outright reject, use request_spec_proposal_changes.

        Args:
            card_ref: 'ON-914'-style card reference.
            proposal_id: The proposal's public_id (UUID).
            reason: Free-text reason (kept as-is on the rejection record).
            reason_code: Optional taxonomy code for evaluation reporting.
        """
        body: dict = {"reason": reason}
        if reason_code:
            body["reason_code"] = reason_code
        async with SpryngClient() as c:
            story_id = await c._resolve_card_id(card_ref)
            return await c.post(
                Config.project_url(
                    f"stories/{story_id}/spec-proposals/"
                    f"{proposal_id}/reject/"),
                body,
            )

    @mcp.tool()
    async def request_spec_proposal_changes(
        card_ref: str,
        proposal_id: str,
        reason: str,
        reason_code: str = "",
    ) -> dict:
        """Mark a pending proposal `revision_requested` (not rejected) — the
        card spec is left unchanged. Follow up with revise_spec_proposal to
        actually dispatch the re-draft once you're ready.

        Only a human principal may call this.

        Args:
            card_ref: 'ON-914'-style card reference.
            proposal_id: The proposal's public_id (UUID).
            reason: What needs to change — stored as a redacted summary, and
                handed to the agent verbatim when revise_spec_proposal runs.
            reason_code: Optional taxonomy code for evaluation reporting.
        """
        body: dict = {"reason": reason, "request_changes": True}
        if reason_code:
            body["reason_code"] = reason_code
        async with SpryngClient() as c:
            story_id = await c._resolve_card_id(card_ref)
            return await c.post(
                Config.project_url(
                    f"stories/{story_id}/spec-proposals/"
                    f"{proposal_id}/reject/"),
                body,
            )

    @mcp.tool()
    async def revise_spec_proposal(
        card_ref: str,
        proposal_id: str,
        repo_full_name: str = "",
    ) -> dict:
        """Dispatch a re-draft for a proposal already marked
        `revision_requested` (via request_spec_proposal_changes).

        Only a human principal may call this. Same async/202 contract as
        generate_spec_proposal — returns acceptance, not drafted content;
        poll list_spec_proposals for the new proposal to leave `generating`.
        Only one revision may be in flight per parent proposal at a time.

        Args:
            card_ref: 'ON-914'-style card reference.
            proposal_id: The public_id (UUID) of the revision_requested
                proposal to revise — NOT the new proposal this creates.
            repo_full_name: 'owner/name' override; defaults to the parent
                proposal's repo so a revision stays grounded consistently.
        """
        body: dict = {}
        if repo_full_name:
            body["repo_full_name"] = repo_full_name
        async with SpryngClient() as c:
            story_id = await c._resolve_card_id(card_ref)
            return await c.post(
                Config.project_url(
                    f"stories/{story_id}/spec-proposals/"
                    f"{proposal_id}/revise/"),
                body,
            )
