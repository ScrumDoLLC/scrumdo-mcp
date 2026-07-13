# scrumdo-mcp — AI Cockpit Bridge Spec

Status: Slices 1–3 core shipped (v0.3.2, 101 tools); Slice 3b remaining
(confirm_token handshake + multi-doc `doc_type` on get/set/patch).
Date: 2026-07-13
Baseline: `scrumdo-mcp` v0.2.13, 93 tools, branch `feat/ai-cockpit-bridge`.

Derived from, and the execution-ready complement to:

- `MassSense/docs/SCRUMDO_MCP_AI_COCKPIT_WRITE_SPEC.md` (product contract, authoritative)
- `MassSense/docs/AI_COCKPIT_AGENT_COMMAND_GOVERNANCE_SPEC.md` (command catalog + invoke)
- `MassSense/docs/UNIFIED_COCKPIT_TIMELINE_SPEC.md` (timeline is FE-only over the cockpit payload)
- `MassSense/docs/card-cockpit-v2/*` (multi-doc specs, outcomes, phase-5 MCP notes)

The backend route contract in §3 was **verified directly against `apps/api_v4`** (not assumed
from an endpoint list) on 2026-07-13.

---

## 1. Goal

Make `scrumdo-mcp` a first-class **Card AI Cockpit bridge** so Codex / Claude Code / Cursor can
read cockpit context and drive the same governed card artifacts the browser cockpit uses —
under the same governance, permissions, and human-approval gates. No new business-logic fork:
every MCP tool wraps an existing DRF route.

The MCP exposes **typed tools, not raw slash strings** (chat/slash is a browser-UX concern).
"Command governance" for MCP means the tool catalog reflects the server's effective policy and
every write re-checks policy server-side.

## 2. Baseline — what already exists (do not rebuild)

v0.2.13 already ships: cards, tasks, comments, fields, members, search, blockers, attachments,
webhooks, time, activity, `agents` (identity), `spec` (get/set/patch/history), `spec_proposals`
(generate/list/accept/reject/request-changes/revise, with `instructions` + `card_fields`
spotlight), `github` links, `agent_runs` (start/cancel/approve/get/list/progress), `loops`
(governed loops + verify + skills), `intelligence` (drift/verify/complexity/forecast).

Client (`client.py`) resolves `ON-914` → story id and already propagates `X-Spryng-Agent-Run`
and `X-Spryng-Loop` when the corresponding env vars are set.

## 3. Confirmed backend contract (verified 2026-07-13)

Project scope = `…/organizations/<org>/projects/<project>/…` (`Config.project_url`).
Org scope = `…/organizations/<org>/…` (`Config.org_url`).

### 3.1 Read (cockpit-shaped)

| Capability | Route | Handler | Notes |
|---|---|---|---|
| **Cockpit context** | `GET stories/<id>/ai-cockpit/` | `StoryAiCockpitHandler` | Single aggregate: `spec`, `messages` (≤50), `configured_agents[]` (readiness + `can_chat/can_start_loop/can_execute_spec/can_propose_spec/can_verify_result`), `runtimes[]`, `agent_profiles.managed[]`, `permissions`, `available_actions`, `loops`, `agent_runs`. Requires `can_read`. |
| **Command catalog** | `GET stories/<id>/agent-commands/?agent_profile_id=<id>` | `StoryAgentCommandsHandler` | `{commands[], selected_agent_profile_id, policy_source{governance_profile,version}}`; each cmd: `id,group,label,dispatch_kind,risk_level,requires_human,enabled,reason`. Story-scoped only (no org-level catalog). |
| **Agent-profile manager** | `GET stories/<id>/ai-cockpit/agent-profiles/` | `StoryAgentProfilesManagedHandler` | Composed identity+runtime+readiness (`ready/needs_setup/blocked/disabled`). |
| **Whoami** | `GET agents/whoami/` | `AgentWhoAmIHandler` | Agent identity + `scopes,current_run_id`. **404 if the caller is not an agent** (org/human token). |

### 3.2 Write / dispatch (all map to real routes)

