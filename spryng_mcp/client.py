"""Async HTTP client for the ScrumDo / Spryng REST API."""
from __future__ import annotations

from typing import Any

import httpx

from .config import Config


class SpryngClient:
    """
    Thin async wrapper around the ScrumDo API.

    All methods raise httpx.HTTPStatusError on 4xx/5xx responses.
    The caller (tool layer) is responsible for presenting errors to the LLM.
    """

    def __init__(self) -> None:
        self._http = httpx.AsyncClient(
            headers={
                "Authorization": f"Bearer {Config.token}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            timeout=30.0,
        )
        # Cache: human-readable card ref (e.g. "ON-914") → numeric story id
        self._card_id_cache: dict[str, int] = {}

    async def __aenter__(self) -> "SpryngClient":
        return self

    async def __aexit__(self, *_: Any) -> None:
        await self._http.aclose()

    # ── Card-ref resolution ───────────────────────────────────────────────────

    async def _resolve_card_id(self, card_ref: str) -> int:
        """
        Convert a human-readable card reference like 'ON-914' into the
        numeric database story id required by the /stories/{id}/ endpoints.

        The API does not expose a reference-based lookup; we resolve by
        scanning the paginated story list and matching on the ``number``
        field (which equals the local_id / project-scoped sequence number).

        Results are cached on the client instance so each ref is resolved
        only once per session.
        """
        # Fast path: caller already has a numeric id
        if isinstance(card_ref, int) or (
            isinstance(card_ref, str) and card_ref.lstrip("-").isdigit()
        ):
            return int(card_ref)

        # Cache hit
        if card_ref in self._card_id_cache:
            return self._card_id_cache[card_ref]

        # Parse the number portion from e.g. "ON-914" → 914
        parts = card_ref.rsplit("-", 1)
        if len(parts) != 2 or not parts[1].isdigit():
            raise ValueError(
                f"Cannot parse card reference {card_ref!r}. "
                "Expected format: PREFIX-NUMBER (e.g. 'ON-914')."
            )
        target_number = int(parts[1])

        # Scan story list pages (100 items/page, max ~10 pages for most boards)
        page = 1
        while True:
            data = await self.get(
                Config.project_url("stories/"), page=page, page_size=100
            )
            items = data.get("items", []) if isinstance(data, dict) else data
            for story in items:
                if story.get("number") == target_number:
                    story_id: int = story["id"]
                    self._card_id_cache[card_ref] = story_id
                    return story_id
            # Stop when there are no more pages
            has_next = isinstance(data, dict) and bool(data.get("next"))
            if not has_next or not items:
                break
            page += 1

        raise ValueError(
            f"Card {card_ref!r} (number={target_number}) not found in "
            f"project {Config.project!r}."
        )

    # ── Generic helpers ───────────────────────────────────────────────────────

    async def get(self, url: str, **params: Any) -> Any:
        r = await self._http.get(url, params=params or None)
        r.raise_for_status()
        return r.json()

    async def post(self, url: str, body: dict[str, Any]) -> Any:
        r = await self._http.post(url, json=body)
        r.raise_for_status()
        return r.json()

    async def patch(self, url: str, body: dict[str, Any]) -> Any:
        r = await self._http.patch(url, json=body)
        r.raise_for_status()
        return r.json()

    async def put(self, url: str, body: dict[str, Any] | list) -> Any:
        r = await self._http.put(url, json=body)
        r.raise_for_status()
        return r.json()

    async def delete(self, url: str) -> int:
        r = await self._http.delete(url)
        r.raise_for_status()
        return r.status_code

    # ── Boards / Projects ──────────────────────────────────────────────────────

    async def list_boards(self) -> list[dict]:
        data = await self.get(Config.org_url("projects/"))
        return data if isinstance(data, list) else data.get("projects", data)

    async def get_board(self, project_slug: str | None = None) -> dict:
        slug = project_slug or Config.project
        return await self.get(Config.org_url(f"projects/{slug}/"))

    async def get_board_cells(self, project_slug: str | None = None) -> list[dict]:
        slug = project_slug or Config.project
        data = await self.get(Config.project_url("boardcell/") if not project_slug
                              else Config.api(f"organizations/{Config.org}/projects/{slug}/boardcell/"))
        return data if isinstance(data, list) else data.get("cells", data)

    # ── Cards / Stories ────────────────────────────────────────────────────────

    async def list_cards(self, **filters: Any) -> dict:
        return await self.get(Config.project_url("stories/"), **filters)

    async def get_card(self, card_ref: str) -> dict:
        """card_ref is the full reference like 'ON-914'."""
        story_id = await self._resolve_card_id(card_ref)
        return await self.get(Config.project_url(f"stories/{story_id}/"))

    @staticmethod
    def _normalize_story_body(body: dict[str, Any]) -> dict[str, Any]:
        """Map MCP field names to API field names and drop unsupported keys."""
        body = dict(body)
        # "description" is the MCP-facing name; the API uses "detail"
        if "description" in body:
            body["detail"] = body.pop("description")
        # "cell" is how create passes the value; the API uses "cell_id"
        if "cell" in body:
            body["cell_id"] = body.pop("cell")
        # "iteration" / "archived" are not processed by the story body handler
        body.pop("iteration", None)
        body.pop("archived", None)
        body.pop("status", None)
        return body

    async def create_card(self, body: dict[str, Any], iteration_id: int | None = None) -> dict:
        body = self._normalize_story_body(body)
        # POST must go to iterations/{id}/stories/ — iteration_id required
        iter_id = iteration_id or body.pop("iteration_id", None)
        if not iter_id:
            # Fall back to the project's default (backlog) iteration
            iters = await self.get(Config.project_url("iterations/"))
            iters = iters if isinstance(iters, list) else iters.get("iterations", [])
            default = next((i for i in iters if i.get("iteration_type") == 0), None)
            iter_id = default["id"] if default else iters[0]["id"]
        return await self.post(Config.project_url(f"iterations/{iter_id}/stories/"), body)

    async def update_card(self, card_ref: str, body: dict[str, Any],
                          iteration_id: int | None = None) -> dict:
        story_id = await self._resolve_card_id(card_ref)
        body = self._normalize_story_body(body)
        if iteration_id:
            url = Config.project_url(f"iterations/{iteration_id}/stories/{story_id}/")
        else:
            url = Config.project_url(f"stories/{story_id}/")
        return await self.put(url, body)

    async def archive_card(self, card_ref: str) -> dict:
        story_id = await self._resolve_card_id(card_ref)
        iters = await self.get(Config.project_url("iterations/"))
        iters = iters if isinstance(iters, list) else iters.get("iterations", [])
        archive = next((i for i in iters if i.get("iteration_type") == 2), None)
        if not archive:
            raise ValueError("No archive iteration found for this project.")
        return await self.put(
            Config.project_url(f"iterations/{archive['id']}/stories/{story_id}/"), {}
        )

    async def delete_card(self, card_ref: str) -> int:
        story_id = await self._resolve_card_id(card_ref)
        return await self.delete(Config.project_url(f"stories/{story_id}/"))

    # ── Tasks ──────────────────────────────────────────────────────────────────

    async def list_tasks(self, card_ref: str) -> list[dict]:
        story_id = await self._resolve_card_id(card_ref)
        data = await self.get(Config.project_url(f"stories/{story_id}/tasks/"))
        return data if isinstance(data, list) else data.get("tasks", data)

    async def create_task(self, card_ref: str, body: dict[str, Any]) -> dict:
        story_id = await self._resolve_card_id(card_ref)
        return await self.post(Config.project_url(f"stories/{story_id}/tasks/"), body)

    async def update_task(self, card_ref: str, task_id: int, body: dict[str, Any]) -> dict:
        story_id = await self._resolve_card_id(card_ref)
        return await self.patch(Config.project_url(f"stories/{story_id}/tasks/{task_id}/"), body)

    async def delete_task(self, card_ref: str, task_id: int) -> int:
        story_id = await self._resolve_card_id(card_ref)
        return await self.delete(Config.project_url(f"stories/{story_id}/tasks/{task_id}/"))

    # ── Comments ───────────────────────────────────────────────────────────────

    async def list_comments(self, card_id: int) -> list[dict]:
        data = await self.get(Config.api(f"comments/story/{card_id}/"))
        return data if isinstance(data, list) else data.get("comments", data)

    async def add_comment(self, card_id: int, body: str) -> dict:
        return await self.post(Config.api(f"comments/story/{card_id}/"), {"comment": body})

    async def delete_comment(self, story_id: int, comment_id: int) -> int:
        return await self.delete(Config.api(f"comments/story/{story_id}/comment/{comment_id}/"))

    # ── Custom fields ──────────────────────────────────────────────────────────

    async def list_custom_fields(self, project_slug: str | None = None) -> list[dict]:
        slug = project_slug or Config.project
        data = await self.get(
            Config.api(f"organizations/{Config.org}/projects/{slug}/customfields/")
        )
        return data if isinstance(data, list) else data.get("customfields", data)

    async def get_card_customfields(self, story_id: int) -> list[dict]:
        """
        Fetch the full custom-fields array for a card.
        Returns [{"field": {id, name, ...}, "value": "..."}, ...]
        """
        data = await self.get(Config.project_url(f"stories/{story_id}/customfields"))
        return data if isinstance(data, list) else data.get("customfields", data)

    async def set_custom_field(self, card_ref: str, field_id: int, value: str) -> dict:
        """
        Sets a single custom field on a card using the dedicated customfields endpoint.
        Fetches the full array, mutates the matching entry, and PUTs the whole array back.
        """
        story_id = await self._resolve_card_id(card_ref)
        fields = await self.get_card_customfields(story_id)
        for entry in fields:
            if entry.get("field", {}).get("id") == field_id:
                entry["value"] = value
                break
        else:
            raise ValueError(
                f"Field id={field_id} not found on card {card_ref!r}. "
                "Use list_custom_fields() to get valid field ids."
            )
        return await self.put(
            Config.project_url(f"stories/{story_id}/customfields"),
            fields,
        )

    # ── Blockers ───────────────────────────────────────────────────────────────

    async def list_blockers(self, card_ref: str) -> list[dict]:
        story_id = await self._resolve_card_id(card_ref)
        data = await self.get(Config.project_url(f"stories/{story_id}/blockers/blocker/"))
        return data if isinstance(data, list) else data.get("blockers", data)

    async def block_card(self, card_ref: str, body: dict[str, Any]) -> dict:
        story_id = await self._resolve_card_id(card_ref)
        return await self.post(Config.project_url(f"stories/{story_id}/blockers/"), body)

    async def unblock_card(self, card_ref: str, blocker_id: int, body: dict[str, Any]) -> dict:
        story_id = await self._resolve_card_id(card_ref)
        return await self.put(Config.project_url(f"stories/{story_id}/blockers/{blocker_id}/"), body)

    # ── Members ────────────────────────────────────────────────────────────────

    async def list_members(self, project_slug: str | None = None) -> list[dict]:
        slug = project_slug or Config.project
        data = await self.get(
            Config.api(f"organizations/{Config.org}/projects/{slug}/members/")
        )
        return data if isinstance(data, list) else data.get("members", data)

    # ── Iterations ─────────────────────────────────────────────────────────────

    async def list_iterations(self) -> list[dict]:
        data = await self.get(Config.project_url("iterations/"))
        return data if isinstance(data, list) else data.get("iterations", data)

    # ── Epics ──────────────────────────────────────────────────────────────────

    async def list_epics(self) -> list[dict]:
        data = await self.get(Config.project_url("epics/"))
        return data if isinstance(data, list) else data.get("epics", data)

    # ── Labels ─────────────────────────────────────────────────────────────────

    async def list_labels(self) -> list[dict]:
        data = await self.get(Config.project_url("labels/"))
        return data if isinstance(data, list) else data.get("labels", data)

    # ── Webhooks ───────────────────────────────────────────────────────────────

    async def list_webhooks(self) -> list[dict]:
        data = await self.get(Config.project_url("webhooks/"))
        return data if isinstance(data, list) else data.get("webhooks", data)

    async def create_webhook(self, body: dict[str, Any]) -> dict:
        return await self.post(Config.project_url("webhooks/"), body)

    async def delete_webhook(self, webhook_id: int) -> int:
        return await self.delete(Config.project_url(f"webhooks/{webhook_id}/"))

    # ── Search ─────────────────────────────────────────────────────────────────

    async def search(self, query: str) -> list[dict]:
        data = await self.get(Config.org_url("search/"), q=query)
        if isinstance(data, list):
            return data
        # org search endpoint returns paginated {"items": [...], "count": N, ...}
        return data.get("items", data.get("results", []))

    # ── Time entries ───────────────────────────────────────────────────────────

    async def list_time_entries(self, card_ref: str | None = None) -> list[dict]:
        if card_ref:
            story_id = await self._resolve_card_id(card_ref)
            url = Config.project_url(f"stories/{story_id}/time_entries/")
        else:
            url = Config.project_url("time_entries/")
        data = await self.get(url)
        return data if isinstance(data, list) else data.get("time_entries", data)

    async def log_time(self, card_ref: str, body: dict[str, Any]) -> dict:
        story_id = await self._resolve_card_id(card_ref)
        return await self.post(Config.project_url(f"stories/{story_id}/time_entries/"), body)
