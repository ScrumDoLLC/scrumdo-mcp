"""Custom field tools."""
from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from ..client import SpryngClient


def register(mcp: FastMCP) -> None:

    @mcp.tool()
    async def list_custom_fields(project_slug: str | None = None) -> list[dict]:
        """
        List all custom field definitions for the board.

        Each field has an id, name, field_type, and optional choices.
        Use the id when calling set_card_field() or update_card(extra_fields=…).

        Args:
            project_slug: Board slug. Defaults to the configured project.
        """
        async with SpryngClient() as c:
            return await c.list_custom_fields(project_slug)

    @mcp.tool()
    async def get_card_field(card_ref: str, field_id: int) -> dict:
        """
        Get the current value of a single custom field on a card.

        Args:
            card_ref:  Card reference, e.g. 'ON-914'.
            field_id:  Numeric custom field id from list_custom_fields().

        Returns {'field_id': …, 'name': …, 'value': …} or {'field_id': …, 'value': null}
        if the field is not set.
        """
        async with SpryngClient() as c:
            story_id = await c._resolve_card_id(card_ref)
            fields = await c.get_card_customfields(story_id)
        for entry in fields:
            if entry.get("field", {}).get("id") == field_id:
                return {
                    "field_id": field_id,
                    "name": entry["field"].get("name"),
                    "value": entry.get("value"),
                }
        return {"field_id": field_id, "value": None}

    @mcp.tool()
    async def get_all_card_fields(card_ref: str) -> list[dict]:
        """
        Get all custom field values currently set on a card.

        Returns the full list of custom fields with their names and current values.

        Args:
            card_ref: Card reference, e.g. 'ON-914'.
        """
        async with SpryngClient() as c:
            story_id = await c._resolve_card_id(card_ref)
            return await c.get_card_customfields(story_id)
