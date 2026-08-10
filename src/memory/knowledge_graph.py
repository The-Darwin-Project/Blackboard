# BlackBoard/src/memory/knowledge_graph.py
# @ai-rules:
# 1. [Constraint]: Uses asyncpg for Postgres. Adjacency table model (kg_entities + kg_relationships).
# 2. [Pattern]: Lazy init via _ensure_initialized(). Creates tables on first use (idempotent DDL).
# 3. [Pattern]: All public methods fail-open (try/except, log warning, return empty). Never raises.
# 4. [Constraint]: Node identity via INSERT ON CONFLICT UPDATE on natural keys.
# 5. [Pattern]: Parameterized queries only. Never string-interpolate user data into SQL.
"""
Async Knowledge Graph adapter for Postgres (adjacency tables).

Stores entity relationships extracted from archived events. Fail-open:
all errors logged, never raised. Postgres unavailability does not block
event closure or archival.
"""
from __future__ import annotations

import logging
import os
import re
from typing import Any

logger = logging.getLogger(__name__)

KG_POSTGRES_URL = os.getenv("KG_POSTGRES_URL", "")

_VALID_ENTITY_TYPE_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

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

    async def _ensure_initialized(self) -> bool:
        if self._initialized:
            return True
        if not self._url:
            return False
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

            async with self._pool.acquire() as conn:
                for entity in entities:
                    etype = getattr(entity, "type", None) or entity.get("type", "Node")
                    eid = getattr(entity, "id", None) or entity.get("id", "")
                    props = getattr(entity, "properties", None) or entity.get("properties", {})

                    if not _VALID_ENTITY_TYPE_RE.match(etype):
                        logger.warning("Skipping entity with invalid type: %s", etype)
                        continue

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
                    from_id = getattr(rel, "from_id", None) or rel.get("from_id", "")
                    rel_type = getattr(rel, "rel_type", None) or rel.get("rel_type", "RELATED_TO")
                    to_type = getattr(rel, "to_type", None) or rel.get("to_type", "Node")
                    to_id = getattr(rel, "to_id", None) or rel.get("to_id", "")

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
        """Find entities related to a given node (1-hop by default)."""
        try:
            if not await self._ensure_initialized():
                return []

            async with self._pool.acquire() as conn:
                rows = await conn.fetch(
                    """
                    SELECT e.entity_type, e.entity_id, e.properties, r.rel_type
                    FROM kg_relationships r
                    JOIN kg_entities e ON (e.entity_type = r.to_entity_type AND e.entity_id = r.to_entity_id)
                    WHERE r.from_entity_type = $1 AND r.from_entity_id = $2
                    UNION
                    SELECT e.entity_type, e.entity_id, e.properties, r.rel_type
                    FROM kg_relationships r
                    JOIN kg_entities e ON (e.entity_type = r.from_entity_type AND e.entity_id = r.from_entity_id)
                    WHERE r.to_entity_type = $1 AND r.to_entity_id = $2
                    """,
                    entity_type, entity_id,
                )
                return [dict(row) for row in rows]
        except Exception as e:
            logger.warning("Knowledge graph query failed (non-fatal): %s", e)
            return []

    async def has_entity(self, entity_type: str, entity_id: str) -> bool:
        """Check if an entity exists."""
        try:
            if not await self._ensure_initialized():
                return False

            async with self._pool.acquire() as conn:
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

            async with self._pool.acquire() as conn:
                row = await conn.fetchrow("SELECT 1 AS ok")
                return row is not None and row["ok"] == 1
        except Exception as e:
            logger.warning("Knowledge graph health check failed: %s", e)
            return False
