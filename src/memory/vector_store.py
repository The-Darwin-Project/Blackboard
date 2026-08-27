# BlackBoard/src/memory/vector_store.py
# @ai-rules:
# 1. [Constraint]: Uses httpx only (no qdrant-client pip package). Qdrant REST API at QDRANT_URL.
# 2. [Pattern]: All methods are async. Caller handles exceptions.
# 3. [Gotcha]: ensure_collection is idempotent -- safe to call on every startup.
# 4. [Pattern]: vector_size=768 for text-embedding-005 model.
# 5. [Pattern]: scroll() returns (points, next_offset) tuple for cursor-based pagination.
#    next_offset is an OPAQUE string -- str offsets pass through unchanged, non-str offsets
#    (int, dict) are json.dumps'd. Callers must treat it as opaque and pass it back verbatim
#    as the next call's `offset` -- never parse or construct it manually.
# 6. [Pattern]: get_points() retrieves by ID list. delete() removes by ID list. Both follow Qdrant REST conventions.
# 7. [Pattern]: search() accepts optional keyword-only `filter` dict (Qdrant filter DSL). Passed as sibling key in request body.
# 8. [Pattern]: create_payload_index() is idempotent -- 409 means index already exists (same as ensure_collection).
# 9. [Pattern]: scroll() also accepts optional keyword-only `filter` dict (same DSL as search()) to constrain pages
#    by indexed payload fields.
"""
Thin async wrapper around Qdrant REST API.
No additional pip dependencies -- uses httpx (already installed).
"""
from __future__ import annotations

import json
import logging
import os
from typing import Any

import httpx

logger = logging.getLogger(__name__)

QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")


def _encode_cursor(next_page_offset: Any) -> str | None:
    """Encode Qdrant's raw next_page_offset as an opaque string cursor.

    str offsets (the common case -- uuid5 point IDs) pass through unchanged.
    Non-str offsets (int point IDs, or an unexpected compound offset object)
    are json.dumps'd so the cursor stays a plain string over REST.
    """
    if next_page_offset is None:
        return None
    if isinstance(next_page_offset, str):
        return next_page_offset
    return json.dumps(next_page_offset)


def _decode_cursor(cursor: str | None) -> Any:
    """Decode an opaque cursor back to the value Qdrant expects as `offset`.

    Mirrors _encode_cursor: attempts json.loads first (recovers non-str
    offsets); falls back to the raw string when it isn't valid JSON (the
    common case -- a uuid5 point ID is never valid JSON).
    """
    if cursor is None:
        return None
    try:
        return json.loads(cursor)
    except Exception:
        return cursor


class VectorStore:
    """Async Qdrant client using REST API."""

    def __init__(self, base_url: str = QDRANT_URL):
        self.base_url = base_url.rstrip("/")
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(base_url=self.base_url, timeout=30.0)
        return self._client

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    async def ensure_collection(self, name: str, vector_size: int = 768) -> None:
        """Create collection if it doesn't exist. Idempotent."""
        client = await self._get_client()
        # Check if exists
        resp = await client.get(f"/collections/{name}")
        if resp.status_code == 200:
            return
        # Create
        resp = await client.put(
            f"/collections/{name}",
            json={
                "vectors": {
                    "size": vector_size,
                    "distance": "Cosine",
                },
            },
        )
        if resp.status_code in (200, 409):  # 409 = already exists (race)
            logger.info(f"Collection '{name}' ready (vector_size={vector_size})")
        else:
            resp.raise_for_status()

    async def upsert(
        self,
        collection: str,
        point_id: str,
        vector: list[float],
        payload: dict[str, Any],
    ) -> None:
        """Store a vector + metadata payload."""
        client = await self._get_client()
        resp = await client.put(
            f"/collections/{collection}/points",
            json={
                "points": [
                    {
                        "id": point_id,
                        "vector": vector,
                        "payload": payload,
                    }
                ]
            },
        )
        resp.raise_for_status()

    async def search(
        self,
        collection: str,
        vector: list[float],
        limit: int = 5,
        *,
        filter: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Similarity search. Returns list of {id, score, payload}."""
        client = await self._get_client()
        body: dict[str, Any] = {
            "vector": vector,
            "limit": limit,
            "with_payload": True,
        }
        if filter is not None:
            body["filter"] = filter
        resp = await client.post(
            f"/collections/{collection}/points/search",
            json=body,
        )
        resp.raise_for_status()
        results = resp.json().get("result", [])
        return [
            {
                "id": r.get("id"),
                "score": r.get("score", 0),
                "payload": r.get("payload", {}),
            }
            for r in results
        ]

    async def create_payload_index(
        self,
        collection: str,
        field_name: str,
        field_schema: str,
    ) -> None:
        """Create a payload field index. Idempotent -- 409 means already exists."""
        client = await self._get_client()
        resp = await client.put(
            f"/collections/{collection}/index",
            json={"field_name": field_name, "field_schema": field_schema},
        )
        if resp.status_code in (200, 409):
            logger.info(f"Payload index '{field_name}' ready on '{collection}'")
            return
        resp.raise_for_status()

    async def scroll(
        self,
        collection: str,
        limit: int = 100,
        offset: str | None = None,
        *,
        filter: dict[str, Any] | None = None,
    ) -> tuple[list[dict[str, Any]], str | None]:
        """List points in a collection (cursor-based pagination).

        `offset` is the opaque cursor returned as `next_offset` by a prior call --
        pass it back verbatim. `filter` uses the same Qdrant filter DSL as search().

        Returns (points, next_offset). next_offset is None when no more pages.
        """
        client = await self._get_client()
        body: dict[str, Any] = {"limit": limit, "with_payload": True}
        decoded_offset = _decode_cursor(offset)
        if decoded_offset is not None:
            body["offset"] = decoded_offset
        if filter is not None:
            body["filter"] = filter
        resp = await client.post(
            f"/collections/{collection}/points/scroll",
            json=body,
        )
        resp.raise_for_status()
        data = resp.json().get("result", {})
        points = [
            {"id": p.get("id"), "payload": p.get("payload", {})}
            for p in data.get("points", [])
        ]
        return points, _encode_cursor(data.get("next_page_offset"))

    async def get_points(
        self,
        collection: str,
        point_ids: list[str],
    ) -> list[dict[str, Any]]:
        """Retrieve specific points by ID. Returns list of {id, payload}."""
        client = await self._get_client()
        resp = await client.post(
            f"/collections/{collection}/points",
            json={"ids": point_ids, "with_payload": True},
        )
        resp.raise_for_status()
        results = resp.json().get("result", [])
        return [
            {"id": r.get("id"), "payload": r.get("payload", {})}
            for r in results
        ]

    async def delete(
        self,
        collection: str,
        point_ids: list[str],
    ) -> None:
        """Delete points by ID list."""
        client = await self._get_client()
        resp = await client.post(
            f"/collections/{collection}/points/delete",
            json={"points": point_ids},
        )
        resp.raise_for_status()
