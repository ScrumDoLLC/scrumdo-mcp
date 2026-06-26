"""CLI output formatters — human-readable and JSON modes."""
from __future__ import annotations

import json
import os
from typing import Any

import click


def dump_json(data: Any) -> None:
    """Dump data as pretty-printed JSON."""
    click.echo(json.dumps(data, indent=2, default=str))


def _truncate(s: str, n: int) -> str:
    s = s or ""
    return s if len(s) <= n else s[: n - 1] + "…"


def _points_fmt(p: Any) -> str:
    if p is None or p == "?" or p == 0:
        return "[-]   "
    try:
        pts = int(p)
        return f"[{pts}pt{'s' if pts != 1 else ' '}]".ljust(7)
    except (TypeError, ValueError):
        return f"[{p}]".ljust(7)


def _assignees_fmt(card: dict) -> str:
    assignees = card.get("assignee") or card.get("assignees") or []
    if not assignees:
        return "(unassigned)"
    names = [
        f"@{a.get('username') or a.get('email') or '?'}"
        for a in assignees
    ]
    suffix = "…" if len(names) > 3 else ""
    return ", ".join(names[:3]) + suffix


def print_card_list(cards: list[dict]) -> None:
    """Print cards as compact fixed-width one-liners."""
    try:
        width = os.get_terminal_size().columns
    except OSError:
        width = 120

    REF_W, PTS_W, CELL_W, ASSIGN_W = 8, 7, 20, 22
    summary_w = max(20, width - REF_W - PTS_W - CELL_W - ASSIGN_W - 8)

    for card in cards:
        ref = card.get("local_id") or (
            card.get("prefix", "") + "-" + str(card.get("number", "?"))
        )
        cell = card.get("cell")
        if isinstance(cell, dict):
            cell_name = cell.get("label") or cell.get("full_label", "")
        else:
            cell_name = str(cell or "")

        pts = _points_fmt(card.get("points"))
        summary = _truncate(card.get("summary", ""), summary_w)
        assignees = _assignees_fmt(card)

        click.echo(
            f"{str(ref):<{REF_W}}  {pts}  {cell_name:<{CELL_W}}  "
            f"{summary:<{summary_w}}  {assignees}"
        )


def print_card_detail(card: dict) -> None:
    """Print full card detail as a vertical key-value block."""
    ref = card.get("local_id", "?")
    click.echo()
    click.echo(f"  Ref        {ref}")
    click.echo(f"  Summary    {card.get('summary', '')}")

    pts = card.get("points")
    click.echo(f"  Points     {pts if pts and pts != '?' else '(unset)'}")

    cell = card.get("cell")
    cell_name = (
        cell.get("label", str(cell)) if isinstance(cell, dict) else str(cell or "")
    )
    click.echo(f"  Column     {cell_name}")

    iter_name = card.get("iteration_name") or card.get("iteration_id") or ""
    if iter_name:
        click.echo(f"  Iteration  {iter_name}")

    click.echo(f"  Assignees  {_assignees_fmt(card)}")

    labels = card.get("labels") or []
    label_names = [
        (lbl.get("name") or str(lbl)) if isinstance(lbl, dict) else str(lbl)
        for lbl in labels
    ]
    click.echo(f"  Labels     {', '.join(label_names) or '(none)'}")

    due = card.get("due_date") or ""
    if due:
        click.echo(f"  Due        {due}")

    tags = card.get("tags") or ""
    if tags:
        click.echo(f"  Tags       {tags}")

    click.echo(f"  Created    {card.get('created', '')}")
    click.echo(f"  Modified   {card.get('modified', '')}")

    detail = card.get("detail") or card.get("description") or ""
    if detail:
        click.echo()
        click.echo("  " + "─" * 52)
        for line in detail.splitlines():
            click.echo(f"  {line}")
    click.echo()


def print_table(rows: list[dict], columns: list[str]) -> None:
    """Print a simple fixed-width table with auto-sized columns."""
    if not rows:
        click.echo("(none)")
        return

    col_widths = {c: len(c) for c in columns}
    str_rows: list[dict[str, str]] = []
    for row in rows:
        str_row = {}
        for c in columns:
            val = str(row.get(c, "") or "")
            col_widths[c] = max(col_widths[c], len(val))
            str_row[c] = val
        str_rows.append(str_row)

    header = "  ".join(c.upper().ljust(col_widths[c]) for c in columns)
    divider = "  ".join("-" * col_widths[c] for c in columns)
    click.echo(header)
    click.echo(divider)
    for row in str_rows:
        click.echo("  ".join(row[c].ljust(col_widths[c]) for c in columns))
