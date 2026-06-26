"""
scrumdo CLI — terminal interface for ScrumDo / Spryng boards.

Quick reference:
    scrumdo card get ON-914
    scrumdo card ls [--cell N] [--iter N] [--assignee X] [--limit N]
    scrumdo card create "Fix the auth bug" --points 3
    scrumdo card update ON-914 --points 5 --tags "backend,blocked"
    scrumdo card move ON-914 20133
    scrumdo card add-comment ON-914 --body "Ship it"
    scrumdo card comments ON-914
    scrumdo search "login bug"
    scrumdo board cells
    scrumdo board labels
    scrumdo board iterations
    scrumdo board members

Global flags (put before the subcommand):
    --json          Dump raw JSON instead of formatted output

Environment variables:
    SCRUMDO_TOKEN       Bearer token (required)
    SCRUMDO_ORG         Organisation slug
    SCRUMDO_PROJECT     Default project slug
    SCRUMDO_BASE_URL    API base URL (default: https://app.spryng.io)
"""
from __future__ import annotations

import asyncio
import json
import sys
from typing import Any

import click
import httpx

from ..client import SpryngClient
from ..config import Config
from .output import dump_json, print_card_detail, print_card_list, print_table


# ── Async runner ──────────────────────────────────────────────────────────────

def run(coro):
    """Run an async coroutine, translate common API errors into clean messages."""
    try:
        Config.validate()
        return asyncio.run(coro)
    except httpx.HTTPStatusError as e:
        body = e.response.text[:300]
        try:
            msg = json.loads(body).get("detail", body)
        except Exception:
            msg = body
        click.echo(f"Error {e.response.status_code}: {msg}", err=True)
        sys.exit(1)
    except (ValueError, RuntimeError) as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


# ── Top-level group ───────────────────────────────────────────────────────────

@click.group()
@click.option("--json", "as_json", is_flag=True, help="Output raw JSON.")
@click.version_option(package_name="scrumdo-mcp")
@click.pass_context
def cli(ctx, as_json):
    """ScrumDo CLI — manage your board from the terminal.

    Reads SCRUMDO_TOKEN, SCRUMDO_ORG, SCRUMDO_PROJECT, SCRUMDO_BASE_URL
    from the environment or a .env file in the working directory.
    """
    ctx.ensure_object(dict)
    ctx.obj["json"] = as_json


# ── card group ────────────────────────────────────────────────────────────────

@cli.group()
def card():
    """Card (story) commands."""


@card.command("get")
@click.argument("ref")
@click.pass_context
def card_get(ctx, ref):
    """Get full detail for a card.

    \b
    Example:
        scrumdo card get ON-914
    """
    async def _():
        async with SpryngClient() as c:
            return await c.get_card(ref)

    data = run(_())
    if ctx.obj["json"]:
        dump_json(data)
    else:
        print_card_detail(data)


@card.command("ls")
@click.option("--cell", "cell_id", type=int, default=None, help="Filter by column id (see: scrumdo board cells).")
@click.option("--iter", "iteration_id", type=int, default=None, help="Filter by iteration id (see: scrumdo board iterations).")
@click.option("--assignee", default=None, help="Filter by assignee username or email.")
@click.option("--label", default=None, help="Filter by label name.")
@click.option("--limit", default=25, show_default=True, help="Results per page.")
@click.option("--page", default=1, show_default=True, help="Page number.")
@click.pass_context
def card_ls(ctx, cell_id, iteration_id, assignee, label, limit, page):
    """List cards on the board.

    \b
    Examples:
        scrumdo card ls
        scrumdo card ls --iter 13900 --limit 50
        scrumdo card ls --cell 20132 --assignee alice
    """
    filters: dict[str, Any] = {"page": page, "limit": limit}
    if cell_id is not None:
        filters["cell_id"] = cell_id
    if iteration_id is not None:
        filters["iteration_id"] = iteration_id
    if assignee:
        filters["assignee"] = assignee
    if label:
        filters["label"] = label

    async def _():
        async with SpryngClient() as c:
            return await c.list_cards(**filters)

    data = run(_())
    items = data.get("items", data) if isinstance(data, dict) else data
    total = data.get("count", len(items)) if isinstance(data, dict) else len(items)

    if ctx.obj["json"]:
        dump_json(data)
        return

    if not items:
        click.echo("No cards found.")
        return

    print_card_list(items)

    if isinstance(data, dict) and data.get("next"):
        click.echo(f"\n  {total} total · page {page} · use --page to paginate")


