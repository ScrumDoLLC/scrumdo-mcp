"""Task (checklist item) tools."""
from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from ..client import SpryngClient


def register(mcp: FastMCP) -> None:

    @mcp.tool()
    async def list_tasks(card_ref: str) -> list[dict]:
        """
        List all tasks (checklist items) on a card.

        Args:
            card_ref: Card reference, e.g. 'ON-914'.

        Returns a list of tasks, each with id, description, complete flag,
        assignee, and position.
        """
        async with SpryngClient() as c:
            return await c.list_tasks(card_ref)

    @mcp.tool()
    async def create_task(
        card_ref: str,
        description: str,
        assignee_id: int | None = None,
    ) -> dict:
        """
        Create a new task on a card.

        Args:
            card_ref:    Card reference, e.g. 'ON-914'.
            description: Task description (plain text or markdown).
            assignee_id: Optional user ID to assign the task to.

        Returns the created task object.
        """
        body: dict = {"description": description}
        if assignee_id is not None:
            body["assignee"] = assignee_id
        async with SpryngClient() as c:
            return await c.create_task(card_ref, body)

    @mcp.tool()
    async def complete_task(card_ref: str, task_id: int) -> dict:
        """
        Mark a task as complete.

        Args:
            card_ref: Card reference, e.g. 'ON-914'.
            task_id:  Task id (from list_tasks).
        """
        async with SpryngClient() as c:
            return await c.update_task(card_ref, task_id, {"complete": True})

    @mcp.tool()
    async def reopen_task(card_ref: str, task_id: int) -> dict:
        """
        Reopen (un-complete) a task.

        Args:
            card_ref: Card reference, e.g. 'ON-914'.
            task_id:  Task id (from list_tasks).
        """
        async with SpryngClient() as c:
            return await c.update_task(card_ref, task_id, {"complete": False})

    @mcp.tool()
    async def update_task(
        card_ref: str,
        task_id: int,
        description: str | None = None,
        complete: bool | None = None,
        assignee_id: int | None = None,
    ) -> dict:
        """
        Update a task's description, completion state, or assignee.

        Args:
            card_ref:    Card reference, e.g. 'ON-914'.
            task_id:     Task id (from list_tasks).
            description: New description (leave None to keep current).
            complete:    True to complete, False to reopen.
            assignee_id: New assignee user id.
        """
        body: dict = {}
        if description is not None:
            body["description"] = description
        if complete is not None:
            body["complete"] = complete
        if assignee_id is not None:
            body["assignee"] = assignee_id
        async with SpryngClient() as c:
            return await c.update_task(card_ref, task_id, body)

    @mcp.tool()
    async def delete_task(card_ref: str, task_id: int) -> str:
        """
        Delete a task from a card.

        Args:
            card_ref: Card reference, e.g. 'ON-914'.
            task_id:  Task id (from list_tasks).
        """
        async with SpryngClient() as c:
            status = await c.delete_task(card_ref, task_id)
        return f"Task {task_id} deleted (HTTP {status})"
