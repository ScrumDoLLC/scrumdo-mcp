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
    agent_runs,
    agents,
    blockers,
    boards,
    cards,
    comments,
    fields,
    github,
    intelligence,
    loops,
    members,
    search,
    spec,
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

If you are running as an AI agent (BOARD_AI_AGENTS_UNIFIED_SPEC §13.4):
  1. Call get_agent_identity() first; capture current_run_id.
  2. If a run is active, set SPRYNG_AGENT_RUN_ID in the environment so
     every outbound write carries the X-Spryng-Agent-Run header.
  3. Read the card spec via get_card_spec(card_ref) before any write.
     Never write a frontmatter field that isn't in the writable list
     (spec §F.2). Whitelisted keys for agents:
       promotion_status, run_evidence, outcome, human_review,
       agent_context.decisions, agent_context.open_questions, and
       the spec body text.
  4. Always provide a change_summary on spec writes.
  5. Use patch_card_spec for single-field updates — don't overwrite the
     whole content with set_card_spec when one frontmatter key changes.
  6. To attach a PR / commit / issue to a card, call link_github_pr
     (or link_github_commit / link_github_issue) — NEVER write the
     `commit_links` frontmatter key directly. That field is a read-only
     view over StoryGitHubLink rows (spec §D.2 + D3).
  7. To advance the AgentRun state machine, call report_agent_progress(
     run_id, state, ...). Do NOT move the state machine through any
     other surface. State transitions through other endpoints are
     rejected (spec §E.7).

Agent ACL recap (§F.2):
  - Agents may read any card on boards they are members of.
  - Agents may write only to cards they are explicitly assigned to.
  - Agents may NEVER: merge PRs, push to the repo default branch, or
    mutate org config (AgentProfile / LLMConfig / AgentRuntimeConfig).
""".strip(),
)

# ── Register all tool groups ───────────────────────────────────────────────────

boards.register(mcp)
blockers.register(mcp)
cards.register(mcp)
tasks.register(mcp)
comments.register(mcp)
fields.register(mcp)
members.register(mcp)
search.register(mcp)
activity.register(mcp)
webhooks.register(mcp)
time_tracking.register(mcp)
# Phase A (BOARD_AI_AGENTS_UNIFIED_SPEC §A.5) — agent identity tools.
agents.register(mcp)
# Phase B (BOARD_AI_AGENTS_UNIFIED_SPEC §5.6) — card spec tools.
spec.register(mcp)
# Phase D (BOARD_AI_AGENTS_UNIFIED_SPEC §D.4) — GitHub link tools.
github.register(mcp)
# Phase E (BOARD_AI_AGENTS_UNIFIED_SPEC §E.7) — AgentRun lifecycle tools.
agent_runs.register(mcp)
loops.register(mcp)
# Phase G (BOARD_AI_AGENTS_UNIFIED_SPEC §10) — AI intelligence tools.
intelligence.register(mcp)


# ── Entrypoint ─────────────────────────────────────────────────────────────────

def main() -> None:
    Config.validate()
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
