"""Attachment tools — WRITE ONLY.

This module deliberately exposes a single ``add_attachment`` tool that
uploads a file or registers an external URL as an attachment on a
ScrumDo card. It does not expose any read, list, or download tool.

Design intent:
    The MCP can put new attachments on cards (e.g. logs, screenshots,
    evidence files produced during agent work) but cannot retrieve or
    enumerate existing attachments. Read access continues to live in
    the ScrumDo UI / API for human users, not in this MCP.

If a future change ever adds a read or download path to this MCP, the
write-only contract must be re-confirmed with the user first.
"""
from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from ..client import SpryngClient


def register(mcp: FastMCP) -> None:

    @mcp.tool()
    async def add_attachment(
        card_ref: str,
        file_path: str | None = None,
        file_url: str | None = None,
        file_name: str | None = None,
        thumb_url: str | None = None,
    ) -> dict:
        """
        Add a new attachment to a card. WRITE ONLY: this MCP cannot read,
        list, or download attachments.

        Provide EXACTLY ONE of file_path or file_url:

        Local upload:
            add_attachment("ON-914", file_path="/tmp/run-evidence.txt")

            The file at the given absolute path is uploaded as
            multipart/form-data. file_name defaults to the basename
            of file_path; pass file_name to override the display name
            shown in the ScrumDo UI.

        External URL:
            add_attachment("ON-914",
                           file_url="https://example.com/report.pdf",
                           file_name="report.pdf")

            The card stores the URL reference (no copy is made server
            side). file_name is required in URL mode.

        Args:
            card_ref:  Card reference, e.g. 'ON-914'. Resolved to a
                       story id automatically.
            file_path: Absolute path to a local file to upload.
            file_url:  Externally hosted URL to register as an attachment.
            file_name: Display name shown in the ScrumDo UI. Defaults to
                       the basename of file_path in local mode; required
                       in URL mode.
            thumb_url: Optional thumbnail URL.

        Returns the created attachment object from the API. Does not
        return a download URL the MCP can later read.
        """
        async with SpryngClient() as c:
            return await c.add_attachment(
                card_ref,
                file_path=file_path,
                file_url=file_url,
                file_name=file_name,
                thumb_url=thumb_url,
            )
