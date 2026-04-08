"""Blocker tools — block and unblock cards."""
from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from ..client import SpryngClient


def register(mcp: FastMCP) -> None:

    @mcp.tool()
    async def list_blockers(card_ref: str) -> list[dict]:
        """
        List all active (unresolved) blockers on a card.

        Each blocker includes id, reason, blocked_date, blocker (user),
        is_show_stopper, and external flags.

        Args:
            card_ref: Card reference, e.g. 'ON-914'.
        """
        async with SpryngClient() as c:
            return await c.list_blockers(card_ref)

    @mcp.tool()
    async def block_card(
        card_ref: str,
        reason: str,
        is_show_stopper: bool = False,
        external: bool = False,
    ) -> dict:
        """
        Mark a card as blocked with a reason.

        Creates a blocker record on the card. Multiple blockers can exist
        simultaneously; the card remains blocked until all are resolved.

        Args:
            card_ref:        Card reference, e.g. 'ON-914'.
            reason:          Human-readable explanation of what is blocking the card.
            is_show_stopper: Flag this as a show-stopper blocker (default False).
            external:        Flag as an external dependency (default False).

        Returns the created blocker object including its id (needed to unblock).
        """
        body = {
            "reason": reason,
            "is_show_stopper": is_show_stopper,
            "external": external,
        }
        async with SpryngClient() as c:
            return await c.block_card(card_ref, body)

    @mcp.tool()
    async def unblock_card(
        card_ref: str,
        blocker_id: int,
        resolution: str = "",
    ) -> dict:
        """
        Resolve (unblock) a specific blocker on a card.

        If this was the last active blocker, the card's blocked flag is cleared.
        Use list_blockers() to find the blocker_id.

        Args:
            card_ref:   Card reference, e.g. 'ON-914'.
            blocker_id: Numeric blocker id from list_blockers().
            resolution: Optional description of how the block was resolved.

        Returns the resolved blocker object.
        """
        body = {"resolution": resolution}
        async with SpryngClient() as c:
            return await c.unblock_card(card_ref, blocker_id, body)
