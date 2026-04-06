"""Time tracking tools."""
from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from ..client import SpryngClient


def register(mcp: FastMCP) -> None:

    @mcp.tool()
    async def list_time_entries(card_ref: str | None = None) -> list[dict]:
        """
        List time entries, optionally filtered to a specific card.

        Args:
            card_ref: Card reference, e.g. 'ON-914'. If omitted, returns
                      all project time entries.
        """
        async with SpryngClient() as c:
            return await c.list_time_entries(card_ref)

    @mcp.tool()
    async def log_time(
        card_ref: str,
        minutes: int,
        description: str = "",
        date: str = "",
        user_id: int | None = None,
    ) -> dict:
        """
        Log time spent on a card.

        Args:
            card_ref:    Card reference, e.g. 'ON-914'.
            minutes:     Time spent in minutes.
            description: What was done during this time.
            date:        ISO date string (YYYY-MM-DD). Defaults to today.
            user_id:     User to log time for. Defaults to the token owner.

        Returns the created time entry.
        """
        body: dict = {"time": minutes, "description": description}
        if date:
            body["date"] = date
        if user_id is not None:
            body["user"] = user_id
        async with SpryngClient() as c:
            return await c.log_time(card_ref, body)
