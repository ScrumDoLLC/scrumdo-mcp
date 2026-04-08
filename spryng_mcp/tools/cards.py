"""Card (story) tools — the core of the board."""
from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from ..client import SpryngClient
from ..config import Config


def register(mcp: FastMCP) -> None:

    @mcp.tool()
    async def list_cards(
        cell_id: int | None = None,
        iteration_id: int | None = None,
        assignee: str | None = None,
        label: str | None = None,
        status: str | None = None,
        page: int = 1,
        limit: int = 25,
    ) -> dict:
        """
        List cards on the board with optional filters.

        Args:
            cell_id:      Filter by board column (cell) id.
            iteration_id: Filter by iteration/sprint id.
            assignee:     Filter by assignee username or email.
            label:        Filter by label name.
            status:       Filter by status string.
            page:         Page number (default 1).
            limit:        Results per page (default 25, max 100).

        Returns a dict with count, next/previous page URLs, and items list.
        Each item includes id, local_id, summary, points, cell, assignees, labels,
        extra_fields (custom fields), and created/updated timestamps.
        """
        filters: dict[str, Any] = {"page": page, "limit": limit}
        if cell_id is not None:
            filters["cell_id"] = cell_id
        if iteration_id is not None:
            filters["iteration_id"] = iteration_id
        if assignee:
            filters["assignee"] = assignee
        if label:
            filters["label"] = label
        if status:
            filters["status"] = status
        async with SpryngClient() as c:
            return await c.list_cards(**filters)

    @mcp.tool()
    async def get_card(card_ref: str) -> dict:
        """
        Get a card's full detail including all custom fields, task list,
        comment count, labels, assignees, and linked cards.

        Args:
            card_ref: The card reference, e.g. 'ON-914' or 'Q1-42'.
        """
        async with SpryngClient() as c:
            return await c.get_card(card_ref)

    @mcp.tool()
    async def find_card(card_ref: str) -> dict:
        """
        Find a card by its reference ID (e.g. 'ON-914').
        Alias for get_card — useful when you only know the ID string.

        Args:
            card_ref: Card reference like 'ON-914'.
        """
        async with SpryngClient() as c:
            return await c.get_card(card_ref)

    @mcp.tool()
    async def create_card(
        summary: str,
        description: str = "",
        points: int | None = None,
        due_date: str | None = None,
        cell_id: int | None = None,
        iteration_id: int | None = None,
        assignee_ids: list[int] | None = None,
        label_ids: list[int] | None = None,
        extra_fields: dict[str, str] | None = None,
    ) -> dict:
        """
        Create a new card on the board.

        Args:
            summary:       Card title / summary (required).
            description:   Rich text description (markdown supported).
            points:        Story points / estimate.
            due_date:      Due date in YYYY-MM-DD format.
            cell_id:       Board column to place the card in.
            iteration_id:  Iteration/sprint to assign the card to.
            assignee_ids:  List of user IDs to assign. Use list_members() to find ids.
            label_ids:     List of label IDs to attach.
            extra_fields:  Custom field values as {field_id: value} dict.

        Returns the full created card object including its assigned reference (e.g. 'ON-915').
        """
        body: dict[str, Any] = {"summary": summary}
        if description:
            body["description"] = description
        if points is not None:
            body["points"] = points
        if due_date:
            body["due_date"] = due_date
        if cell_id is not None:
            body["cell"] = cell_id
        if iteration_id is not None:
            body["iteration"] = iteration_id
        if assignee_ids:
            body["assignees"] = assignee_ids
        if label_ids:
            body["labels"] = label_ids
        if extra_fields:
            body["extra_fields"] = extra_fields
        async with SpryngClient() as c:
            return await c.create_card(body)

    @mcp.tool()
    async def update_card(
        card_ref: str,
        summary: str | None = None,
        description: str | None = None,
        points: int | None = None,
        status: str | None = None,
        due_date: str | None = None,
        iteration_id: int | None = None,
        assignee_ids: list[int] | None = None,
        label_ids: list[int] | None = None,
        extra_fields: dict[str, str] | None = None,
    ) -> dict:
        """
        Update one or more fields on an existing card.

        Only the fields you provide will be changed — omitted fields are untouched.

        Args:
            card_ref:      Card reference, e.g. 'ON-914'.
            summary:       New title.
            description:   New description (markdown).
            points:        New story points.
            status:        New status string.
            due_date:      Due date in YYYY-MM-DD format. Pass empty string to clear.
            iteration_id:  Move card to this iteration/sprint id. Use list_iterations()
                           to find ids. Pass 0 to remove from all iterations.
            assignee_ids:  Replace assignee list. Use list_members() to find ids.
            label_ids:     Replace label list.
            extra_fields:  Merge into existing custom fields. Existing keys not
                           mentioned here will be preserved.

        Returns the full updated card object.
        """
        body: dict[str, Any] = {}
        if summary is not None:
            body["summary"] = summary
        if description is not None:
            body["description"] = description
        if points is not None:
            body["points"] = points
        if status is not None:
            body["status"] = status
        if due_date is not None:
            body["due_date"] = due_date or None
        if iteration_id is not None:
            body["iteration"] = iteration_id if iteration_id != 0 else None
        if assignee_ids is not None:
            body["assignees"] = assignee_ids
        if label_ids is not None:
            body["labels"] = label_ids

        async with SpryngClient() as c:
            if extra_fields:
                card = await c.get_card(card_ref)
                existing = dict(card.get("extra_fields") or {})
                existing.update(extra_fields)
                body["extra_fields"] = existing
            return await c.update_card(card_ref, body)

    @mcp.tool()
    async def move_card(card_ref: str, cell_id: int) -> dict:
        """
        Move a card to a different column (cell) on the board.

        Args:
            card_ref: Card reference, e.g. 'ON-914'.
            cell_id:  Target cell id. Use get_board_cells() to find cell ids.

        Returns the updated card.
        """
        async with SpryngClient() as c:
            return await c.update_card(card_ref, {"cell": cell_id})

    @mcp.tool()
    async def move_card_to_iteration(card_ref: str, iteration_id: int) -> dict:
        """
        Move a card into an iteration (sprint).

        Args:
            card_ref:     Card reference, e.g. 'ON-914'.
            iteration_id: Target iteration id. Use list_iterations() to find ids.
                          Pass 0 to remove the card from its current iteration.

        Returns the updated card.
        """
        async with SpryngClient() as c:
            body = {"iteration": iteration_id if iteration_id != 0 else None}
            return await c.update_card(card_ref, body)

    @mcp.tool()
    async def set_card_field(card_ref: str, field_id: int, value: str) -> dict:
        """
        Set a single custom field on a card without touching other fields.

        Args:
            card_ref:  Card reference, e.g. 'ON-914'.
            field_id:  Numeric custom field id. Use list_custom_fields() to look up ids.
            value:     New field value (always a string).

        Returns the updated card.
        """
        async with SpryngClient() as c:
            return await c.set_custom_field(card_ref, field_id, value)

    @mcp.tool()
    async def archive_card(card_ref: str) -> dict:
        """
        Archive a card (soft delete — card is hidden but recoverable).

        Args:
            card_ref: Card reference, e.g. 'ON-914'.
        """
        async with SpryngClient() as c:
            return await c.update_card(card_ref, {"archived": True})

    @mcp.tool()
    async def assign_card(card_ref: str, assignee_ids: list[int]) -> dict:
        """
        Set the assignees on a card, replacing any current assignees.

        Args:
            card_ref:     Card reference, e.g. 'ON-914'.
            assignee_ids: List of user IDs. Pass an empty list to unassign all.
        """
        async with SpryngClient() as c:
            return await c.update_card(card_ref, {"assignees": assignee_ids})

    @mcp.tool()
    async def add_card_label(card_ref: str, label_id: int) -> dict:
        """
        Add a single label to a card, preserving existing labels.

        Args:
            card_ref: Card reference, e.g. 'ON-914'.
            label_id: Label id to add. Use list_labels() to find ids.
        """
        async with SpryngClient() as c:
            card = await c.get_card(card_ref)
            existing_ids = [lbl["id"] if isinstance(lbl, dict) else lbl
                            for lbl in (card.get("labels") or [])]
            if label_id not in existing_ids:
                existing_ids.append(label_id)
            return await c.update_card(card_ref, {"labels": existing_ids})

    @mcp.tool()
    async def remove_card_label(card_ref: str, label_id: int) -> dict:
        """
        Remove a single label from a card.

        Args:
            card_ref: Card reference, e.g. 'ON-914'.
            label_id: Label id to remove.
        """
        async with SpryngClient() as c:
            card = await c.get_card(card_ref)
            existing_ids = [lbl["id"] if isinstance(lbl, dict) else lbl
                            for lbl in (card.get("labels") or [])]
            updated = [i for i in existing_ids if i != label_id]
            return await c.update_card(card_ref, {"labels": updated})
