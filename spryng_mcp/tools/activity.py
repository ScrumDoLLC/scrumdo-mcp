"""
Activity log tools — structured, filterable entries attached to cards.

This is the key competitive differentiator over Monday.com: every agent,
human, and CI system writes structured activity in a consistent format.
The log is queryable by card, agent, user, action type, environment, and
milestone — directly through the MCP server, no board UI required.
"""
from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Literal

from mcp.server.fastmcp import FastMCP

from ..client import SpryngClient
from ..config import Config

# Activity entries are stored as a specially-prefixed JSON comment so they
# are human-readable in the ScrumDo UI but also machine-parseable.
_PREFIX = "<!-- spryng-activity-log -->"
_AGENT_HEADER = "**[Activity Log]**"


def _build_comment(entry: dict) -> str:
    """Render an activity entry as a markdown comment (human + machine readable)."""
    ts = entry["timestamp"]
    actor = entry.get("agent") or entry.get("user") or "unknown"
    action = entry["action"]
    detail = entry.get("detail", "")
    env = entry.get("environment", "")
    milestone = entry.get("milestone", "")

    lines = [
        _AGENT_HEADER,
        f"**{action}** · {actor} · {ts}",
    ]
    if env:
        lines.append(f"_Environment:_ {env}")
    if milestone:
        lines.append(f"_Milestone:_ {milestone}")
    if detail:
        lines.append(f"\n{detail}")
    lines.append(f"\n{_PREFIX}")
    lines.append(json.dumps(entry, separators=(",", ":")))

    return "\n".join(lines)


def _parse_comment(comment: dict) -> dict | None:
    """Extract structured activity data from a ScrumDo comment, or None."""
    body: str = comment.get("comment", "")
    if _PREFIX not in body:
        return None
    try:
        json_part = body.split(_PREFIX, 1)[1].strip()
        entry = json.loads(json_part)
        entry["_comment_id"] = comment.get("id")
        entry["_comment_author"] = comment.get("author") or comment.get("user")
        return entry
    except (json.JSONDecodeError, KeyError):
        return None


def register(mcp: FastMCP) -> None:

    @mcp.tool()
    async def log_activity(
        card_ref: str,
        action: str,
        detail: str = "",
        agent: str = "",
        user: str = "",
        environment: str = "",
        milestone: str = "",
        task_ref: str = "",
        extra: dict | None = None,
    ) -> dict:
        """
        Write a structured activity log entry to a card.

        Entries are stored as machine-parseable comments and rendered
        in the ScrumDo UI as human-readable updates. They are filterable
        via get_activity_log().

        Args:
            card_ref:    Card reference, e.g. 'ON-914'.
            action:      Short action label, e.g. 'started', 'deployed',
                         'reviewed', 'snapshot', 'seeded', 'PR opened'.
            detail:      Longer description or context (markdown).
            agent:       Agent/bot name writing the log (e.g. 'claude-code',
                         'codex', 'github-actions').
            user:        Human user involved (username or email).
            environment: Environment name (stage, integration, branch).
            milestone:   Milestone or release tag, if applicable.
            task_ref:    Related task or sub-item reference.
            extra:       Any additional structured data to attach.

        Returns the created comment object.
        """
        entry = {
            "timestamp": datetime.now(UTC).isoformat(),
            "card_ref": card_ref,
            "action": action,
            "detail": detail,
            "agent": agent,
            "user": user,
            "environment": environment,
            "milestone": milestone,
            "task_ref": task_ref,
            **(extra or {}),
        }
        comment_body = _build_comment(entry)
        async with SpryngClient() as c:
            card = await c.get_card(card_ref)
            return await c.add_comment(card["id"], comment_body)

    @mcp.tool()
    async def get_activity_log(
        card_ref: str,
        agent: str = "",
        user: str = "",
        action: str = "",
        environment: str = "",
        milestone: str = "",
        limit: int = 50,
    ) -> list[dict]:
        """
        Get the structured activity log for a card, with optional filters.

        Returns only entries written via log_activity() — plain comments are
        excluded. Results are newest-first.

        Args:
            card_ref:    Card reference, e.g. 'ON-914'.
            agent:       Filter by agent name (substring, case-insensitive).
            user:        Filter by user (substring, case-insensitive).
            action:      Filter by action label (substring, case-insensitive).
            environment: Filter by environment name (exact).
            milestone:   Filter by milestone tag (exact).
            limit:       Maximum entries to return (default 50).
        """
        async with SpryngClient() as c:
            card = await c.get_card(card_ref)
            comments = await c.list_comments(card["id"])

        entries = []
        for comment in comments:
            entry = _parse_comment(comment)
            if not entry:
                continue
            if agent and agent.lower() not in (entry.get("agent") or "").lower():
                continue
            if user and user.lower() not in (entry.get("user") or "").lower():
                continue
            if action and action.lower() not in (entry.get("action") or "").lower():
                continue
            if environment and environment != entry.get("environment"):
                continue
            if milestone and milestone != entry.get("milestone"):
                continue
            entries.append(entry)
            if len(entries) >= limit:
                break

        return entries

    @mcp.tool()
    async def get_workspace_activity(
        action: str = "",
        agent: str = "",
        user: str = "",
        environment: str = "",
        milestone: str = "",
        limit: int = 100,
    ) -> list[dict]:
        """
        Get the activity log across ALL cards in the workspace.

        Aggregates log_activity() entries from every card, sorted newest-first.
        Filterable by agent, user, action type, environment, and milestone.

        This is the workspace-level view requested for board observability —
        answers questions like:
          • "What did claude-code do today?"
          • "What was deployed to stage this week?"
          • "Show me all activity on the book-kit milestone"

        Args:
            action:      Filter by action label (substring).
            agent:       Filter by agent name (substring).
            user:        Filter by user (substring).
            environment: Filter by environment (exact).
            milestone:   Filter by milestone tag (exact).
            limit:       Max entries across all cards (default 100).

        NOTE: This scans recent cards; for large boards use per-card
              get_activity_log() for targeted queries.
        """
        async with SpryngClient() as c:
            data = await c.list_cards(limit=100)
            items = data.get("items", []) if isinstance(data, dict) else data

        all_entries: list[dict] = []
        async with SpryngClient() as c:
            for item in items:
                ref = item.get("local_id") or item.get("number")
                if not ref:
                    continue
                try:
                    comments = await c.list_comments(item["id"])
                except Exception:
                    continue
                for comment in comments:
                    entry = _parse_comment(comment)
                    if not entry:
                        continue
                    if action and action.lower() not in (entry.get("action") or "").lower():
                        continue
                    if agent and agent.lower() not in (entry.get("agent") or "").lower():
                        continue
                    if user and user.lower() not in (entry.get("user") or "").lower():
                        continue
                    if environment and environment != entry.get("environment"):
                        continue
                    if milestone and milestone != entry.get("milestone"):
                        continue
                    all_entries.append(entry)

        all_entries.sort(key=lambda e: e.get("timestamp", ""), reverse=True)
        return all_entries[:limit]
