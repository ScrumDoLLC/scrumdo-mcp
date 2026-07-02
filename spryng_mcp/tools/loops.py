"""Governed Agent Loops — MCP tools (GOVERNED_AGENT_LOOPS_SPEC §4).

Thin wrappers over the monolith's `agent-loops/` REST surface so an orchestrator
agent (Claude Code, Cursor, …) can start, observe, and steer a governed loop
that treats the ScrumDo card as durable loop state.

Every outbound write already carries `X-Spryng-Loop` when `SPRYNG_LOOP_ID` is
set in the agent's env (see client.py), so card mutations made while a loop runs
are attributable to it.
"""
from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from ..client import SpryngClient
from ..config import Config


def _resolve_loop_id(loop_id: int | None) -> int:
    """The explicit loop_id, else the active loop from the SPRYNG_LOOP_ID env
    (set when an agent runs inside a loop). So in-loop reporting tools — and the
    seeded maker prompts that call them without an id — just work.
    """
    if loop_id is not None:
        return loop_id
    env_id = (Config.loop_id or "").strip()
    if env_id:
        return int(env_id)
    raise ValueError(
        "loop_id is required (or set SPRYNG_LOOP_ID for the active loop)")


def _verifier_req(value: str) -> str:
    """Map a friendly verifier_agent ('different'/'same'/'human') to the API's
    verifier_requirement enum. Pass an already-canonical value straight through.
    """
    v = (value or "").strip().lower()
    return {
        "different": "different_agent", "different_agent": "different_agent",
        "same": "same_agent", "same_agent": "same_agent",
        "human": "human_only", "human_only": "human_only",
        "claude": "different_agent",  # a named verifier ⇒ a different agent
    }.get(v, value)


