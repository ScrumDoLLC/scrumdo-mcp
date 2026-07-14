"""Governed cockpit commands — full catalog coverage.

The Card AI Cockpit exposes a governed slash-command catalog (see
get_effective_governance): spec.draft/review/approve/reject, loop.*, execute,
verify.run, research, tasks, test.run, deploy.trigger, outcome.*, memory.*,
context, help, and dynamic skill.<slug>. This module makes every one of them
reachable from the MCP:

- `invoke_cockpit_command` is the generic governed dispatcher — it POSTs to the
  same `agent-commands/invoke/` endpoint the cockpit composer uses, so ANY
  catalog command (including future ones and `skill.<slug>`) is invocable with a
  single server-side governance re-check. The backend EXECUTES loop.status/pause/
  resume and skill.<slug> directly; for the other (`cockpit_action`) commands it
  returns `{status:"validated", dispatch_kind}` — run the matching typed tool to
  perform the action (mapping in the docstring below).
- The typed tools here fill the execution gaps the rest of the MCP didn't cover:
  research / test.run / tasks / memory.status / memory.clear.

Command → MCP tool map (so every catalog entry is supported):
  spec.draft      → draft_spec_from_card          loop.start   → start_loop
  spec.review     → verify_card                    loop.status  → get_loop_status
  spec.approve    → accept_spec_proposal           loop.pause   → pause_loop
  spec.reject     → reject_spec_proposal           loop.resume  → resume_loop
  execute         → start_agent_run                verify.run   → run_verifier
  research        → research_card       (here)     tasks        → tasks_from_spec (here)
  test.run        → run_card_tests      (here)     memory.status→ get_card_memory (here)
  memory.clear    → clear_card_memory   (here)     context      → get_card_cockpit_context
  help            → get_effective_governance       skill.<slug> → invoke_cockpit_command
  deploy.trigger  → invoke_cockpit_command (governed; SDLC deployments)
  outcome.review/approve/reject → invoke_cockpit_command (governed)
"""
from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from ..client import SpryngClient
from ..config import Config


def register(mcp: FastMCP) -> None:

    @mcp.tool()
    async def invoke_cockpit_command(
        card_ref: str,
        command_id: str,
        args: dict | None = None,
        agent_profile_id: int | None = None,
    ) -> dict:
        """Invoke ANY governed cockpit command by id (the catalog's own dispatcher).

        Runs the exact server-side governance check the cockpit composer uses, then
        dispatches. The backend EXECUTES `loop.status` / `loop.pause` / `loop.resume`
        and `skill.<slug>` directly (returns the loop state or a queued run); for
        the other commands it returns `{status:"validated", dispatch_kind}` —
        meaning "governance passed, now run the matching typed tool" (see the module
        map). Unknown ids → 400; disabled ids → 403 with the catalog reason.

        Discover valid `command_id`s (and whether each is enabled / human-only) with
        get_effective_governance(card_ref). This is the future-proof path: any
        command the catalog adds is invocable here without a new tool.

        Args:
            card_ref: 'ON-914'-style reference.
            command_id: e.g. 'loop.status', 'skill.qa-checklist', 'spec.draft',
                'deploy.trigger', 'outcome.review'.
            args: Command-specific arguments (e.g. {"slug": "...", "message": "..."}
                for a skill; loop verbs need none).
            agent_profile_id: Score/dispatch for a specific agent profile.

        Returns the invoke result (`status` is 'ok' | 'queued' | 'validated', plus
        `dispatch_kind`, `command_id`, and `run_id` / `loop` when dispatched).
        """
        body: dict = {"command_id": command_id}
        if args:
            body["args"] = args
        if agent_profile_id is not None:
            body["agent_profile_id"] = agent_profile_id
        async with SpryngClient(human_principal=True) as c:
            story_id = await c._resolve_card_id(card_ref)
            return await c.post(
                Config.project_url(
                    f"stories/{story_id}/agent-commands/invoke/"),
                body,
            )

    @mcp.tool()
    async def research_card(
        card_ref: str,
        brief: str,
        agent_id: int | None = None,
    ) -> dict:
        """Start a read-only research pass on a card (the `/research` command).

        Dispatches a `kind='research'` run that investigates the card + web/context
        against your brief and posts findings back — it does not modify the spec or
        code. Human-only (runs as a human principal).

        Args:
            card_ref: 'ON-914'-style reference.
            brief: What to research (the question / scope).
            agent_id: Which agent runs it. Defaults to a suitable agent.
        """
        body: dict = {"card_ref": card_ref, "brief": brief}
        if agent_id is not None:
            body["agent_id"] = agent_id
        async with SpryngClient(human_principal=True) as c:
            return await c.post(Config.org_url("agent-runs/research/"), body)

    @mcp.tool()
    async def run_card_tests(
        card_ref: str,
        test_command: str = "",
        agent_id: int | None = None,
    ) -> dict:
        """Run the card's test suite via an agent (the `/test run` command).

        Dispatches a run that executes the card's tests and reports a verdict.
        Human-only (runs as a human principal).

        Args:
            card_ref: 'ON-914'-style reference.
            test_command: Optional explicit command (e.g. 'pytest -q'); omit to use
                the card/project default.
            agent_id: Which agent runs it. Defaults to a suitable agent.
        """
        body: dict = {"card_ref": card_ref}
        if test_command:
            body["test_command"] = test_command
        if agent_id is not None:
            body["agent_id"] = agent_id
        async with SpryngClient(human_principal=True) as c:
            return await c.post(Config.org_url("agent-runs/test-run/"), body)

    @mcp.tool()
    async def tasks_from_spec(
        card_ref: str,
        spec_ref: str,
        agent_id: int | None = None,
    ) -> dict:
        """Turn a spec document's items into tasks (the `/tasks` command).

        Reads the referenced spec doc and extracts actionable tasks onto the card
        (read-only research engine; it proposes tasks, it doesn't execute them).
        Human-only (runs as a human principal).

        Args:
            card_ref: 'ON-914'-style reference.
            spec_ref: An `@spec://` reference to the doc whose items to extract
                (e.g. '@spec://requirements').
            agent_id: Which agent runs it. Defaults to a suitable agent.
        """
        body: dict = {"card_ref": card_ref, "spec_ref": spec_ref}
        if agent_id is not None:
            body["agent_id"] = agent_id
        async with SpryngClient(human_principal=True) as c:
            return await c.post(
                Config.org_url("agent-runs/tasks-from-spec/"), body)

    @mcp.tool()
    async def get_card_memory(card_ref: str) -> dict:
        """Read a card's agent memory status (the `/memory status` command).

        Returns the memory entries + counts / quota / Cognee status the cockpit's
        Memory tab shows. Read-only.
        """
        async with SpryngClient() as c:
            story_id = await c._resolve_card_id(card_ref)
            return await c.get(
                Config.project_url(f"stories/{story_id}/memory/"))

    @mcp.tool()
    async def clear_card_memory(card_ref: str) -> dict:
        """Retire a card's agent memory (the `/memory clear` command).

        DESTRUCTIVE: clears this card's accumulated agent memory. Human-only (runs
        as a human principal); governance may gate it further.

        Args:
            card_ref: 'ON-914'-style reference.
        """
        async with SpryngClient(human_principal=True) as c:
            story_id = await c._resolve_card_id(card_ref)
            return await c.post(
                Config.project_url(f"stories/{story_id}/memory/clear/"), {})
