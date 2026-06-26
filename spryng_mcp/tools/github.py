"""Phase D (BOARD_AI_AGENTS_UNIFIED_SPEC §D.4) — GitHub link tools.

Five tools that read and write the canonical GitHub linkage:

- list_card_github_links(card_ref, type?)
- link_github_pr(card_ref, pr_url)
- link_github_issue(card_ref, issue_url)
- link_github_commit(card_ref, repo, sha)
- get_github_repos(project_slug?)

Per D3 these are the only writers of `commit_links` for the spec
frontmatter (the projection layer derives the read-only view from
`StoryGitHubLink` rows after every link change).
"""
from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from ..client import SpryngClient
from ..config import Config


def register(mcp: FastMCP) -> None:

    @mcp.tool()
    async def list_card_github_links(
        card_ref: str, type: str | None = None,
    ) -> list[dict]:
        """List the PR / commit / issue links attached to a card.

        Args:
            card_ref: 'ON-914'-style reference.
            type: Optional filter — 'pr', 'commit', 'issue', or 'branch'.
        """
        params: dict = {}
        if type:
            params['type'] = type
        async with SpryngClient() as c:
            story_id = await c._resolve_card_id(card_ref)
            return await c.get(
                Config.project_url(f'stories/{story_id}/github-links/'),
                **params,
            )

    @mcp.tool()
    async def link_github_pr(card_ref: str, pr_url: str) -> dict:
        """Attach a Pull Request URL to a card.

        Use this instead of writing `commit_links` directly — that
        frontmatter key is a read-only view over the StoryGitHubLink
        table (spec §D.2 + D3).
        """
        async with SpryngClient() as c:
            story_id = await c._resolve_card_id(card_ref)
            return await c.post(
                Config.project_url(f'stories/{story_id}/github-links/'),
                {'link_type': 'pr', 'github_ref': pr_url},
            )

    @mcp.tool()
    async def link_github_issue(card_ref: str, issue_url: str) -> dict:
        """Attach a GitHub Issue URL to a card."""
        async with SpryngClient() as c:
            story_id = await c._resolve_card_id(card_ref)
            return await c.post(
                Config.project_url(f'stories/{story_id}/github-links/'),
                {'link_type': 'issue', 'github_ref': issue_url},
            )

    @mcp.tool()
    async def link_github_commit(
        card_ref: str, repo: str, sha: str,
    ) -> dict:
        """Attach a commit SHA to a card.

        Args:
            card_ref: 'ON-914'-style reference.
            repo: 'owner/name' full GitHub repo path.
            sha: Commit SHA (full or short).
        """
        commit_url = f'https://github.com/{repo}/commit/{sha}'
        async with SpryngClient() as c:
            story_id = await c._resolve_card_id(card_ref)
            return await c.post(
                Config.project_url(f'stories/{story_id}/github-links/'),
                {
                    'link_type': 'commit',
                    'github_ref': commit_url,
                    'github_sha': sha,
                },
            )

    @mcp.tool()
    async def get_github_repos(
        project_slug: str | None = None,
    ) -> list[dict]:
        """List GitHub repos connected to a project (or all org repos)."""
        async with SpryngClient() as c:
            slug = project_slug or Config.project
            return await c.get(
                Config.api(
                    f'organizations/{Config.org}/projects/{slug}/github-repos/'
                ),
            )
