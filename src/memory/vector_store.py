# BlackBoard/src/memory/vector_store.py
# @ai-rules:
# 1. [Constraint]: Uses httpx only (no qdrant-client pip package). Qdrant REST API at QDRANT_URL.
# 2. [Pattern]: All methods are async. Caller handles exceptions.
# 3. [Gotcha]: ensure_collection is idempotent -- safe to call on every startup.
# 4. [Pattern]: vector_size=768 for text-embedding-005 model.
# 5. [Pattern]: scroll() returns (points, next_offset) tuple for cursor-based pagination.
# 6. [Pattern]: get_points() retrieves by ID list. delete() removes by ID list. Both follow Qdrant REST conventions.
"""
Thin async wrapper around Qdrant REST API.
No additional pip dependencies -- uses httpx (already installed).
"""
from __future__ import annotations

import logging
import os
from typing import Any

import httpx

logger = logging.getLogger(__name__)

QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")


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
    ) -> list[dict[str, Any]]:
        """Similarity search. Returns list of {id, score, payload}."""
        client = await self._get_client()
        resp = await client.post(
            f"/collections/{collection}/points/search",
            json={
                "vector": vector,
                "limit": limit,
                "with_payload": True,
            },
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

    async def scroll(
        self,
        collection: str,
        limit: int = 100,
        offset: str | None = None,
    ) -> tuple[list[dict[str, Any]], str | None]:
        """List all points in a collection (cursor-based pagination).

        Returns (points, next_offset). next_offset is None when no more pages.
        """
        client = await self._get_client()
        body: dict[str, Any] = {"limit": limit, "with_payload": True}
        if offset is not None:
            body["offset"] = offset
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
        return points, data.get("next_page_offset")

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
