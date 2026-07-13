"""Configuration — loaded from environment variables or .env file."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# Load .env from the mcp/ directory if present
load_dotenv(Path(__file__).parent.parent / ".env")


def _env(*keys: str, default: str = "") -> str:
    """Return the first non-empty value from the given env var names."""
    for key in keys:
        val = os.getenv(key, "")
        if val:
            return val
    return default


class Config:
    """Runtime configuration for the ScrumDo MCP server.

    Accepts both SCRUMDO_* (preferred) and legacy SPRYNG_* env var names.
    """

    base_url: str = _env("SCRUMDO_BASE_URL", "SPRYNG_BASE_URL",
                          default="https://app.spryng.io").rstrip("/")
    token: str = _env("SCRUMDO_TOKEN", "SPRYNG_TOKEN")
    org: str = _env("SCRUMDO_ORG", "SPRYNG_ORG", default="")
    project: str = _env("SCRUMDO_PROJECT", "SPRYNG_PROJECT", default="")

    # Phase 0 (BOARD_AI_AGENTS_UNIFIED_SPEC §13.2) — run-context header.
    # When the connecting agent has been issued an AgentRunToken, this id
    # MUST be set; every outbound request will carry the
    # `X-Spryng-Agent-Run` header so audit-log destinations can attribute
    # writes to a specific AgentRun.
    agent_run_id: str = _env("SPRYNG_AGENT_RUN_ID", "SCRUMDO_AGENT_RUN_ID",
                             default="")

    # GOVERNED_AGENT_LOOPS_SPEC §4 — loop correlation header. When an agent is
    # operating inside a governed loop, set this so every outbound write carries
    # `X-Spryng-Loop` and can be grouped into the loop's timeline.
    loop_id: str = _env("SPRYNG_LOOP_ID", "SCRUMDO_LOOP_ID", default="")

    # AI_COCKPIT_BRIDGE_SPEC.md §4.3 — write attribution. Every request carries
    # `X-Spryng-Source: mcp` + a client name so the Card AI Cockpit can render
    # "via MCP (<client>)". Set SCRUMDO_CLIENT_NAME to the host tool (codex /
    # claude-code / cursor); defaults to "mcp".
    client_name: str = _env("SCRUMDO_CLIENT_NAME", "SPRYNG_CLIENT_NAME",
                            default="mcp")
    client_version: str = _env("SCRUMDO_CLIENT_VERSION", "SPRYNG_CLIENT_VERSION",
                               default="")

    @classmethod
    def validate(cls) -> None:
        if not cls.token:
            raise RuntimeError(
                "SCRUMDO_TOKEN is not set. "
                "Set it in your MCP config env block or in a .env file."
            )

    @classmethod
    def api(cls, path: str) -> str:
        """Build a full API URL. path is relative to /api/scrumdo/."""
        return f"{cls.base_url}/api/scrumdo/{path.lstrip('/')}"

    @classmethod
    def org_url(cls, path: str = "") -> str:
        return cls.api(f"organizations/{cls.org}/{path.lstrip('/')}")

    @classmethod
    def project_url(cls, path: str = "") -> str:
        return cls.org_url(f"projects/{cls.project}/{path.lstrip('/')}")
