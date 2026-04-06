"""Board / project tools."""
from __future__ import annotations

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
