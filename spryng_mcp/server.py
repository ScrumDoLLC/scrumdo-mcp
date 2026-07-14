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
    attachments,
    blockers,
    boards,
    cards,
    cockpit,
    commands,
    comments,
    fields,
    github,
    intelligence,
    loops,
    members,
    memory,
    notifications,
    search,
    spec,
    spec_proposals,
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
  • Upload attachments to cards via add_attachment (WRITE ONLY; this MCP
    cannot list, read, or download attachments)

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

Card AI Cockpit bridge:
  To understand a card in one shot, call get_card_cockpit_context(card_ref) —
  it returns the cockpit's own aggregate (spec, configured agents + runtimes with
  per-card readiness, your permissions, available actions, active loops, and
  recent runs) rather than making you stitch five narrow reads together. Before
  attempting a governed write, call get_effective_governance(card_ref) to see the
  server-authoritative command policy (what's enabled/disabled and why, risk, and
  whether it's human-only). get_mcp_capabilities() lists the whole tool surface +
  connection context (a network-free smoke check).
  To talk to a board agent on a card, use send_cockpit_chat(card_ref, message,
  agent_profile_id) — its reply posts back into the cockpit timeline. To have an
  agent draft a spec document, use draft_spec_from_card(card_ref, doc_type=...).
  Both are HUMAN-ONLY: they run as a human principal (the run header is dropped),
  so a run-scoped agent token is refused — use the agent-run tools to work a card
  as an agent. The agent_profile_id these take is the `id` of a
  get_card_cockpit_context configured_agents[] entry (filter by can_chat /
  can_propose_spec); a chat reply lands in the card's `messages`
  (get_card_cockpit_context(..., include=["messages"])).
  Every governed slash-command in the catalog (get_effective_governance) is
  reachable: invoke_cockpit_command(card_ref, command_id, args?) runs the same
  governed dispatcher the cockpit uses (executes loop.status/pause/resume +
  skill.<slug>; governance-validates the rest). Typed tools cover the executable
  actions — research_card, run_card_tests, tasks_from_spec, get_card_memory,
  clear_card_memory — alongside draft_spec_from_card / accept_spec_proposal /
  start_loop / start_agent_run / run_verifier already present.

Spec proposals — the reviewed alternative to editing the spec directly:
  generate_spec_proposal / list_spec_proposals / accept_spec_proposal /
  reject_spec_proposal / request_spec_proposal_changes / revise_spec_proposal.
  ALL SIX are human-only — the backend rejects an agent-flagged caller with
  403 on every one of them, including generate (an agent drafts when
  dispatched by a human's generate call; it never self-triggers drafting).
  If you are an autonomous agent, do not call these — use get_card_spec /
  set_card_spec / patch_card_spec instead, which are the agent-writable path
  (subject to the frontmatter whitelist in step 3 below). accept_spec_proposal
  can trigger an execution run if the room has a runnable profile — it is a
  real "make this official" action, not a passive review note.
  MCP decide gate: from an MCP session the backend requires a confirm_token to
  accept/reject/request-changes on a proposal. Flow: get_decision_inbox() →
  preview_spec_decision(proposal_id, action) to mint the token (bound to the
  proposal's current version, 10-min TTL) → accept_spec_proposal(...,
  confirm_token=<token>).

Shared cognition (slice 10) — the board's governed memory:
  - Starting work on a card? Call get_handoff_brief(card_ref) FIRST —
    recent events, new constraints/decisions, and the live blackboard,
    so you don't repeat what another actor already did.
  - Know the rules: get_room_context() (the room library every card
    inherits) and get_card_memory(card_ref) (this card's saved context).
  - Learned or tried something? post_blackboard_note(card_ref, body,
    kind) — ALLOWED for agents, ungated. Notes expire in 7 days and are
    never durable unless a human promotes them. Use kind='gotcha' for
    traps, 'fact' for findings.
  - HUMAN-only (backend 403s agent tokens; do not retry on denial):
    promote_blackboard_note, add_card_memory, add_room_context,
    curate_room_context, run_distiller, resolve_memory_dispute.
  - list_memory_disputes shows contradicting entries; while a dispute is
    open none of its members reach any agent.

Notifications — the in-app message center for YOUR identity:
  - Poll notification_counts() / list_notifications(status='unread')
    between work units to catch "plan approved" / "changes requested"
    without re-fetching whole cards.
  - After acting on a message, mark_notification(id, 'acknowledge') so
    humans watching the queue see it handled.

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
memory.register(mcp)
notifications.register(mcp)
search.register(mcp)
activity.register(mcp)
attachments.register(mcp)
webhooks.register(mcp)
time_tracking.register(mcp)
# Phase A (BOARD_AI_AGENTS_UNIFIED_SPEC §A.5) — agent identity tools.
agents.register(mcp)
# Phase B (BOARD_AI_AGENTS_UNIFIED_SPEC §5.6) — card spec tools.
spec.register(mcp)
# Spec proposal lifecycle: generate/list/accept/reject/request-changes/revise.
spec_proposals.register(mcp)
# Phase D (BOARD_AI_AGENTS_UNIFIED_SPEC §D.4) — GitHub link tools.
github.register(mcp)
# Phase E (BOARD_AI_AGENTS_UNIFIED_SPEC §E.7) — AgentRun lifecycle tools.
agent_runs.register(mcp)
loops.register(mcp)
# Phase G (BOARD_AI_AGENTS_UNIFIED_SPEC §10) — AI intelligence tools.
intelligence.register(mcp)
# Card AI Cockpit bridge (AI_COCKPIT_BRIDGE_SPEC.md Slice 1) — cockpit-shaped
# read + governance/capability discovery.
cockpit.register(mcp)
# Governed cockpit command catalog coverage — generic invoke + typed tools for
# research / test.run / tasks / memory so every catalog command is reachable.
commands.register(mcp)


# ── Entrypoint ─────────────────────────────────────────────────────────────────

def main() -> None:
    Config.validate()
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