| Capability | Route | Human-only? |
|---|---|---|
| Send cockpit chat (`kind='chat'`) | `POST stories/<id>/ai-cockpit/` `{action:"message", body, agent_profile_id, media_ids?, scope_ref?}` → `{message, chat_run_id}` | **Yes** (409 `chat_in_progress` if a run is active) |
| Draft spec from card (doc-type aware) | `POST stories/<id>/ai-cockpit/` `{action:"draft_spec_from_card", doc_type, instructions, card_fields?, context_selection?}` → `{run, proposal, runner_readiness}` | **Yes** |
| Proposal generate/accept/reject/revise | `stories/<id>/spec-proposals/…` | **Yes** (accept from MCP needs `confirm_token`, see §4.2) |
| Command invoke | `POST stories/<id>/agent-commands/invoke/` `{command_id, args?, agent_profile_id?}` | per-command `requires_human` |
| Start run | `POST agent-runs/` `{card_ref, agent_id?, instructions?, doc_type?}` | **Yes** |
| Report progress | `POST agent-runs/<id>/progress/` | agent (run's own) |
| Approve plan / accept proof / replan / verify | `POST agent-runs/<id>/{approve,accept-proof,replan,verify}/` `{review_session_id?}` | **Yes** |
| Paste plan / paste spec draft (no-runner) | `POST agent-runs/<id>/{paste-plan,paste-spec-draft}/` | **Yes** |
| Materialize tasks / promote research / open PR | `POST agent-runs/<id>/{materialize-tasks,promote-research,open-pr}/` | mostly **Yes** |
| Execute spec-derived task | `POST agent-runs/execute-task/` `{task_id, agent_id?}` | **Yes** (Todo→Doing→Reviewing) |
| Whole-spec execution runs | `stories/<id>/spec/executions/…` | — |
| Loops start/steer/state/steps/evidence | `agent-loops/…` | start/steer **Yes**; steps/evidence agent |
| Governed review sessions | `stories/<id>/review-sessions/…` | most **Yes**; gated on `governed_review_sessions_enabled` → **402** when off |

### 3.3 MCP Workbench (human decision surface — already exists)

`apps/mcp_workbench/`, org-scoped: `mcp/whoami/`, `mcp-tokens/`, `decision-inbox/`,
`workbench/proposals/<uuid>/{diff,comments,request-changes,understood,preview-decision}/`.
This is the human-side gate/decision-inbox for MCP-originated proposals.

## 4. Design decisions

### 4.1 Human-principal client mode (critical)

`assert_human_actor` treats **any request carrying `X-Spryng-Agent-Run` as an agent** and 403s.
The human-only cockpit actions (chat, draft-from-card, execute-task, loop start/steer, proposal
accept/reject, review dispositions) therefore must run on a **non-run-scoped token with the run
header suppressed**.

→ `SpryngClient` gains `human_principal: bool = False`. When `True`, the client omits
`X-Spryng-Agent-Run` (and `X-Spryng-Loop`) regardless of env. Human-only tools construct their
client with `human_principal=True`. Read tools are unaffected (reads accept either token).

### 4.2 Proposal accept `confirm_token`

`accept_spec_proposal` from an MCP session requires a `confirm_token` (`_require_mcp_confirm_token`)
obtained through the MCP Workbench gate (`workbench/proposals/<uuid>/preview-decision/` →
`understood/`). Slice 3 wires the handshake and exposes a minimal `decision_inbox` read.

### 4.3 Write attribution (Slice 2)

Every write additionally sends `source=mcp`, `client_name`/`client_version`
(`SCRUMDO_CLIENT_NAME` env, default `"mcp"`), and a per-call `request_id`. Confirm the backend
accepts a `X-Spryng-Source` header / `evidence.source`; if not, add a header the API can ignore.

### 4.4 Compact context

`get_card_cockpit_context` passes through the aggregate but supports an `include` selector and
**omits `messages` by default** (potentially large); always returns `card_ref` + `story_id`
refs so the caller can drill into the narrow tools.

## 5. Slice 1 — Context & discovery (read-only; no backend change)

New module `spryng_mcp/tools/cockpit.py`:

- **`get_card_cockpit_context(card_ref, include=None)`** → `GET stories/<id>/ai-cockpit/`.
  `include` = list of top-level sections or `"all"`. Default = compact set
  (`spec, permissions, available_actions, configured_agents, runtimes, loops, agent_runs`),
  `messages`/`agent_profiles` only on request. Returns `{card_ref, story_id, …sections}`.
- **`get_effective_governance(card_ref, agent_profile_id=None)`** →
  `GET stories/<id>/agent-commands/?agent_profile_id=`. Returns the catalog verbatim
  (`commands`, `selected_agent_profile_id`, `policy_source`). `card_ref` is required (the
  catalog is story-scoped).
- **`get_mcp_capabilities()`** → static+config discovery: base_url/org/project, token/run/loop
  context, and the installed tool catalog grouped by capability. Network-free (a reliable smoke
  + install aid). Per-card enforcement is delegated to `get_effective_governance`.

Harden **`get_agent_identity()`** (`agents.py`):

- Tolerate the whoami **404** (org/human token) → return `{is_agent: False,
  token_mode: "org_or_human", …}` instead of raising.
- Add `token_mode` (`run_scoped` if `SPRYNG_AGENT_RUN_ID` else `agent` if whoami succeeds else
  `org_or_human`), `organization`, `project`, `run_context`, and `writes_permitted` (best-effort).

Register in `server.py`; extend the instructions block ("call `get_card_cockpit_context` first
to understand a card in one shot").

**DoD:** respx tests for all four tools (incl. the whoami-404 path + `include` selection);
README tool table + `AI_PLATFORM_LOG.md` updated; version `0.2.13 → 0.3.0`; `pytest` green.

## 6. Slice 2 — Human-principal writes + attribution + multi-doc + chat/draft

- `SpryngClient(human_principal=True)` mode (§4.1) + `SCRUMDO_CLIENT_NAME`/source attribution (§4.3).
- `send_cockpit_chat(card_ref, message, agent_profile_id=None)` → `POST …/ai-cockpit/` message.
- `draft_spec_from_card(card_ref, doc_type="requirements", instructions="", card_fields=None,
  agent_profile_id=None)` → `POST …/ai-cockpit/` draft action (doc-type-aware).
- Multi-doc spec ergonomics: `doc_type` on `get/set/patch_card_spec`;
  `list_card_spec_documents(card_ref)`; stale-write guard.
- Harden existing run/spec writes to run as human-principal where the backend requires it.

## 7. Slice 3 — Outcomes / QA / evidence / execute-task / gated accept

- Typed wrappers: `accept_proof(run_id, review_session_id?)`, `request_agent_replan(run_id, reason)`,
  `report_agent_verification(...)`, `report_agent_outcome(...)`, `submit_outcome_for_review(...)`.
- `execute_task(card_ref, task_id, agent_id=None)` → `POST agent-runs/execute-task/`.
- MCP-Workbench `confirm_token` handshake for `accept_spec_proposal` (§4.2) +
  `get_decision_inbox()` read.
- Optional (feature-gated): review-session annotate/resolve tools.

## 8. Cross-cutting rules (write-spec §9, §12)

Writes: explicit `change_summary`/action summary, return the canonical object or timeline id,
idempotent where plausible, stable structured error codes, server-side governance re-check, no raw
model field names. Reads: redact secrets, respect permissions, stable refs, compact.

## 9. Test strategy

respx-mocked (no network), following `tests/test_spec_proposal_tools.py`: register the module on a
`FastMCP`, pull the tool fn, mock the card-resolution GET + the endpoint, assert request shape +
response handling. Add auth-mode (agent vs human token), whoami-404, governance-denied, and
idempotency cases.

## 10. Open decisions

1. Scope beyond Slice 1 (chat/invoke/review = Tier 2) — confirm before Slice 2.
2. `source=mcp` header/evidence acceptance — confirm backend or add ignore-safe header.
3. `restore_spec_version` — only if product approves restore.

## 11. Version plan

Slice 1 → `0.3.0` (new read/discovery surface). Slices 2–3 → `0.3.x`.