@card.command("create")
@click.argument("summary")
@click.option("--description", "-d", default=None, help="Description (markdown).")
@click.option("--points", "-p", type=int, default=None, help="Story points.")
@click.option("--cell", "cell_id", type=int, default=None, help="Column id.")
@click.option("--iter", "iteration_id", type=int, default=None, help="Iteration id.")
@click.option("--label-ids", default=None, help="Comma-separated label ids, e.g. '12,34'.")
@click.option("--tags", default=None, help="Comma-separated tags.")
@click.pass_context
def card_create(ctx, summary, description, points, cell_id, iteration_id, label_ids, tags):
    """Create a new card.

    \b
    Examples:
        scrumdo card create "Fix the login bug"
        scrumdo card create "New feature" --points 5 --cell 20132 --iter 13900
    """
    body: dict[str, Any] = {"summary": summary}
    if description:
        body["description"] = description
    if points is not None:
        body["points"] = points
    if cell_id is not None:
        body["cell_id"] = cell_id
    if label_ids:
        body["labels"] = [int(x.strip()) for x in label_ids.split(",")]
    if tags:
        body["tags"] = tags

    async def _():
        async with SpryngClient() as c:
            return await c.create_card(body, iteration_id=iteration_id)

    data = run(_())

    if ctx.obj["json"]:
        dump_json(data)
    else:
        ref = data.get("local_id", "?")
        click.echo(f"Created {ref}: {data.get('summary', '')}")


@card.command("update")
@click.argument("ref")
@click.option("--summary", "-s", default=None, help="New title.")
@click.option("--description", "-d", default=None, help="New description (markdown).")
@click.option("--points", "-p", type=int, default=None, help="Story points.")
@click.option("--tags", default=None, help="Comma-separated tags (replaces existing). Pass '' to clear.")
@click.pass_context
def card_update(ctx, ref, summary, description, points, tags):
    """Update fields on a card.

    \b
    Examples:
        scrumdo card update ON-914 --points 5
        scrumdo card update ON-914 --summary "Better title" --tags "backend,qa"
    """
    body: dict[str, Any] = {}
    if summary is not None:
        body["summary"] = summary
    if description is not None:
        body["description"] = description
    if points is not None:
        body["points"] = points
    if tags is not None:
        body["tags"] = tags

    if not body:
        click.echo("Nothing to update — pass at least one option.", err=True)
        sys.exit(1)

    async def _():
        async with SpryngClient() as c:
            return await c.update_card(ref, body)

    data = run(_())

    if ctx.obj["json"]:
        dump_json(data)
    else:
        click.echo(f"Updated {data.get('local_id', ref)}")


@card.command("move")
@click.argument("ref")
@click.argument("cell_id", type=int)
@click.pass_context
def card_move(ctx, ref, cell_id):
    """Move a card to a different column.

    \b
    Tip: run 'scrumdo board cells' to see column ids.

    Example:
        scrumdo card move ON-914 20133
    """
    async def _():
        async with SpryngClient() as c:
            return await c.update_card(ref, {"cell_id": cell_id})

    data = run(_())

    if ctx.obj["json"]:
        dump_json(data)
    else:
        cell = data.get("cell", {})
        cell_name = (
            cell.get("label", str(cell_id)) if isinstance(cell, dict) else str(cell_id)
        )
        click.echo(f"Moved {data.get('local_id', ref)} → {cell_name}")


