"""Webhook tools."""
from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from ..client import SpryngClient


def register(mcp: FastMCP) -> None:

    @mcp.tool()
    async def list_webhooks() -> list[dict]:
        """
        List all webhooks configured on the project.

        Returns each webhook's id, url, events, and active state.
        """
        async with SpryngClient() as c:
            return await c.list_webhooks()

    @mcp.tool()
    async def create_webhook(
        url: str,
        events: list[str],
        secret: str = "",
    ) -> dict:
        """
        Create a new webhook on the project.

        Args:
            url:    HTTPS endpoint that will receive webhook POST requests.
            events: List of event names to subscribe to, e.g.
                    ['story.created', 'story.updated', 'story.moved',
                     'task.completed', 'comment.created'].
            secret: Optional HMAC secret for payload signature verification.

        Returns the created webhook object with its id.
        """
        body: dict = {"url": url, "events": events}
        if secret:
            body["secret"] = secret
        async with SpryngClient() as c:
            return await c.create_webhook(body)

    @mcp.tool()
    async def delete_webhook(webhook_id: int) -> str:
        """
        Delete a webhook by id.

        Args:
            webhook_id: Webhook id from list_webhooks().
        """
        async with SpryngClient() as c:
            status = await c.delete_webhook(webhook_id)
        return f"Webhook {webhook_id} deleted (HTTP {status})"
