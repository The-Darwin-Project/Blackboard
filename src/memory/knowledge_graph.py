# BlackBoard/src/memory/knowledge_graph.py
# @ai-rules:
# 1. [Constraint]: Uses asyncpg for Postgres. Adjacency table model (kg_entities + kg_relationships).
# 2. [Pattern]: Lazy init via _ensure_initialized(). Creates tables on first use (idempotent DDL).
# 3. [Pattern]: All public methods fail-open (try/except, log warning, return empty). Never raises.
# 4. [Constraint]: Node identity via INSERT ON CONFLICT UPDATE on natural keys.
# 5. [Pattern]: Parameterized queries only. Never string-interpolate user data into SQL.
# 6. [Pattern]: Service entity resolution (_resolve_service_id) — fuzzy ILIKE match on bare name,
#    ranked by relationship count. Belt: read path resolves before query. Suspenders: write path
#    resolves before upsert, rewrites relationship IDs via resolved_ids map.
"""
Async Knowledge Graph adapter for Postgres (adjacency tables).

Stores entity relationships extracted from archived events. Fail-open:
all errors logged, never raised. Postgres unavailability does not block
event closure or archival.
"""
from __future__ import annotations

import asyncio
import logging
import os
import re
from typing import Any

logger = logging.getLogger(__name__)

KG_POSTGRES_URL = os.getenv("KG_POSTGRES_URL", "")

_VALID_ENTITY_TYPE_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

# Pool max_size is 4, but up to MAX_ACTIVE_EVENTS (default 20) workers may
# call KG methods concurrently. Bound concurrent pool.acquire() waiters to
# 2x pool size so excess callers fail fast via the existing timeout wrappers
# instead of queuing unboundedly on pool contention.
_KG_SEMAPHORE = asyncio.Semaphore(8)

# Free-text entity/relationship fields originate from LLM extraction over
# agent output and are persisted with no TTL. graph_recall.py sanitizes on
# read, but that is the only current consumer of query_related -- any future
# reader would inherit unsanitized data. Strip tag-like sequences at write
# time too, as defense-in-depth (same _TAG_RE pattern as graph_recall.py).
_TAG_RE = re.compile(r"<[^>]+>")


def _sanitize(text: Any) -> str:
    """Strip tag-like sequences from a string before it is persisted."""
    if not isinstance(text, str):
        return "" if text is None else _TAG_RE.sub("", str(text))
    return _TAG_RE.sub("", text)


_SCHEMA_DDL = """
CREATE TABLE IF NOT EXISTS kg_entities (
    id SERIAL PRIMARY KEY,
    entity_type TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    properties JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    last_seen TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(entity_type, entity_id)
);

CREATE TABLE IF NOT EXISTS kg_relationships (
    id SERIAL PRIMARY KEY,
    from_entity_type TEXT NOT NULL,
    from_entity_id TEXT NOT NULL,
    rel_type TEXT NOT NULL,
    to_entity_type TEXT NOT NULL,
    to_entity_id TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    last_seen TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(from_entity_type, from_entity_id, rel_type, to_entity_type, to_entity_id)
);

CREATE INDEX IF NOT EXISTS idx_kg_entities_lookup ON kg_entities(entity_type, entity_id);
CREATE INDEX IF NOT EXISTS idx_kg_rel_from ON kg_relationships(from_entity_type, from_entity_id);
CREATE INDEX IF NOT EXISTS idx_kg_rel_to ON kg_relationships(to_entity_type, to_entity_id);
"""


