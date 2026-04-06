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
                          default="https://app.scrumdo.com").rstrip("/")
    token: str = _env("SCRUMDO_TOKEN", "SPRYNG_TOKEN")
    org: str = _env("SCRUMDO_ORG", "SPRYNG_ORG", default="")
    project: str = _env("SCRUMDO_PROJECT", "SPRYNG_PROJECT", default="")

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
