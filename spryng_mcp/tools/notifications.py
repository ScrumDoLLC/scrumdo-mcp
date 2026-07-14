"""Notification tools — the in-app message center, for the token's identity.

Lets an MCP session check what the platform is trying to tell it: approval
requests, run outcomes, mentions, digests. Messages belong to the
authenticated identity (the token's user — for agent tokens, the agent).

Typical agent use: poll list_notifications(status='unread') between work
units to discover "your plan was approved" / "changes requested" without
re-fetching whole cards; acknowledge what you've acted on so humans watching
the same queue see it handled. Reading is always safe; these tools never
send anything to other people.
"""
from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from ..client import SpryngClient


def register(mcp: FastMCP) -> None:

    @mcp.tool()
    async def list_notifications(
        status: str | None = "unread",
        category: str | None = None,
        limit: int = 50,
    ) -> dict:
        """
        List in-app notifications for the authenticated identity, newest
        first.

        Args:
            status:   Filter — 'unread' (default), 'read', 'acknowledged',
                      'dismissed', or None for all.
            category: Optional category filter (as shown in each message's
                      'category' field — e.g. agent runs, approvals).
            limit:    Max messages (1-100, default 50).

        Returns {'results': [...], 'count': N}; each message carries id,
        kind, category, title/body, created time, and read state.
        """
        async with SpryngClient() as c:
            return await c.list_notifications(
                status=status, category=category, limit=limit)

    @mcp.tool()
    async def notification_counts() -> dict:
        """
        Unread/total counts for the authenticated identity's notification
        inbox — a cheap poll before deciding to fetch the list.
        """
        async with SpryngClient() as c:
            return await c.notification_counts()

    @mcp.tool()
    async def mark_notification(message_id: int, action: str = "read") -> dict:
        """
        Mark one notification: 'read' (seen), 'acknowledge' (handled — use
        this after acting on an approval/request so humans see it covered),
        or 'dismiss' (not relevant).

        Args:
            message_id: Message id (from list_notifications).
            action:     'read' | 'acknowledge' | 'dismiss'.
        """
        if action not in ("read", "acknowledge", "dismiss"):
            raise ValueError("action must be 'read', 'acknowledge' or 'dismiss'")
        async with SpryngClient() as c:
            return await c.notification_action(message_id, action)

    @mcp.tool()
    async def mark_all_notifications_read() -> dict:
        """Mark every unread notification as read for this identity."""
        async with SpryngClient() as c:
            return await c.mark_all_notifications_read()

    @mcp.tool()
    async def wait_for_notifications(after: int = 0, timeout_s: int = 25) -> dict:
        """
        BLOCK until a new notification arrives (the push channel) — one call
        replaces a poll-sleep loop. The server holds the request and returns
        the moment a message newer than ``after`` lands, or after
        ``timeout_s`` with an empty page.

        Args:
            after:     Cursor from the previous call's 'cursor' field
                       (0 = anything currently unread returns immediately).
            timeout_s: Seconds to wait server-side (capped at 30).

        Returns {'results': [...], 'count': N, 'cursor': M}. ALWAYS pass the
        returned cursor into your next call — an empty result with the same
        cursor just means "nothing new yet; call again".
        """
        async with SpryngClient() as c:
            return await c.wait_for_notifications(
                after=after, timeout_s=timeout_s)
