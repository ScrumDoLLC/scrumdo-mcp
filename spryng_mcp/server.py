"""
spryng_mcp.server — FastMCP server entrypoint.

Registers all tools and starts the MCP server over stdio.

Usage:
    # Run directly
    python -m spryng_mcp.server

    # Or via the installed CLI
    spryng-mcp

    # Add to Claude Code
    claude mcp add spryng -- python -m spryng_mcp.server

Environment variables (set in mcp/.env or export before running):
    SPRYNG_TOKEN      Bearer token for the ScrumDo / Spryng API (required)
    SPRYNG_BASE_URL   API base URL (default: https://app.spryng.io)
    SPRYNG_ORG        Organisation slug (default: spryng-internal)
    SPRYNG_PROJECT    Default project slug (default: onboarding)
"""
from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from .config import Config
from .tools import (
    activity,
    boards,
    cards,
    comments,
    fields,
    members,
    search,
    tasks,
    time_tracking,
    webhooks,
)

# ── Server definition ──────────────────────────────────────────────────────────

mcp = FastMCP(
    name="spryng",
    instructions=f"""
You are connected to a ScrumDo / Spryng board.

Default context:
  Organisation: {Config.org}
  Project:      {Config.project}
  Base URL:     {Config.base_url}

This MCP server gives you full Monday.com-level access to the board:
  • Read and write cards (stories) with all custom fields
  • Move cards between columns, assign members, manage labels
  • Create, complete, and delete tasks (checklist items)
  • Post and read comments
  • Write and query structured activity log entries (log_activity / get_activity_log)
  • Search cards by text or custom field value
  • Manage webhooks, time tracking, custom fields, members, labels, and iterations

Key conventions for this project:
  - Card references are in the format ON-<number>, e.g. ON-914
  - Custom field IDs: 5303=Feature Identity, 5304=Promotion Status,
    5306=Branch Path, 5307=Human Review, 5422=Intended Promotion Path,
    5425=Test Contract, 5426=Outcome, 5428=Run Evidence, 5430=Feature Statement,
    5432=In Scope, 5433=Commit Links, 5436=Behavior Contract,
    5437=Out of Scope, 5439=Repos Attached
  - Board cells (columns): 18531=Analyze, 20132=Being Developed,
    20133=Ready for Stage Pull, 16246=Integrated

Use log_activity() to record agent actions against cards so the workspace
activity log stays current and filterable.
""".strip(),
)

# ── Register all tool groups ───────────────────────────────────────────────────

boards.register(mcp)
cards.register(mcp)
tasks.register(mcp)
comments.register(mcp)
fields.register(mcp)
members.register(mcp)
search.register(mcp)
activity.register(mcp)
webhooks.register(mcp)
time_tracking.register(mcp)


# ── Entrypoint ─────────────────────────────────────────────────────────────────

def main() -> None:
    Config.validate()
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
