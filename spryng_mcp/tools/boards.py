"""Board / project tools."""
from __future__ import annotations

import asyncio

from mcp.server.fastmcp import FastMCP

from ..client import SpryngClient
from ..config import Config


def register(mcp: FastMCP) -> None:

    @mcp.tool()
    async def list_boards() -> list[dict]:
        """
        List all boards (projects) in the organisation.

        Returns each board's slug, name, description, and member count.
        Use get_board() for full detail on a specific board.
        """
        async with SpryngClient() as c:
            return await c.list_boards()

    @mcp.tool()
    async def get_board(project_slug: str | None = None) -> dict:
        """
        Get a board (project) with its cells (columns), custom field definitions,
        and key statistics.

        Args:
            project_slug: Board slug to fetch. Defaults to the configured project.
        """
        async with SpryngClient() as c:
            board = await c.get_board(project_slug)
            cells = await c.get_board_cells(project_slug)
            fields = await c.list_custom_fields(project_slug)
            board["cells"] = cells
            board["custom_fields"] = fields
            return board

    @mcp.tool()
    async def get_board_cells(project_slug: str | None = None) -> list[dict]:
        """
        List the columns (cells) of a board.

        Each cell has an id, name, and position. Use the id when moving cards.

        Args:
            project_slug: Board slug. Defaults to the configured project.
        """
        async with SpryngClient() as c:
            return await c.get_board_cells(project_slug)

    @mcp.tool()
    async def list_iterations(project_slug: str | None = None) -> list[dict]:
        """
        List all iterations (sprints / milestones) in the project.

        Args:
            project_slug: Board slug. Defaults to the configured project.
        """
        async with SpryngClient() as c:
            return await c.list_iterations()

    @mcp.tool()
    async def list_labels(project_slug: str | None = None) -> list[dict]:
        """
        List all labels defined in the project.

        Returns each label's id, name, and color. Use the numeric id with
        add_card_label(), remove_card_label(), or update_card(label_ids=[...]).
        To see which labels are currently on a card, use get_card().

        Args:
            project_slug: Board slug. Defaults to the configured project.
        """
        async with SpryngClient() as c:
            return await c.list_labels()

    @mcp.tool()
    async def list_epics(project_slug: str | None = None) -> list[dict]:
        """
        List all epics in the project.

        Args:
            project_slug: Board slug. Defaults to the configured project.
        """
        async with SpryngClient() as c:
            return await c.list_epics()

    @mcp.tool()
    async def list_milestones(project_slug: str | None = None) -> list[dict]:
        """
        List all milestones for a project.

        In ScrumDo, milestones are called 'releases' — they are portfolio-level
        stories that team cards can be assigned to, used to track work toward a
        delivery target. Cards show which milestone they belong to via the
        'release' field returned by get_card().

        Use the numeric id from this list with:
          - create_card(milestone_id=...)
          - update_card(card_ref, milestone_id=...)   pass 0 to clear

        Args:
            project_slug: Board slug. Defaults to the configured project.
                          For team boards, pass the parent portfolio slug to
                          see milestones defined at the portfolio level.
        """
        async with SpryngClient() as c:
            return await c.list_milestones(project_slug)

    @mcp.tool()
    async def card_schema() -> dict:
        """
        Return a complete guide to every field that can be set on a card or task.

        Call this once before writing cards or tasks for the first time.
        It fetches custom field definitions, available labels, and board columns
        in a single parallel request and returns them alongside descriptions of
        all standard fields and task fields.

        Returns a dict with keys:
          card_fields   — all writable fields on a card (standard + custom)
          task_fields   — all writable fields on a task (checklist item)
          labels        — list of {id, name, color} available to attach to cards
          cells         — list of {id, name} board columns for move_card()
        """
        async with SpryngClient() as c:
            custom_fields, labels, cells = await asyncio.gather(
                c.list_custom_fields(),
                c.list_labels(),
                c.get_board_cells(),
            )

        return {
            "card_fields": {
                "standard": [
                    {
                        "field": "summary",
                        "type": "string",
                        "required": True,
                        "description": "Card title — one concise sentence describing the work.",
                    },
                    {
                        "field": "description",
                        "type": "markdown string",
                        "required": False,
                        "description": (
                            "Rich body text. Use markdown. Describe the goal, context, "
                            "and acceptance criteria. For feature cards follow the pattern: "
                            "'As a <role>, I want <capability> so that <benefit>.'"
                        ),
                    },
                    {
                        "field": "points",
                        "type": "integer",
                        "required": False,
                        "description": "Story-point estimate. Typical scale: 1, 2, 3, 5, 8, 13.",
                    },
                    {
                        "field": "due_date",
                        "type": "YYYY-MM-DD string",
                        "required": False,
                        "description": "Target completion date. Pass '' to clear.",
                    },
                    {
                        "field": "label_ids",
                        "type": "list[int]",
                        "required": False,
                        "description": (
                            "Labels to attach. Pass a list of label ids from the "
                            "'labels' key in this response. Replaces the full label set."
                        ),
                    },
                    {
                        "field": "tags",
                        "type": "comma-separated string",
                        "required": False,
                        "description": (
                            "Free-form tags, e.g. 'backend,qa,blocked'. "
                            "Replaces the current tag list. Pass '' to clear."
                        ),
                    },
                    {
                        "field": "assignee_ids",
                        "type": "list[int]",
                        "required": False,
                        "description": "Member ids to assign. Use list_members() to find ids.",
                    },
                    {
                        "field": "iteration_id",
                        "type": "integer",
                        "required": False,
                        "description": "Sprint/iteration to place the card in. Use list_iterations().",
                    },
                    {
                        "field": "cell_id",
                        "type": "integer",
                        "required": False,
                        "description": (
                            "Board column to place the card in (create) or move to (update). "
                            "See 'cells' key in this response for valid ids."
                        ),
                    },
                    {
                        "field": "milestone_id",
                        "type": "integer",
                        "required": False,
                        "description": (
                            "Milestone (release) to assign this card to. "
                            "Use list_milestones() to find ids. Pass 0 to clear."
                        ),
                    },
                ],
                "custom_fields": [
                    {
                        "field_id": entry.get("id"),
                        "name": entry.get("name"),
                        "type": entry.get("field_type"),
                        "choices": entry.get("choices") or [],
                        "description": (
                            f"Set via set_card_field(card_ref, {entry.get('id')!r}, value) "
                            f"or include in set_card_fields() / update_card(extra_fields={{...}})."
                        ),
                    }
                    for entry in (custom_fields or [])
                ],
            },
            "task_fields": [
                {
                    "field": "summary",
                    "type": "string",
                    "required": True,
                    "description": "Task title — a short imperative action, e.g. 'Write unit tests for auth flow'.",
                },
                {
                    "field": "completed",
                    "type": "boolean",
                    "required": False,
                    "description": "True marks the task done. Use complete_task() / reopen_task() helpers.",
                },
            ],
            "labels": labels or [],
            "cells": cells or [],
        }
