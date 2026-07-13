# scrumdo-mcp — AI Platform Log

Per BOARD_AI_AGENTS_UNIFIED_SPEC.md §16.

## Status

All phase MCP surfaces shipped. Tool count grew from 41 → 62:
- Phase A: +2 (`get_agent_identity`, `list_agent_accounts`)
- Phase B: +3 (`get_card_spec`, `set_card_spec`, `patch_card_spec`)
- Phase C: +1 (`get_spec_history`)
- Phase D: +5 (`list_card_github_links`, `link_github_pr`,
  `link_github_issue`, `link_github_commit`, `get_github_repos`)
- Phase E: +6 (`start_agent_run`, `cancel_agent_run`,
  `approve_agent_plan`, `get_agent_run`, `list_agent_runs`,
  `report_agent_progress`)
- Phase G: +4 (`check_spec_drift`, `verify_behavior_contract`,
  `get_spec_complexity`, `get_velocity_forecast`)
- Phase F + H: no new MCP tools (enforced server-side).

## Active Phase

Phase B. Backwards-compatible with v0.1.x (all 41 prior tools retain
signatures per spec §13.3).

## Decision Log

- **Q-X2 (exact pins):** all runtime deps now pinned `==X.Y.Z` in
  `pyproject.toml`. Major bumps will require two reviewer approvals
  per spec §3a.3.
- **Spec divergence:** spec §13.1 anchors the version at v0.2.9 with
  45 tools as the baseline. The actual repo is v0.1.1 with 41 tools.
  We added the Phase A + B tools on top of v0.1.1, landing at 46.
  Recorded in Spec Deviations.

## Blockers

- The `get_card_spec(card_ref, fmt='json'|'yaml')` round-trip uses a
  PATCH-with-empty-body trick to convert formats server-side. Cleaner
  would be `?fmt=` on GET; revisit if backend ergonomics warrant.

## Completed Phases

### Phase 0

- `Config.agent_run_id` reads `SPRYNG_AGENT_RUN_ID` /
  `SCRUMDO_AGENT_RUN_ID`.
- `SpryngClient.__init__(*, agent_run_id=None)` accepts an explicit
  run id; falls back to the env var. When set, attaches
  `X-Spryng-Agent-Run` to every outbound request.
- `SpryngClient.agent_run_id` property exposes the active run.
- Exact pins on all runtime deps + dev deps.
- Tests: `tests/test_run_context_header.py` covers the three header
  scenarios from spec §3a.5 #4.

### Phase A

- `spryng_mcp/tools/agents.py` — `get_agent_identity()` and
  `list_agent_accounts(active_only=True)`.
- `server.py` instructions block extended per spec §13.4: agents are
  told to call `get_agent_identity()` first and propagate
  `current_run_id` on writes.
- Backend calls `/organizations/<org>/agents/whoami/` and
  `/organizations/<org>/agents/`.

### Phase B

- `spryng_mcp/tools/spec.py` — `get_card_spec`, `set_card_spec`,
  `patch_card_spec`. Tools resolve `card_ref` via the existing
  `SpryngClient._resolve_card_id` cache.

### Phase C

- `spryng_mcp/tools/spec.py` (same module) — `get_spec_history(card_ref,
  limit, source, changed_by, agent_run_id, include_archived,
  include_content)`. Filters mirror the REST endpoint exactly.
- No new SDK pins; the existing `httpx` exact pin covers the new
  endpoint calls.

### Phase D

- `spryng_mcp/tools/github.py` — 5 link tools (PR / issue / commit
  attach + list + repos). Tools use the existing
  `_resolve_card_id` cache.

### Phase E

