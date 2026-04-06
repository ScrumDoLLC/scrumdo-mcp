"""Member / team tools."""
from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from ..client import SpryngClient


def register(mcp: FastMCP) -> None:

    @mcp.tool()
    async def list_members(project_slug: str | None = None) -> list[dict]:
        """
        List members of the organisation or a specific project.

        Each member has an id, username, email, display_name, and role.

        Args:
            project_slug: If provided, returns project-level members only.
                          If omitted, returns all org members.
        """
        async with SpryngClient() as c:
            return await c.list_members(project_slug)

    @mcp.tool()
    async def find_member(query: str) -> list[dict]:
        """
        Find a member by name, username, or email.

        Args:
            query: Name, username, or email fragment to search.

        Returns matching members from the org member list.
        """
        async with SpryngClient() as c:
            members = await c.list_members()
        q = query.lower()
        return [
            m for m in members
            if q in (m.get("username") or "").lower()
            or q in (m.get("email") or "").lower()
            or q in (m.get("display_name") or "").lower()
            or q in (m.get("name") or "").lower()
        ]