@card.command("add-comment")
@click.argument("ref")
@click.option("--body", "-b", required=True,
              help="Comment text (markdown). Use '-' to read from stdin.")
@click.pass_context
def card_add_comment(ctx, ref, body):
    """Post a comment on a card.

    \b
    Examples:
        scrumdo card add-comment ON-914 --body "Looks good to merge"
        echo "See attached logs" | scrumdo card add-comment ON-914 --body -
    """
    if body == "-":
        body = sys.stdin.read()

    async def _():
        async with SpryngClient() as c:
            card = await c.get_card(ref)
            return await c.add_comment(card["id"], body)

    data = run(_())

    if ctx.obj["json"]:
        dump_json(data)
    else:
        click.echo(f"Comment posted (id: {data.get('id', '?')})")


@card.command("comments")
@click.argument("ref")
@click.pass_context
def card_comments(ctx, ref):
    """List comments on a card.

    \b
    Example:
        scrumdo card comments ON-914
    """
    async def _():
        async with SpryngClient() as c:
            card = await c.get_card(ref)
            return await c.list_comments(card["id"])

    comments = run(_())

    if ctx.obj["json"]:
        dump_json(comments)
        return

    if not comments:
        click.echo("No comments.")
        return

    for comment in comments:
        author = comment.get("author") or comment.get("user") or "?"
        ts = comment.get("created", "")
        body = comment.get("comment", "")
        click.echo(f"\n  [{comment.get('id')}] {author}  {ts}")
        # Indent and truncate body to 400 chars for readability
        preview = body[:400] + ("…" if len(body) > 400 else "")
        for line in preview.splitlines():
            click.echo(f"    {line}")
    click.echo()


# ── search command ─────────────────────────────────────────────────────────────

@cli.command()
@click.argument("query")
@click.pass_context
def search(ctx, query):
    """Full-text search across all cards.

    \b
    Example:
        scrumdo search "auth bug"
    """
    async def _():
        async with SpryngClient() as c:
            return await c.search(query)

    results = run(_())

    if ctx.obj["json"]:
        dump_json(results)
        return

    if not results:
        click.echo("No results.")
        return

    print_card_list(results)


# ── board group ───────────────────────────────────────────────────────────────

@cli.group()
def board():
    """Board reference data — cells, labels, iterations, members."""


@board.command("cells")
@click.pass_context
def board_cells(ctx):
    """List board columns (cells) and their ids.

    \b
    Use the id with 'scrumdo card move <ref> <cell_id>'.
    """
    async def _():
        async with SpryngClient() as c:
            return await c.get_board_cells()

    cells = run(_())
    if ctx.obj["json"]:
        dump_json(cells)
    else:
        print_table(cells, ["id", "label"])


@board.command("labels")
@click.pass_context
def board_labels(ctx):
    """List labels and their ids.

    \b
    Use the id with 'scrumdo card create --label-ids 12,34'.
    """
    async def _():
        async with SpryngClient() as c:
            return await c.list_labels()

    labels = run(_())
    if ctx.obj["json"]:
        dump_json(labels)
    else:
        print_table(labels, ["id", "name", "color"])


@board.command("iterations")
@click.pass_context
def board_iterations(ctx):
    """List iterations (sprints) and their ids."""
    async def _():
        async with SpryngClient() as c:
            return await c.list_iterations()

    iters = run(_())
    if ctx.obj["json"]:
        dump_json(iters)
    else:
        print_table(iters, ["id", "name", "start_date", "end_date"])


@board.command("members")
@click.pass_context
def board_members(ctx):
    """List project members."""
    async def _():
        async with SpryngClient() as c:
            return await c.list_members()

    members = run(_())
    if ctx.obj["json"]:
        dump_json(members)
    else:
        print_table(members, ["id", "username", "email"])


# ── Entrypoint ─────────────────────────────────────────────────────────────────

def main() -> None:
    cli()


if __name__ == "__main__":
    main()