- `spryng_mcp/tools/agent_runs.py` — 6 lifecycle tools.
  `report_agent_progress` is the ONLY way for an agent runtime to
  drive the state machine (spec §13.4 #7).

### Phase G

- `spryng_mcp/tools/intelligence.py` — 4 tools. `get_spec_complexity`
  reads from the existing `/spec/` endpoint (the score lives on the
  StorySpec row). The other three POST to dedicated AI endpoints.

### Post-spec punch list

- `.pre-commit-config.yaml` shipped; references
  `MassSense/scripts/check_exact_pins.py` so the exact-pin policy
  (Q-X2) is single-sourced across repos.
- No new MCP tools added in this pass; surface stays at 62 tools.

### Second-pass gap close

- `server.py` instructions block extended with the §13.4 items 5-7
  guidance: use `patch_card_spec` for single-field updates, call
  `link_github_pr` instead of writing `commit_links` directly,
  use `report_agent_progress` as the only state-mover.
- Whitelisted writable frontmatter keys listed inline (matches the
  Phase F §F.2 ACL).
- Backend now strictly validates the `X-Spryng-Agent-Run` header per
  §13.2; the client-side propagation already complied.
- No tools added; surface stays at 62.

## SDK Bumps

- 2026-05-27 — initial exact pins:
  - `mcp[cli]==1.3.0`
  - `httpx==0.27.0`
  - `pydantic==2.7.4`
  - `python-dotenv==1.0.1`
  - `PyYAML==6.0.1`
  - dev: `pytest==8.2.2`, `pytest-asyncio==0.23.7`, `respx==0.21.1`

## Spec Deviations

- **Version drift from §13.1:** spec assumes v0.2.9 with 45 tools as
  the v0.3.0 baseline. The actual current shipping version is v0.1.1
  with 41 tools — there's an undocumented 4-tool gap (likely
  milestones/epics that exist in the docs but not the registry).
  Phase A + B add 5 tools, landing at 46. The migration log for the
  v0.3.x cut should reconcile the gap or amend the spec.
- **`patch_card_spec` semantics:** spec §B.6 says the patch shape is
  "JSON merge patch for JSON/YAML or a frontmatter-key dict for MD".
  Implementation accepts a flat dict in both cases since backend's
  PATCH handler reconciles to whatever the current format is. JSON
  merge patch semantics (e.g. null = delete) are NOT yet enforced.

## Card AI Cockpit Bridge — Slice 1 (2026-07-13, v0.3.0)

Per `AI_COCKPIT_BRIDGE_SPEC.md` (this repo), derived from
`MassSense/docs/SCRUMDO_MCP_AI_COCKPIT_WRITE_SPEC.md` + a route map verified
directly against `apps/api_v4` on 2026-07-13.

Slice 1 (read + discovery, no backend change) — new module
`spryng_mcp/tools/cockpit.py`, +3 tools (93 → 96):

- `get_card_cockpit_context(card_ref, include?)` → `GET stories/<id>/ai-cockpit/`
  (`StoryAiCockpitHandler`). The cockpit's own aggregate in one call: spec,
  configured agents + runtimes w/ per-card readiness, permissions, available
  actions, loops, recent runs. Compact by default (drops the ≤50-row `messages`
  + `agent_profiles` blob unless `include=["all"]` or named).
- `get_effective_governance(card_ref, agent_profile_id?)` →
  `GET stories/<id>/agent-commands/` (`StoryAgentCommandsHandler`). The
  server-authoritative command policy (enabled/disabled + reason, risk,
  requires_human, dispatch_kind) + deciding `policy_source`. Story-scoped.
- `get_mcp_capabilities()` — network-free connection context + full tool
  registry enumeration (install/smoke aid). Per-card enforcement delegated to
  `get_effective_governance`.

Hardened `get_agent_identity()` — tolerates the `agents/whoami/` **404** (an
org/human token, not an agent) instead of raising; adds `token_mode`
(`run_scoped`|`agent`|`org_or_human`), `organization`, `project`, `run_context`,
`writes_permitted`. This is load-bearing for the human-only cockpit writes in
Slice 2 (the human-principal client mode, spec §4.1).

Tests: `tests/test_cockpit_tools.py` (7) — default/all/explicit `include`
selection, governance passthrough + param, capabilities registry+config, and
both whoami paths (agent 200 + human 404). Suite 40 passed.

## Card AI Cockpit Bridge — Slice 2 (2026-07-13, v0.3.1)

Human-principal writes + attribution — +2 tools (96 → 98):

