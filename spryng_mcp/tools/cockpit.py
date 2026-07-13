"""Card AI Cockpit bridge — read + discovery tools (Slice 1).

See AI_COCKPIT_BRIDGE_SPEC.md. These wrap the cockpit's own aggregate + governance
endpoints so an external agent (Claude Code / Codex / Cursor) can understand a card
and know what it's allowed to do in one or two calls, instead of stitching five
narrow tools together.

All three are READS — safe for any token; no backend changes required. The write /
dispatch tools (chat, draft-from-card, execute-task, typed outcome wrappers) land in
Slices 2-3 and require the human-principal client mode (spec §4.1).
"""
from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from ..client import SpryngClient
from ..config import Config

# Cockpit-context sections returned by default. `messages` (up to 50 chat rows) and
# the full `agent_profiles` manager blob are omitted unless explicitly requested —
# they can be large, and the ranked essentials below answer "what is this card and
# what can I do on it" on their own. Pass include=["all"] for the raw payload.
_DEFAULT_SECTIONS = (
    "spec",
    "permissions",
    "available_actions",
    "configured_agents",
    "runtimes",
    "loops",
    "agent_runs",
)


def register(mcp: FastMCP) -> None:

    @mcp.tool()
    async def get_card_cockpit_context(
        card_ref: str,
        include: list[str] | None = None,
    ) -> dict:
        """Read the Card AI Cockpit's own aggregate for a card in one call.

        This is the cockpit-shaped context the browser console renders: the current
        spec, the agents/runtimes configured for this card (with per-card readiness
        and capability flags — can_chat / can_start_loop / can_execute_spec /
        can_propose_spec / can_verify_result), your permissions, the available
        actions, active loops, and recent agent runs. Prefer this over calling
        get_card / get_card_spec / list_agent_runs / list_active_loops separately.

        Args:
            card_ref: 'ON-914'-style reference.
            include: Which top-level sections to return. Omit for the compact
                default set (spec, permissions, available_actions, configured_agents,
                runtimes, loops, agent_runs). Pass ["all"] for the full payload
                (adds `messages` + `agent_profiles`), or an explicit list of section
                names (e.g. ["spec", "messages"]).

        Returns {card_ref, story_id, <selected sections>}. Use the narrower tools
        (get_card_spec, list_agent_runs, get_loop_status, …) when you need full
        detail on one section.
        """
        async with SpryngClient() as c:
            story_id = await c._resolve_card_id(card_ref)
            payload = await c.get(
                Config.project_url(f"stories/{story_id}/ai-cockpit/"))

        result: dict = {"card_ref": card_ref, "story_id": story_id}
        if not isinstance(payload, dict):
            # Defensive: surface whatever the backend returned rather than crash.
            result["cockpit"] = payload
            return result

        wants = [s.lower() for s in (include or [])]
        if "all" in wants:
            sections = list(payload.keys())
        elif wants:
            sections = wants
        else:
            sections = list(_DEFAULT_SECTIONS)
        for key in sections:
            if key in payload:
                result[key] = payload[key]
        return result

    @mcp.tool()
    async def get_effective_governance(
        card_ref: str,
        agent_profile_id: int | None = None,
    ) -> dict:
        """Read the server-authoritative command/tool policy for a card.

        Returns the same governed catalog the cockpit composer uses: every command
        with its enabled/disabled state, disabled reason, risk level, dispatch kind,
        and requires_human flag, plus the governance profile + version that made the
        decision. Use it to know — before you attempt a write — what this
        token+agent is actually permitted to do on this card. Enforcement is always
        re-checked server-side at invocation, so this is advisory-but-authoritative.

        The catalog is story-scoped: `card_ref` is required (there is no org-level
        catalog endpoint).

        Args:
            card_ref: 'ON-914'-style reference.
            agent_profile_id: Score the catalog for a specific agent profile (an
                agent override may narrow the profile policy, never widen it).
                Omit to score for the default/selected agent.

        Returns {commands: [...], selected_agent_profile_id, policy_source:
        {governance_profile, version}}.
        """
        params: dict = {}
        if agent_profile_id is not None:
            params["agent_profile_id"] = agent_profile_id
        async with SpryngClient() as c:
            story_id = await c._resolve_card_id(card_ref)
            return await c.get(
                Config.project_url(f"stories/{story_id}/agent-commands/"),
                **params,
            )

    @mcp.tool()
    async def get_mcp_capabilities() -> dict:
        """Describe this MCP bridge: connection context + the installed tool surface.

        A network-free discovery + smoke aid — use it to confirm the server is
        configured (org/project/base URL), see whether a run or loop context is
        active, and enumerate every tool this bridge exposes. It does NOT evaluate
        per-card permission: for "what am I allowed to do on THIS card", call
        get_effective_governance(card_ref). To confirm identity + write eligibility,
        call get_agent_identity().

        Returns {config, run_context, tool_count, tools: [{name, summary}, ...]}.
        """
        run_id = (Config.agent_run_id or "").strip()
        loop_id = (Config.loop_id or "").strip()
        token_mode = (
            "run_scoped" if run_id
            else "configured" if Config.token
            else "unconfigured"
        )
        config = {
            "base_url": Config.base_url,
            "organization": Config.org or None,
            "project": Config.project or None,
            "token_present": bool(Config.token),
            "token_mode_hint": token_mode,
        }
        run_context = {
            "agent_run_id": run_id or None,
            "loop_id": loop_id or None,
        }

        tools: list[dict] = []
        try:
            registered = mcp._tool_manager._tools  # type: ignore[attr-defined]
            for tool in registered.values():
                desc = (getattr(tool, "description", "") or "").strip()
                summary = desc.splitlines()[0] if desc else ""
                tools.append({"name": tool.name, "summary": summary})
            tools.sort(key=lambda t: t["name"])
        except Exception:  # pragma: no cover - private API guard
            tools = []

        return {
            "config": config,
            "run_context": run_context,
            "tool_count": len(tools),
            "tools": tools,
            "note": (
                "Per-card permission is enforced server-side; call "
                "get_effective_governance(card_ref) for the governed command policy "
                "and get_agent_identity() for token mode + write eligibility."
            ),
        }