class KnowledgeGraphStore:
    """Async Postgres knowledge graph using adjacency tables."""

    def __init__(self, url: str = ""):
        self._url = url or KG_POSTGRES_URL
        self._pool = None
        self._initialized = False
        self._init_lock: Any = None

    async def _ensure_initialized(self) -> bool:
        if self._initialized:
            return True
        if not self._url:
            return False
        if self._init_lock is None:
            self._init_lock = asyncio.Lock()
        async with self._init_lock:
            if self._initialized:
                return True
            try:
                import asyncpg

                self._pool = await asyncpg.create_pool(self._url, min_size=1, max_size=4)
                async with self._pool.acquire() as conn:
                    await conn.execute(_SCHEMA_DDL)
                self._initialized = True
                logger.info("KnowledgeGraphStore initialized (postgres)")
                return True
            except Exception as e:
                logger.warning("KnowledgeGraphStore init failed (non-fatal): %s", e)
                return False

    async def close(self) -> None:
        if self._pool:
            await self._pool.close()
            self._pool = None
            self._initialized = False

    async def upsert_entities(
        self,
        entities: list[Any],
        relationships: list[Any],
    ) -> None:
        """Upsert entities and relationships. Idempotent."""
        try:
            if not await self._ensure_initialized():
                return

            async with _KG_SEMAPHORE, self._pool.acquire() as conn:
                resolved_ids: dict[str, str] = {}
                for entity in entities:
                    etype = getattr(entity, "type", None) or entity.get("type", "Node")
                    eid = _sanitize(getattr(entity, "id", None) or entity.get("id", ""))
                    props = getattr(entity, "properties", None) or entity.get("properties", {})
                    props = {k: _sanitize(v) for k, v in props.items()}

                    if not _VALID_ENTITY_TYPE_RE.match(etype):
                        logger.warning("Skipping entity with invalid type: %s", etype)
                        continue

                    if etype == "Service":
                        canonical = await self._resolve_service_id(conn, eid)
                        if canonical != eid:
                            logger.debug("Write-time alias: %s -> %s", eid, canonical)
                            resolved_ids[eid] = canonical
                            eid = canonical

                    import json
                    await conn.execute(
                        """
                        INSERT INTO kg_entities (entity_type, entity_id, properties)
                        VALUES ($1, $2, $3::jsonb)
                        ON CONFLICT (entity_type, entity_id)
                        DO UPDATE SET properties = $3::jsonb, last_seen = NOW()
                        """,
                        etype, eid, json.dumps(props),
                    )

                for rel in relationships:
                    from_type = getattr(rel, "from_type", None) or rel.get("from_type", "Node")
                    from_id = _sanitize(getattr(rel, "from_id", None) or rel.get("from_id", ""))
                    rel_type = getattr(rel, "rel_type", None) or rel.get("rel_type", "RELATED_TO")
                    to_type = getattr(rel, "to_type", None) or rel.get("to_type", "Node")
                    to_id = _sanitize(getattr(rel, "to_id", None) or rel.get("to_id", ""))
                    if from_type == "Service":
                        from_id = resolved_ids.get(from_id, from_id)
                    if to_type == "Service":
                        to_id = resolved_ids.get(to_id, to_id)

                    if not all(_VALID_ENTITY_TYPE_RE.match(t) for t in (from_type, to_type, rel_type)):
                        logger.warning("Skipping relationship with invalid types: %s->%s->%s", from_type, rel_type, to_type)
                        continue

                    await conn.execute(
                        """
                        INSERT INTO kg_relationships (from_entity_type, from_entity_id, rel_type, to_entity_type, to_entity_id)
                        VALUES ($1, $2, $3, $4, $5)
                        ON CONFLICT (from_entity_type, from_entity_id, rel_type, to_entity_type, to_entity_id)
                        DO UPDATE SET last_seen = NOW()
                        """,
                        from_type, from_id, rel_type, to_type, to_id,
                    )

            logger.info(
                "Knowledge graph: wrote %d entities, %d relationships",
                len(entities), len(relationships),
            )
        except Exception as e:
            logger.warning("Knowledge graph upsert failed (non-fatal): %s", e)

    async def query_related(
        self,
        entity_type: str,
        entity_id: str,
        depth: int = 1,
    ) -> list[dict[str, Any]]:
        """Find entities related to a given node (1-hop by default).

        Uses exact match first; falls back to fuzzy resolution for Service
        entities when exact match yields no results (handles name variants
        like "Blackboard" vs "darwin-blackboard").
        """
        try:
            if not await self._ensure_initialized():
                return []

            async with _KG_SEMAPHORE, self._pool.acquire() as conn:
                resolved_id = entity_id
                if entity_type == "Service":
                    resolved_id = await self._resolve_service_id(conn, entity_id)

                rows = await conn.fetch(
                    """
                    SELECT e.entity_type, e.entity_id, e.properties, r.rel_type
                    FROM kg_relationships r
                    JOIN kg_entities e ON (e.entity_type = r.to_entity_type AND e.entity_id = r.to_entity_id)
                    WHERE r.from_entity_type = $1 AND r.from_entity_id = $2
                        AND e.last_seen > NOW() - INTERVAL '7 days'
                    UNION
                    SELECT e.entity_type, e.entity_id, e.properties, r.rel_type
                    FROM kg_relationships r
                    JOIN kg_entities e ON (e.entity_type = r.from_entity_type AND e.entity_id = r.from_entity_id)
                    WHERE r.to_entity_type = $1 AND r.to_entity_id = $2
                        AND e.last_seen > NOW() - INTERVAL '7 days'
                    """,
                    entity_type, resolved_id,
                )
                return [dict(row) for row in rows]
        except Exception as e:
            logger.warning("Knowledge graph query failed (non-fatal): %s", e)
            return []

    async def _resolve_service_id(
        self, conn: Any, entity_id: str,
    ) -> str:
        """Resolve a service entity_id to the canonical ID with the most relationships.

        Handles name variants: "service:Blackboard" may need to resolve to
        "service:darwin-blackboard" (seeded from Qdrant archives). Extracts the
        bare name from "service:<name>" and searches ILIKE for variants.
        Returns the variant with the most relationships, or the original ID
        if no better match exists.
        """
        bare = entity_id.removeprefix("service:").lower()
        if not bare:
            return entity_id

        row = await conn.fetchrow(
            "SELECT 1 FROM kg_entities WHERE entity_type = 'Service' AND entity_id = $1",
            entity_id,
        )
        if row:
            rel_count = await conn.fetchval(
                """
                SELECT count(*) FROM kg_relationships
                WHERE (from_entity_type = 'Service' AND from_entity_id = $1)
                   OR (to_entity_type = 'Service' AND to_entity_id = $1)
                """,
                entity_id,
            )
            if rel_count and rel_count >= 2:
                return entity_id

        candidates = await conn.fetch(
            """
            SELECT e.entity_id, count(r.id) as rel_count
            FROM kg_entities e
            LEFT JOIN kg_relationships r ON (
                (r.from_entity_type = 'Service' AND r.from_entity_id = e.entity_id)
                OR (r.to_entity_type = 'Service' AND r.to_entity_id = e.entity_id)
            )
            WHERE e.entity_type = 'Service'
              AND LOWER(e.entity_id) LIKE $1
            GROUP BY e.entity_id
            ORDER BY rel_count DESC
            LIMIT 1
            """,
            f"%{bare}%",
        )
        if candidates and candidates[0]["rel_count"] > 0:
            resolved = candidates[0]["entity_id"]
            if resolved != entity_id:
                logger.debug(
                    "Service resolution: %s -> %s (%d rels)",
                    entity_id, resolved, candidates[0]["rel_count"],
                )
            return resolved

        return entity_id

    async def has_entity(self, entity_type: str, entity_id: str) -> bool:
        """Check if an entity exists (with fuzzy resolution for Services)."""
        try:
            if not await self._ensure_initialized():
                return False

            async with _KG_SEMAPHORE, self._pool.acquire() as conn:
                if entity_type == "Service":
                    resolved = await self._resolve_service_id(conn, entity_id)
                    row = await conn.fetchrow(
                        "SELECT 1 FROM kg_entities WHERE entity_type = $1 AND entity_id = $2",
                        entity_type, resolved,
                    )
                else:
                    row = await conn.fetchrow(
                        "SELECT 1 FROM kg_entities WHERE entity_type = $1 AND entity_id = $2",
                        entity_type, entity_id,
                    )
                return row is not None
        except Exception as e:
            logger.warning("Knowledge graph has_entity failed (non-fatal): %s", e)
            return False

    async def health_check(self) -> bool:
        """Verify Postgres is reachable."""
        try:
            if not await self._ensure_initialized():
                return False

            async with _KG_SEMAPHORE, self._pool.acquire() as conn:
                row = await conn.fetchrow("SELECT 1 AS ok")
                return row is not None and row["ok"] == 1
        except Exception as e:
            logger.warning("Knowledge graph health check failed: %s", e)
            return False
