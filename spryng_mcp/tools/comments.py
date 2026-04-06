"""Comment / update tools."""
from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from ..client import SpryngClient


def register(mcp: FastMCP) -> None:

    @mcp.tool()
    async def list_comments(card_ref: str) -> list[dict]:
        """
        List all comments on a card, newest first.

        Args:
            card_ref: Card reference, e.g. 'ON-914'. The card's numeric id
                      is resolved automatically.

        Returns a list of comments with id, author, body (markdown),
        and created timestamp.
        """
        async with SpryngClient() as c:
            card = await c.get_card(card_ref)
            return await c.list_comments(card["id"])

    @mcp.tool()
    async def add_comment(card_ref: str, body: str) -> dict:
        """
        Post a comment on a card. Markdown is supported.

        Args:
            card_ref: Card reference, e.g. 'ON-914'.
            body:     Comment text (markdown). Code blocks, lists, and
                      headers all render in the ScrumDo UI.

        Returns the created comment object with id and timestamp.
        """
        async with SpryngClient() as c:
            card = await c.get_card(card_ref)
            return await c.add_comment(card["id"], body)

    @mcp.tool()
    async def delete_comment(comment_id: int) -> str:
        """
        Delete a comment by its id.

        Args:
            comment_id: Numeric comment id from list_comments.
        """
        async with SpryngClient() as c:
            status = await c.delete_comment(comment_id)
        return f"Comment {comment_id} deleted (HTTP {status})"