def register(mcp: FastMCP) -> None:

    @mcp.tool()
    async def start_loop(
        card_ref: str,
        goal: str = "",
        trust_level: str | None = None,
        max_iterations: int | None = None,
        max_cost_cents: int | None = None,
        verifier_requirement: str | None = None,
        maker_agent_id: int | None = None,
        verifier_agent_id: int | None = None,
    ) -> dict:
        """Start a governed, iterate-until-green loop on a card.

        The platform orchestrates maker → verify → fix until a passing
        verification (the never-trust-done exit invariant) or a bound is hit.
        Only a human principal may start a loop; an agent run-token is rejected.

        Args:
            card_ref: 'ON-914'-style card reference.
            goal: free-text goal (the loop's `/goal`).
            trust_level: 'L1' (report-only) | 'L2' (assisted) | 'L3' (governed).
            max_iterations: hard turn cap (default 12).
            max_cost_cents: loop-level spend ceiling (cents).
            verifier_requirement: 'same_agent' | 'different_agent' | 'human_only'.
            maker_agent_id / verifier_agent_id: explicit agent user ids.
        """
        body: dict = {"card_ref": card_ref, "goal": goal}
        if trust_level is not None:
            body["trust_level"] = trust_level
        if max_iterations is not None:
            body["max_iterations"] = max_iterations
        if max_cost_cents is not None:
            body["max_cost_cents"] = max_cost_cents
        if verifier_requirement is not None:
            body["verifier_requirement"] = verifier_requirement
        if maker_agent_id is not None:
            body["maker_agent_id"] = maker_agent_id
        if verifier_agent_id is not None:
            body["verifier_agent_id"] = verifier_agent_id
        async with SpryngClient() as c:
            return await c.post(Config.org_url("agent-loops/"), body)

    @mcp.tool()
    async def get_loop_status(loop_id: int) -> dict:
        """Fetch a loop's full status: state, iteration, last verdict, the
        `auto_loop` block, its runs + event timeline, evidence-story status, and
        the accumulated cost."""
        async with SpryngClient() as c:
            return await c.get(Config.org_url(f"agent-loops/{loop_id}/"))

    @mcp.tool()
    async def list_active_loops(card_ref: str | None = None) -> list[dict]:
        """List active governed loops (optionally scoped to one card)."""
        params: dict = {"state": "active"}
        if card_ref is not None:
            async with SpryngClient() as c:
                card = await c.get_card(card_ref)
                params["card_id"] = card.get("id")
                return await c.get(Config.org_url("agent-loops/"), **params)
        async with SpryngClient() as c:
            return await c.get(Config.org_url("agent-loops/"), **params)

    @mcp.tool()
    async def pause_loop(loop_id: int) -> dict:
        """Pause a loop — stop dispatching new runs (an in-flight run finishes;
        the loop only advances again on resume)."""
        async with SpryngClient() as c:
            return await c.post(
                Config.org_url(f"agent-loops/{loop_id}/pause/"), {})

    @mcp.tool()
    async def resume_loop(loop_id: int) -> dict:
        """Resume a paused or escalated loop — re-enter the driver."""
        async with SpryngClient() as c:
            return await c.post(
                Config.org_url(f"agent-loops/{loop_id}/resume/"), {})

    @mcp.tool()
    async def cancel_loop(loop_id: int, reason: str = "") -> dict:
        """Cancel a loop and its in-flight run."""
        async with SpryngClient() as c:
            return await c.post(
                Config.org_url(f"agent-loops/{loop_id}/cancel/"),
                {"reason": reason})

    @mcp.tool()
    async def get_loop_state(loop_id: int) -> dict:
        """Read a loop's durable cross-run memory (LoopState §2.12):
        previous_outcomes, deltas, learned_patterns, accumulated_evidence."""
        async with SpryngClient() as c:
            return await c.get(Config.org_url(f"agent-loops/{loop_id}/state/"))

    @mcp.tool()
    async def update_loop_state(loop_id: int, patch: dict) -> dict:
        """Merge a patch into the loop's LoopState (append-or-set: list keys
        extend, others overwrite). Use it so a later iteration's maker sees what
        earlier iterations learned/failed, instead of re-deriving it."""
        async with SpryngClient() as c:
            return await c.patch(
                Config.org_url(f"agent-loops/{loop_id}/state/"),
                {"patch": patch})

    @mcp.tool()
    async def get_verification_status(loop_id: int | None = None) -> dict:
        """The loop's verification snapshot: last verdict, the card's qa_status,
        whether the stop condition is met, and the per-clause breakdown.

        loop_id defaults to the active loop (SPRYNG_LOOP_ID) when omitted."""
        lid = _resolve_loop_id(loop_id)
        async with SpryngClient() as c:
            return await c.get(
                Config.org_url(f"agent-loops/{lid}/verification/"))

    @mcp.tool()
    async def start_verification_loop(
        card_ref: str, profile: str | None = None, goal: str = "",
        max_turns: int | None = None, verifier_agent: str | None = None,
        proof_requirements: list[str] | None = None,
    ) -> dict:
        """Start a governed verification loop on a card — by a VerificationProfile
        slug, inline config, or both. Verification-first alias of start_loop.

        Args:
            profile: a VerificationProfile slug (e.g. 'high-governance-maker-
                checker', 'test-driven-only', 'fast-exploration', 'human-heavy')
                — sets the verifier requirement, proof, and bounds. Inline args
                below override the profile.
            goal: free-text loop goal.
            max_turns: hard iteration cap (default 12).
            verifier_agent: 'different' (must differ from maker), 'same', or
                'human'. A named model (e.g. 'claude') implies 'different'.
            proof_requirements: e.g. ['tests', 'evidence_attach', 'spec_match'].
        """
        body: dict = {"card_ref": card_ref, "goal": goal}
        if profile:
            body["verification_profile"] = profile
        if max_turns is not None:
            body["max_iterations"] = max_turns
        if verifier_agent:
            body["verifier_requirement"] = _verifier_req(verifier_agent)
        if proof_requirements is not None:
            body["proof_requirements"] = proof_requirements
        async with SpryngClient() as c:
            return await c.post(Config.org_url("agent-loops/"), body)

    @mcp.tool()
    async def log_loop_step(
        action: str, detail: str = "", result: str = "",
        iteration: int | None = None, loop_id: int | None = None,
    ) -> dict:
        """Record a narrative step on a loop's timeline so the loop's reasoning is
        auditable on the card.

        Args:
            action: 'make_change' | 'test_run' | 'verify' | …
            detail: free-text narrative.
            result: 'PASS' | 'FAIL' | 'PARTIAL' — the step outcome (observability).
            iteration: loop turn number (defaults to the loop's current).
            loop_id: defaults to the active loop (SPRYNG_LOOP_ID) when omitted.
        """
        lid = _resolve_loop_id(loop_id)
        body: dict = {"action": action, "detail": detail}
        if result:
            body["result"] = result
        if iteration is not None:
            body["iteration"] = iteration
        async with SpryngClient() as c:
            return await c.post(
                Config.org_url(f"agent-loops/{lid}/steps/"), body)

    @mcp.tool()
    async def attach_evidence(artifacts: dict, loop_id: int | None = None) -> dict:
        """Attach durable proof artifacts (test output, screenshots, diffs, logs)
        to a loop's accumulated evidence.

        loop_id defaults to the active loop (SPRYNG_LOOP_ID) when omitted."""
        lid = _resolve_loop_id(loop_id)
        async with SpryngClient() as c:
            return await c.post(
                Config.org_url(f"agent-loops/{lid}/evidence/"),
                {"artifacts": artifacts})

    @mcp.tool()
    async def route_to_agent(loop_id: int, agent_id: int, task_type: str) -> dict:
        """Delegate a loop task type ('plan'|'implement'|'verify'|'integrate') to
        a specific agent — sub-agent routing for an orchestrator."""
        async with SpryngClient() as c:
            return await c.post(
                Config.org_url(f"agent-loops/{loop_id}/route/"),
                {"agent_id": agent_id, "task_type": task_type})

    @mcp.tool()
    async def verify_card(card_ref: str) -> dict:
        """Run a spec-verification pass on a card (an independent agent reviews
        the accepted spec's quality/testability and posts a report).

        UNIFIED AGENT: any agent can verify — there is no QA-only role. The
        server picks an active agent; separation-of-duties is enforced by the
        card's verifier_policy (a different agent than the implementer by
        default)."""
        async with SpryngClient() as c:
            return await c.post(
                Config.org_url("agent-runs/verify-spec/"), {"card_ref": card_ref})

    @mcp.tool()
    async def run_verifier(
        card_ref: str, maker_changes: str = "", verifier_prompt: str = "",
    ) -> dict:
        """Run an INDEPENDENT verifier against the card's accepted spec.

        Dispatches an adversarial Verification Specialist (a DIFFERENT agent than
        the maker — never self-verification) to review the maker's changes
        against the accepted spec + every evidence story, then post a QA report
        with a structured VERDICT. Call this after a maker edit (e.g. Grok or
        Codex) to prove the work — the maker must never self-verify.

        UNIFIED AGENT: any agent can verify (no QA-only role); the server's
        verifier_policy enforces that it differs from the implementer.

        Args:
            card_ref: 'ON-914'-style card reference.
            maker_changes: diff summary or file list the maker produced (captured
                on the run so the verifier sees exactly what changed).
            verifier_prompt: optional override of the default Verification
                Specialist prompt (adversarial mode).
        """
        body: dict = {"card_ref": card_ref}
        if maker_changes:
            body["maker_changes"] = maker_changes
        if verifier_prompt:
            body["verifier_prompt"] = verifier_prompt
        async with SpryngClient() as c:
            return await c.post(
                Config.org_url("agent-runs/verify-spec/"), body)

    @mcp.tool()
    async def list_skills(category: str | None = None) -> list[dict]:
        """List reusable Skill packs (governed Markdown context) available to
        this org — published org skills + global ones. Filter by category."""
        params: dict = {"published": "true"}
        if category:
            params["category"] = category
        async with SpryngClient() as c:
            return await c.get(Config.org_url("skills/"), **params)

    @mcp.tool()
    async def load_skill(skill_id: int) -> dict:
        """Load a Skill's approved content (Markdown + config) to inject into the
        agent's context — e.g. company testing standards, a security checklist."""
        async with SpryngClient() as c:
            return await c.get(Config.org_url(f"skills/{skill_id}/load/"))
