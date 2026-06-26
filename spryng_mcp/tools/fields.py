"""Custom field tools."""
from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from ..client import SpryngClient


def register(mcp: FastMCP) -> None:

    @mcp.tool()
    async def list_custom_fields(project_slug: str | None = None) -> list[dict]:
        """
        List all custom field definitions for the board.

        Each field has an id, name, field_type, and optional choices list.
        Use the numeric id when calling set_card_field(), set_card_fields(),
        or update_card(extra_fields={id: value}).

        To see what values a specific card currently has, use get_all_card_fields().
        To see everything settable on a card (labels, tags, custom fields) in one
        call, use get_card().

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
            field_id:  Numeric custom field id. Use list_custom_fields() to find ids.

        Returns {'field_id': …, 'name': …, 'value': …}, or {'field_id': …, 'value': null}
        if the field has not been set on this card.
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
        This covers only the structured custom fields — for labels and tags, use
        get_card() which returns the complete card including labels (list of
        {id, name, color} objects) and tags (comma-separated string).

        Args:
            card_ref: Card reference, e.g. 'ON-914'.
        """
        async with SpryngClient() as c:
            story_id = await c._resolve_card_id(card_ref)
            return await c.get_card_customfields(story_id)

    @mcp.tool()
    async def set_card_fields(card_ref: str, fields: dict) -> dict:
        """
        Set multiple custom fields on a card in a single request.

        Prefer this over calling set_card_field() repeatedly — it does one
        GET and one PUT regardless of how many fields you're updating.

        Args:
            card_ref: Card reference, e.g. 'ON-914'.
            fields:   Mapping of field_id (int) → value (str) for every field
                      you want to set, e.g. {"5303": "...", "5304": "..."}.
                      Keys may be ints or strings — both are accepted.

        Returns the updated custom fields array.
        """
        normalised = {int(k): v for k, v in fields.items()}
        async with SpryngClient() as c:
            return await c.set_custom_fields(card_ref, normalised)
