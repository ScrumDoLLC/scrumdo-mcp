"""Search tools."""
from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from ..client import SpryngClient


def register(mcp: FastMCP) -> None:

    @mcp.tool()
    async def search_cards(query: str) -> list[dict]:
        """
        Full-text search across all cards in the organisation.

        Searches card summaries, descriptions, and comments.

        Args:
            query: Search string. Supports partial matches.

        Returns a ranked list of matching cards with summary, reference,
        board name, and a short excerpt.
        """
        async with SpryngClient() as c:
            return await c.search(query)

    @mcp.tool()
    async def search_by_field_value(field_id: int, value: str, limit: int = 50) -> list[dict]:
        """
        Find all cards where a custom field contains a given value.

        Useful for finding cards tagged with a specific branch, PR URL,
        feature flag, or any other custom field content.

        Args:
            field_id: Numeric custom field id from list_custom_fields().
            value:    Value to match (substring match, case-insensitive).
            limit:    Maximum cards to scan (default 50).

        Returns matching card objects.
        """
        async with SpryngClient() as c:
            data = await c.list_cards(limit=limit)
        items = data.get("items", data) if isinstance(data, dict) else data
        key = str(field_id)
        return [
            item for item in items
            if value.lower() in str((item.get("extra_fields") or {}).get(key, "")).lower()
        ]
