# scrumdo-mcp

Connect any MCP-compatible AI tool (Claude Code, Cursor, Windsurf, and others) directly to your [ScrumDo](https://www.scrumdo.com) boards.

Once installed, your AI assistant can read cards, move them, create tasks, post comments, and search across your board — without you copy-pasting anything.

---

## Installation

```bash
pip install scrumdo-mcp
```

---

## Cursor quick-start

**1 — Install**
```bash
# To run the server only:
pip install scrumdo-mcp

# To run tests too:
git clone https://github.com/ScrumDoLLC/scrumdo-mcp.git
cd scrumdo-mcp
pip install -e ".[dev]"
pytest tests/ -v
```

**2 — Get your token**

Log in to ScrumDo → your org → **Settings → API Tokens → Create Token**. Copy it — shown once only.

**3 — Add to `~/.cursor/mcp.json`**

```json
{
  "mcpServers": {
    "scrumdo": {
      "command": "scrumdo-mcp",
      "env": {
        "SCRUMDO_TOKEN": "your-token-here",
        "SCRUMDO_ORG": "your-org-slug",
        "SCRUMDO_PROJECT": "your-default-project-slug"
      }
    }
  }
}
```

Your org and project slugs are the short names in your board URL:
`app.scrumdo.com/`**`my-company`**`/`**`engineering`**

**4 — Restart Cursor**

Done. In any Cursor chat you can now ask:
- *"What cards are in the current sprint?"*
- *"Move ENG-42 to In Review"*
- *"Add a comment to ENG-42: PR is up for review"*
- *"List all cards assigned to me"*

---

## Setup

### Step 1 — Get your token

Log in to ScrumDo → your organization → **Settings → API Tokens → Create Token**.

Copy the token — it is only shown once. This is your personal key; keep it private.

### Step 2 — Configure your AI tool

Find your tool's MCP config file and add the `scrumdo` server entry:

| Tool | Config file |
|------|-------------|
| Claude Code | `~/.claude/claude.json` |
| Cursor | `~/.cursor/mcp.json` |
| Windsurf | `~/.codeium/windsurf/mcp_config.json` |

```json
{
  "mcpServers": {
    "scrumdo": {
      "command": "scrumdo-mcp",
      "env": {
        "SCRUMDO_TOKEN": "your-token-here",
        "SCRUMDO_ORG": "your-org-slug",
        "SCRUMDO_PROJECT": "your-default-project-slug"
      }
    }
  }
}
```

Your org slug and project slug are the short names in your board URL:
`app.scrumdo.com/`**`my-company`**`/`**`engineering`**

### Step 3 — Restart your AI tool

Done. Your AI assistant now has direct access to your board.

---

## What you can do

Once connected, just talk to your AI tool naturally:

```
"What's the status of ENG-42?"
"Move ENG-42 to In Review and add a comment saying the PR is up"
"List all cards assigned to me in the current sprint"
"Create a sub-task on ENG-42: write release notes"
"Search for cards about the login bug"
"What did the team work on this week?"
"Block ENG-42 — waiting on design approval"
"Move ENG-42 to the Sprint 14 iteration"
"Set the due date on ENG-42 to 2026-04-30"
"Assign ENG-42 to Sarah"
```

---

## Available tools (113 total)

| Group | Tools |
|-------|-------|
| **Boards** | `list_boards`, `get_board`, `get_board_cells`, `list_iterations`, `list_milestones`, `list_labels`, `list_epics` |
| **Cards** | `list_cards`, `get_card`, `card_schema`, `find_card`, `create_card`, `update_card`, `move_card`, `move_card_to_iteration`, `set_card_field`, `set_card_fields`, `archive_card`, `assign_card`, `add_card_label`, `remove_card_label` |
| **Blockers** | `list_blockers`, `block_card`, `unblock_card` |
| **Tasks** | `list_tasks`, `create_task`, `complete_task`, `reopen_task`, `update_task`, `delete_task` |
| **Comments** | `list_comments`, `add_comment`, `delete_comment` |
| **Attachments** | `add_attachment` |
| **Fields** | `list_custom_fields`, `get_card_field`, `get_all_card_fields` |
| **Members** | `list_members`, `find_member` |
| **Search** | `search_cards`, `search_by_field_value` |
| **Activity** | `log_activity`, `get_activity_log`, `get_workspace_activity` |
| **Webhooks** | `list_webhooks`, `create_webhook`, `delete_webhook` |
| **Time** | `list_time_entries`, `log_time` |
| **Spec** | `get_card_spec`, `set_card_spec`, `patch_card_spec`, `get_spec_history`, `list_card_spec_documents`, `set_card_spec_document`, `restore_spec_version` — get/set/patch operate on the primary (`requirements`) doc; the multi-doc trio lists per-`doc_type` documents, writes a specific one (human-only), and restores an accepted version forward |
| **Spec proposals** | `generate_spec_proposal`, `list_spec_proposals`, `accept_spec_proposal`, `reject_spec_proposal`, `request_spec_proposal_changes`, `revise_spec_proposal`, `get_decision_inbox`, `preview_spec_decision`, `attest_spec_understood` — all human-only; deciding from an MCP session is gated: `get_decision_inbox` → `preview_spec_decision` mints a `confirm_token` (bound to the proposal's current version, 10-min TTL) → pass it to `accept`/`reject`/`request_changes` |
| **GitHub** | `get_github_repos`, `list_card_github_links`, `link_github_pr`, `link_github_commit`, `link_github_issue` |
| **Cockpit commands** | `invoke_cockpit_command` (governed dispatcher for ANY catalog command by id — executes `loop.status/pause/resume` + `skill.*`, governance-validates the rest), `research_card`, `run_card_tests`, `tasks_from_spec`, `get_card_memory`, `clear_card_memory` — every command in `get_effective_governance`'s catalog is reachable |
| **Cockpit** | `get_card_cockpit_context`, `get_effective_governance`, `get_mcp_capabilities`, `send_cockpit_chat`, `draft_spec_from_card` — the Card AI Cockpit bridge: one-call card context, the governed command policy for a card, this bridge's own tool/connection surface, plus human-only cockpit writes (chat a board agent, draft a spec doc). MCP writes are attributed to the cockpit timeline via `X-Spryng-Source: mcp` |
| **Agents** | `get_agent_identity`, `list_agent_accounts` |
| **Agent runs** | `start_agent_run`, `get_agent_run`, `list_agent_runs`, `approve_agent_plan`, `accept_proof`, `request_agent_replan`, `execute_task`, `report_agent_progress`, `cancel_agent_run` — `approve_agent_plan` / `accept_proof` / `request_agent_replan` / `execute_task` are human-only (run as a human principal); `execute_task` runs a spec-derived task with an agent (Todo→Doing→Reviewing) |
| **Loops & verification** | `start_loop`, `start_verification_loop`, `get_loop_status`, `list_active_loops`, `pause_loop`, `resume_loop`, `cancel_loop`, `get_loop_state`, `update_loop_state`, `get_verification_status`, `run_verifier`, `verify_card`, `log_loop_step`, `attach_evidence`, `route_to_agent`, `list_skills`, `load_skill` |
| **Intelligence** | `get_velocity_forecast`, `get_spec_complexity`, `check_spec_drift`, `verify_behavior_contract` |

For a governed verification loop, an orchestrator agent calls `start_verification_loop`
(by `VerificationProfile` slug or inline `proof_requirements`/`verifier_agent`), the
Maker (Grok/Codex) implements and calls `run_verifier` against the accepted spec
(never self-verifies), and `log_loop_step` / `attach_evidence` write the audit trail
to the card. When an agent runs **inside** a loop (`SPRYNG_LOOP_ID` set), the loop-scoped
tools default to that loop, so `loop_id` is optional.

---

## Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `SCRUMDO_TOKEN` | — | **Required.** API token from Settings → API Tokens (or an agent's token, for AI Agent runs) |
| `SCRUMDO_BASE_URL` | `https://app.spryng.io` | API base URL |
| `SCRUMDO_ORG` | — | Your organization slug |
| `SCRUMDO_PROJECT` | — | Default project slug |
| `SCRUMDO_AGENT_RUN_ID` | — | Optional. AI Agent run id this MCP is driving. When set, every write sends the `X-Spryng-Agent-Run` header so the run's audit trail attributes the write (`change_source='agent_run'`). Requires `SCRUMDO_TOKEN` to be that agent's own token, and the run to belong to it. |
| `SCRUMDO_CLIENT_NAME` | `mcp` | Optional. The host tool driving this bridge (`codex` / `claude-code` / `cursor`). Sent as `X-Spryng-Client` alongside `X-Spryng-Source: mcp` so the Card AI Cockpit timeline can show "via MCP (<client>)". (`SPRYNG_CLIENT_NAME` accepted as an alias; `SCRUMDO_CLIENT_VERSION` optionally adds a version.) |
| `SPRYNG_LOOP_ID` | — | Optional. The governed loop this MCP is running inside. When set, writes carry the `X-Spryng-Loop` header (attributed to the loop's timeline) and the loop-scoped tools (`log_loop_step`, `attach_evidence`, `get_verification_status`) default their `loop_id` to it — so in-loop agents call them without an id. (`SCRUMDO_LOOP_ID` is accepted as an alias.) |

---

## Token scope

Your API token is restricted to your organization's board data only — cards, tasks, comments, members, iterations. It cannot access billing, account settings, or any other organization's data. Revoke it at any time from Settings → API Tokens.

---

## What is MCP?

[Model Context Protocol](https://modelcontextprotocol.io) is an open standard for connecting AI tools to external services. Claude Code, Cursor, Windsurf, and other AI editors support it natively. Install the server once; any MCP-compatible tool can use it.

---

## License

MIT
