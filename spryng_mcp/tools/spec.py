"""Phase B (BOARD_AI_AGENTS_UNIFIED_SPEC §5.6) — card spec tools.

Three tools that read and write the canonical card spec via the new
`/spec/` REST endpoint (handler lives in MassSense at
`apps.api_v4.handlers.story_spec.StorySpecHandler`).
"""
from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from ..client import SpryngClient
from ..config import Config


def register(mcp: FastMCP) -> None:

    @mcp.tool()
    async def get_card_spec(
        card_ref: str,
        fmt: str | None = None,
    ) -> dict:
        """Read the canonical machine-readable spec for a card.

        Per BOARD_AI_AGENTS_UNIFIED_SPEC §5: the spec is the source of
        truth for everything Phase B–G consumes. On first read for a
        card that only has legacy custom-field values, the projection
        layer creates a `StorySpec` row seeded from those values.

        Args:
            card_ref: 'ON-914'-style reference.
            fmt: Optional 'md' | 'json' | 'yaml' — when supplied,
                 the backend returns the content in that format
                 (round-trip via `meta.body` preserves the markdown
                 body per Q-B2).
        """
        async with SpryngClient() as c:
            story_id = await c._resolve_card_id(card_ref)
            data = await c.get(Config.project_url(f'stories/{story_id}/spec/'))
        if fmt and fmt != data.get('format'):
            # Caller wants a different format; round-trip through the
            # PATCH endpoint preserves the body in `meta.body`.
            async with SpryngClient() as c:
                story_id = await c._resolve_card_id(card_ref)
                data = await c.patch(
                    Config.project_url(f'stories/{story_id}/spec/'),
                    {'patch': {}, 'format': fmt},
                )
        return data

    @mcp.tool()
    async def set_card_spec(
        card_ref: str,
        content: str,
        fmt: str = 'md',
        change_summary: str = '',
    ) -> dict:
        """Replace the card spec wholesale.

        The backend re-projects to legacy custom fields atomically; the
        change is recorded in spec history (Phase C) with the supplied
        `change_summary`.

        Args:
            card_ref: 'ON-914'-style reference.
            content: New full content (frontmatter + body for MD).
            fmt: 'md' (default) | 'json' | 'yaml'.
            change_summary: Short why-line for the history row.

        Returns the updated spec row + any conversion warnings.
        """
        async with SpryngClient() as c:
            story_id = await c._resolve_card_id(card_ref)
            return await c.post(
                Config.project_url(f'stories/{story_id}/spec/'),
                {
                    'content': content,
                    'format': fmt,
                    'change_summary': change_summary,
                },
            )

    @mcp.tool()
    async def get_spec_history(
        card_ref: str,
        limit: int = 20,
        source: str | None = None,
        changed_by: int | None = None,
        agent_run_id: int | None = None,
        include_archived: bool = False,
        include_content: bool = False,
    ) -> list[dict]:
        """Read the spec change-history rows for a card.

        Each row carries: changed_at, changed_by, change_summary,
        auto_summary, change_source (one of ui|mcp|api|github_sync|
        legacy_field|agent_run), agent_run_id, diff, and optionally
        the previous/new content blobs when `include_content=True`.

        Args:
            card_ref: 'ON-914'-style reference.
            limit: max rows to return (default 20, hard cap 200).
            source: filter by change_source value.
            changed_by: filter by user id.
            agent_run_id: filter to writes from one AgentRun.
            include_archived: union the archive table (rows > 90d).
            include_content: include previous_content/new_content blobs.
                             Defaults off because they can be large.
        """
        params: dict = {'limit': limit}
        if source:
            params['source'] = source
        if changed_by is not None:
            params['changed_by'] = changed_by
        if agent_run_id is not None:
            params['agent_run_id'] = agent_run_id
        if include_archived:
            params['include_archived'] = 'true'
        if include_content:
            params['include_content'] = 'true'

        async with SpryngClient() as c:
            story_id = await c._resolve_card_id(card_ref)
            return await c.get(
                Config.project_url(f'stories/{story_id}/spec/history/'),
                **params,
            )

    @mcp.tool()
    async def patch_card_spec(
        card_ref: str,
        patch: dict,
        fmt: str | None = None,
        change_summary: str = '',
    ) -> dict:
        """Apply a single-field merge to the card spec.

        Use this for narrow updates (`outcome`, `promotion_status`,
        `agent_context.decisions`, …) rather than re-writing the whole
        spec.

        Frontmatter keys that are read-only (`commit_links`) or that an
        agent identity isn't permitted to write (per §F.2) cause the
        backend to 400 with `field_readonly` / 403 respectively.

        Args:
            card_ref: 'ON-914'-style reference.
            patch: Dict of frontmatter keys to set (JSON-merge-patch
                   semantics for JSON/YAML; key dict for MD).
            fmt: Optional new format. When supplied AND different from
                 the existing format, body is preserved in `meta.body`
                 and a warning is surfaced (Q-B2).
            change_summary: Short why-line for the history row.
        """
        body: dict = {'patch': patch, 'change_summary': change_summary}
        if fmt:
            body['format'] = fmt
        async with SpryngClient() as c:
            story_id = await c._resolve_card_id(card_ref)
            return await c.patch(
                Config.project_url(f'stories/{story_id}/spec/'), body,
            )

    # ── Multi-document specs (Card AI Cockpit v2 Phase 1) ────────────────────
    #
    # get/set/patch_card_spec above operate on the card's PRIMARY spec (the
    # `requirements` document). A card can also carry other doc_types (design,
    # test, …); these three tools list them and write/restore a specific one.

    @mcp.tool()
    async def list_card_spec_documents(card_ref: str) -> dict:
        """List a card's per-doc_type spec documents (multi-doc model).

        Returns every doc_type slot (requirements, design, test, …) with its
        label, current content, has-content flag, and open review-comment count —
        the data behind the cockpit's doc-type tab strip. Use it to discover which
        documents exist before reading or writing a specific one.

        Args:
            card_ref: 'ON-914'-style reference.

        Returns {docs: [{doc_type, label, content, has_content,
        review_open_comments}, ...], ...}.
        """
        async with SpryngClient() as c:
            story_id = await c._resolve_card_id(card_ref)
            return await c.get(
                Config.project_url(f'stories/{story_id}/spec/docs/'))

    @mcp.tool()
    async def set_card_spec_document(
        card_ref: str,
        doc_type: str,
        content: str,
        fmt: str = 'md',
    ) -> dict:
        """Create or replace one doc_type's spec document (human-only).

        The multi-document counterpart to set_card_spec — writes the `design`,
        `test`, or any non-requirements document (for `requirements`, prefer
        set_card_spec). Records an accepted version when the content changes.
        Runs as a human principal; a run-scoped / agent token is refused (agents
        use the whitelisted set_card_spec / patch_card_spec path instead).

        Args:
            card_ref: 'ON-914'-style reference.
            doc_type: 'requirements' | 'design' | 'test' | … (see
                list_card_spec_documents for the valid slots).
            content: Full document content.
            fmt: 'md' (default) | 'json' | 'yaml'.
        """
        async with SpryngClient(human_principal=True) as c:
            story_id = await c._resolve_card_id(card_ref)
            return await c.post(
                Config.project_url(f'stories/{story_id}/spec/docs/'),
                {'doc_type': doc_type, 'content': content, 'format': fmt},
            )

    @mcp.tool()
    async def restore_spec_version(
        card_ref: str,
        version_number: int,
        doc_type: str = 'requirements',
    ) -> dict:
        """Restore an accepted spec version by copying it FORWARD as a new version.

        History is never rewritten — the restore appends the old content as the
        latest version. Human-only (runs as a human principal).

        Args:
            card_ref: 'ON-914'-style reference.
            version_number: The accepted version to restore (from
                get_spec_history / the versions list).
            doc_type: Which document's history to restore into. Defaults to
                'requirements'.
        """
        async with SpryngClient(human_principal=True) as c:
            story_id = await c._resolve_card_id(card_ref)
            return await c.post(
                Config.project_url(
                    f'stories/{story_id}/spec/versions/restore/'),
                {'doc_type': doc_type, 'version_number': version_number},
            )
