"""Shared cognition tools — the board's governed memory (slice 10).

Three tiers, from throwaway to permanent:

  BLACKBOARD  — sticky notes on a card. Any actor with write access —
                including agent tokens — may post, ungated, because notes
                expire on their own (7 days) and are never injected as
                durable truth. THIS is where an agent should record what it
                just learned or tried.
  SAVED CONTEXT — durable, human-approved knowledge on a card or for the
                whole room. Agent tokens are rejected by the backend on
                every write here; a human promotes a blackboard note or
                writes an entry directly.
  HANDOFF BRIEF — "since you last touched this": recent events, new
                constraints/decisions, and the live blackboard. Call it
                FIRST when starting work on a card.

Agents: post_blackboard_note early and often; get_handoff_brief before you
start; read get_card_memory / get_room_context to know the standing rules.
Leave promotion, room writes, dispute resolution, and the distiller to
humans — the backend enforces this (403), so don't retry on denial.
"""
from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from ..client import SpryngClient

_KINDS = "constraint | decision | convention | gotcha | fact | preference | playbook"


def register(mcp: FastMCP) -> None:

    # ── Handoff brief ─────────────────────────────────────────────────────

    @mcp.tool()
    async def get_handoff_brief(card_ref: str, since: str | None = None) -> dict:
        """
        "Since you last touched this card" — call FIRST when starting work.

        Returns recent events, constraints and decisions added, and the
        card's live blackboard (working notes), so you don't repeat what
        another agent or human already did.

        Args:
            card_ref: Card reference, e.g. 'ON-914'.
            since:    Optional ISO-8601 datetime; defaults to the last 7 days.
        """
        async with SpryngClient() as c:
            return await c.get_handoff_brief(card_ref, since)

    # ── Blackboard (working notes — agents may write) ────────────────────

    @mcp.tool()
    async def read_blackboard(card_ref: str) -> list[dict]:
        """
        Read the card's live working notes (the blackboard).

        Notes are attributed (human vs agent), typed by kind, and expire on
        their own after 7 days. They are the card's short-term memory —
        check them before redoing work someone else already tried.

        Args:
            card_ref: Card reference, e.g. 'ON-914'.
        """
        async with SpryngClient() as c:
            return await c.read_blackboard(card_ref)

    @mcp.tool()
    async def post_blackboard_note(
        card_ref: str,
        body: str,
        kind: str = "fact",
        confidence: float | None = None,
    ) -> dict:
        """
        Post a working note to the card's blackboard. Agents are ALLOWED
        and encouraged — record what you just learned, tried, or ruled out
        so the next actor (human or agent) doesn't repeat it.

        Notes expire after 7 days and never become durable memory unless a
        human promotes them. Max 2000 chars; secrets are redacted on write.

        Args:
            card_ref:   Card reference, e.g. 'ON-914'.
            body:       The note text (what you learned/tried; be specific).
            kind:       constraint | decision | convention | gotcha | fact |
                        preference | playbook. Use 'gotcha' for traps,
                        'fact' for findings.
            confidence: Optional 0..1 (defaults: 0.6 agent / 0.9 human).
        """
        payload: dict = {"body": body, "kind": kind}
        if confidence is not None:
            payload["confidence"] = confidence
        async with SpryngClient() as c:
            return await c.post_blackboard_note(card_ref, payload)

    @mcp.tool()
    async def promote_blackboard_note(
        card_ref: str,
        entry_id: int,
        scope: str = "card",
        title: str | None = None,
    ) -> dict:
        """
        Promote a blackboard note into durable saved context (HUMAN-only —
        the backend rejects agent tokens with 403; do not retry on denial).

        The note leaves the working set and becomes an approved, injectable
        entry every future run inherits.

        Args:
            card_ref: Card reference, e.g. 'ON-914'.
            entry_id: Blackboard entry id (from read_blackboard).
            scope:    card (default) | room | project.
            title:    Optional title for the new entry (defaults from body).
        """
        body: dict = {"scope": scope}
        if title:
            body["title"] = title
        async with SpryngClient() as c:
            return await c.blackboard_action(card_ref, entry_id, "promote", body)

    @mcp.tool()
    async def drop_blackboard_note(card_ref: str, entry_id: int) -> dict:
        """
        Drop a note from the card's blackboard (it expires immediately).

        Args:
            card_ref: Card reference, e.g. 'ON-914'.
            entry_id: Blackboard entry id (from read_blackboard).
        """
        async with SpryngClient() as c:
            return await c.blackboard_action(card_ref, entry_id, "retire")

    # ── Saved context (durable, human-curated) ────────────────────────────
    # NOTE: reading a card's saved context is get_card_memory in
    # tools/commands.py (the cockpit `/memory status` command) — not
    # duplicated here. This module adds the write/curation side.

    @mcp.tool()
    async def add_card_memory(
        card_ref: str,
        title: str,
        body: str,
        kind: str = "fact",
    ) -> dict:
        """
        Add durable saved context to a card (HUMAN-only — agent tokens get
        403; agents should post_blackboard_note instead and let a human
        promote it).

        Args:
            card_ref: Card reference, e.g. 'ON-914'.
            title:    Short title (max 200 chars).
            body:     What agents should remember about this card.
            kind:     constraint | decision | convention | gotcha | fact |
                      preference | playbook.
        """
        async with SpryngClient() as c:
            return await c.add_card_memory(
                card_ref, {"title": title, "body": body, "kind": kind})

    @mcp.tool()
    async def get_room_context() -> list[dict]:
        """
        List the room/board saved-context library — the standing rules and
        learnings every card's agents inherit (approved entries) plus any
        pending proposals awaiting human review.

        Read this to know the room's rules before working any card here.
        """
        async with SpryngClient() as c:
            return await c.get_room_context()

    @mcp.tool()
    async def add_room_context(
        title: str,
        body: str,
        kind: str = "convention",
        scope: str = "room",
    ) -> dict:
        """
        Add an entry to the room/board library (room MANAGERS only — agent
        tokens and plain members get 403; requires the Team+ plan, else 402).

        Args:
            title: Short title (max 200 chars).
            body:  The rule/learning every card's agents should inherit.
            kind:  constraint | decision | convention | gotcha | fact |
                   preference | playbook.
            scope: room (default) | project (board-wide).
        """
        async with SpryngClient() as c:
            return await c.add_room_context(
                {"title": title, "body": body, "kind": kind, "scope": scope})

    @mcp.tool()
    async def curate_room_context(entry_id: int, action: str) -> dict:
        """
        Approve a pending room-library proposal or retire an entry
        (room MANAGERS only; agent tokens get 403).

        Args:
            entry_id: Saved-context entry id (from get_room_context).
            action:   'approve' (accept a pending proposal into the library)
                      or 'retire' (remove an entry from circulation).
        """
        if action not in ("approve", "retire"):
            raise ValueError("action must be 'approve' or 'retire'")
        async with SpryngClient() as c:
            return await c.room_context_action(entry_id, action)

    @mcp.tool()
    async def run_distiller() -> dict:
        """
        Run the room's memory distiller now (room MANAGERS only). It sweeps
        recent card activity for lessons that appeared on 3+ cards and files
        them as pending room-library proposals with citations.

        Returns per-room reports (proposals created, cards scanned).
        """
        async with SpryngClient() as c:
            return await c.run_distiller()

    # ── Disputes ──────────────────────────────────────────────────────────

    @mcp.tool()
    async def list_memory_disputes() -> list[dict]:
        """
        List open saved-context disputes — pairs/groups of entries that
        contradict each other. While a dispute is open, NONE of its members
        are given to agents. Anyone may look; only humans resolve.
        """
        async with SpryngClient() as c:
            return await c.list_memory_disputes()

    @mcp.tool()
    async def resolve_memory_dispute(
        dispute_id: int,
        winner_id: int | None = None,
    ) -> dict:
        """
        Resolve a saved-context dispute (HUMAN-only — agent tokens get 403).

        Args:
            dispute_id: Dispute id (from list_memory_disputes).
            winner_id:  Entry id to keep — the others are retired and
                        chained for audit. Omit to dismiss the dispute
                        ("both are right"): all members stay live.
        """
        async with SpryngClient() as c:
            return await c.resolve_memory_dispute(dispute_id, winner_id)
