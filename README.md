# scrumdo-mcp

Connect any MCP-compatible AI tool (Claude Code, Cursor, Windsurf, and others) directly to your [ScrumDo](https://www.scrumdo.com) boards.

Once installed, your AI assistant can read cards, move them, create tasks, post comments, and search across your board — without you copy-pasting anything.

---

## Installation

```bash
pip install scrumdo-mcp
```

> **Pre-release / before PyPI publish:** install directly from GitHub:
> ```bash
> pip install git+https://github.com/ScrumDoLLC/scrumdo-mcp.git
> ```

---

## Cursor quick-start

**1 — Install**
```bash
# To run the server only:
pip install git+https://github.com/ScrumDoLLC/scrumdo-mcp.git

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
```

---

## Available tools (41 total)

| Group | Tools |
|-------|-------|
| **Boards** | `list_boards`, `get_board`, `get_board_cells`, `list_iterations`, `list_labels`, `list_epics` |
| **Cards** | `list_cards`, `get_card`, `find_card`, `create_card`, `update_card`, `move_card`, `set_card_field`, `archive_card`, `assign_card`, `add_card_label`, `remove_card_label` |
| **Tasks** | `list_tasks`, `create_task`, `complete_task`, `reopen_task`, `update_task`, `delete_task` |
| **Comments** | `list_comments`, `add_comment`, `delete_comment` |
| **Fields** | `list_custom_fields`, `get_card_field`, `get_all_card_fields` |
| **Members** | `list_members`, `find_member` |
| **Search** | `search_cards`, `search_by_field_value` |
| **Activity** | `log_activity`, `get_activity_log`, `get_workspace_activity` |
| **Webhooks** | `list_webhooks`, `create_webhook`, `delete_webhook` |
| **Time** | `list_time_entries`, `log_time` |

---

## Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `SCRUMDO_TOKEN` | — | **Required.** API token from Settings → API Tokens |
| `SCRUMDO_BASE_URL` | `https://app.spryng.io` | API base URL |
| `SCRUMDO_ORG` | — | Your organization slug |
| `SCRUMDO_PROJECT` | — | Default project slug |

---

## Token scope

Your API token is restricted to your organization's board data only — cards, tasks, comments, members, iterations. It cannot access billing, account settings, or any other organization's data. Revoke it at any time from Settings → API Tokens.

---

## What is MCP?

[Model Context Protocol](https://modelcontextprotocol.io) is an open standard for connecting AI tools to external services. Claude Code, Cursor, Windsurf, and other AI editors support it natively. Install the server once; any MCP-compatible tool can use it.

---

## License

MIT