- `SpryngClient(human_principal=True)` (`client.py`) suppresses the
  `X-Spryng-Agent-Run` + `X-Spryng-Loop` headers regardless of env, so the
  human-only cockpit actions are attributed to the token's own identity —
  `assert_human_actor` 403s any request carrying the run header (spec §4.1).
- Write attribution (spec §4.3): every request now carries `X-Spryng-Source: mcp`
  + `X-Spryng-Client: <SCRUMDO_CLIENT_NAME>` (default `mcp`) + optional
  `X-Spryng-Client-Version` (ignore-safe if the backend doesn't read them).
- `send_cockpit_chat(card_ref, message, agent_profile_id?, media_ids?, scope_ref?)`
  → `POST stories/<id>/ai-cockpit/` `{action:"message"}` — posts a governed card
  message and dispatches a `kind='chat'` run whose reply lands in the cockpit
  timeline. Human-only. 409 `chat_in_progress` when a run is active.
- `draft_spec_from_card(card_ref, doc_type="requirements", instructions?,
  card_fields?, agent_profile_id?, context_selection?)` → `POST
  stories/<id>/ai-cockpit/` `{action:"draft_spec_from_card"}` — the cockpit's own
  doc-type-aware draft path (returns `{run, proposal, runner_readiness}`).
  Human-only.

Tests: +3 in `tests/test_cockpit_tools.py` — human-principal header suppression
(even with a run id in env) + attribution presence; chat posts as human
(no run header on the write); draft posts action+doc_type+fields. Suite 43 passed.

Remaining (spec §7): Slice 3 typed outcome/QA/evidence wrappers
(`accept_proof`, `request_agent_replan`, `report_agent_verification`,
`report_agent_outcome`) + `execute_task` + multi-doc spec `doc_type` ergonomics +
MCP-Workbench `confirm_token` handshake for proposal accept.

## Sentry Integration (Phase J — SENTRY_INTEGRATION_V3.md)

- **No MCP changes.** Phase J (Sentry) is backend + frontend only; the
  scrumdo-mcp server exposes no Sentry tools in v1. Error data flows
  Sentry → Spryng webhook → `StorySentryIssue`, surfaced in the card
  Errors tab — not through MCP. If a future phase wants agents to read
  their own runtime errors, a `get_card_errors` MCP tool over the
  `observability/stories/<id>/sentry-issues` endpoint would be the
  natural addition (deferred; not in V3 scope).

## Security Scanning Integration (Phase L — SECURITY_SCANNING_INTEGRATION_V2.md)

- **No MCP changes.** Phase L (security scanning) is backend + frontend
  only; the scrumdo-mcp server exposes no security tools in v1. Findings
  flow scanner → webhook/poll → `SecurityFinding`, surfaced in the card
  Security tab. An MCP tool for agents to query/suppress findings is an
  explicit Phase L.b deferral (V2 §5) — natural shape:
  `get_card_security_findings` over `/security/stories/<id>/findings/`.

## Security Scanning — gap remediation (2026-06-08)

Remediated the Phase L v1 per
`SECURITY_SCANNING_GAP_REMEDIATION_SPEC.md`. Highlights: fixed the
blocking tz-aware ingest bug (USE_TZ=False) that prevented any finding
from persisting; added the Snyk project-mapping UI so Snyk findings
resolve to cards/epics; added GHAS webhook replay/rate-limit/body-cap
guards; implemented real Snyk REST poll + reconcile; added the Epic
Security panel (rollup + direct findings), card-tab pagination, and a
stale-connection warning. Backend suite green (62 tests).

## GitHub App (Phase D) — gap remediation (2026-06-08)

Use-case review of `apps/github_app/` per
`GITHUB_APP_GAP_REMEDIATION_SPEC.md`. Fixed two blockers — repos could
never be connected to projects (no API/UI), so every webhook dropped as
`no_connected_projects`; and the install callback had no org-admin
authorization (cross-tenant install binding). Added the repo↔board
connect API + Settings UI, callback authz, correct installation-token
expiry storage + reuse, installation lifecycle webhooks
(suspend/uninstall/repo add-remove), and a post-install redirect.
Backend green: 18 github_app tests (88 with security_scanning).
