# BlackBoard/src/memory/knowledge_graph.py
# @ai-rules:
# 1. [Constraint]: Uses neo4j async driver (bolt://). Justified waiver of HTTP-only precedent.
# 2. [Pattern]: Lazy init via _ensure_initialized(). Never block import or construction.
# 3. [Pattern]: All public methods fail-open (try/except, log warning, return empty). Never raises.
# 4. [Gotcha]: Memgraph is bolt-compatible but has no APOC/GDS. Use pure Cypher only.
# 5. [Constraint]: Node identity via MERGE on natural keys (name for Service, event_id for Event).
# 6. [Pattern]: Labels/relationship types/depth can't be parameterized by the bolt driver, so every
#    f-string-built label, type, or depth MUST be validated against `_VALID_LABEL_RE` (or the depth
#    bound) before it reaches session.run() -- this applies to ALL public methods, not just upsert.
# 7. [Gotcha]: Entity/Relationship inputs may be pydantic BaseModel instances or plain dicts. Use
#    `_field()` for attribute access -- BaseModel has no `.get()`, so `getattr(x, n, None) or
#    x.get(n, d)` raises AttributeError the moment a real attribute is present but falsy.
"""
Async Knowledge Graph adapter for Memgraph (bolt://).

Stores entity relationships extracted from archived events. Fail-open:
all errors logged, never raised. Memgraph unavailability does not block
event closure or archival.
"""
from __future__ import annotations

import logging
import os
import re
from typing import Any

logger = logging.getLogger(__name__)

MEMGRAPH_URL = os.getenv("MEMGRAPH_URL", "bolt://memgraph:7687")
MEMGRAPH_USER = os.getenv("MEMGRAPH_USER", "")
MEMGRAPH_PASSWORD = os.getenv("MEMGRAPH_PASSWORD", "")

_VALID_LABEL_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_MAX_TRAVERSAL_DEPTH = 10


def _field(obj: Any, name: str, default: Any = None) -> Any:
    """Duck-type field access for either a pydantic model or a plain dict."""
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


class KnowledgeGraphStore:
    """Async Memgraph client using neo4j bolt driver."""

    def __init__(self, url: str = MEMGRAPH_URL):
        self._url = url
        self._driver = None
        self._initialized = False

    async def _ensure_initialized(self) -> bool:
        if self._initialized:
            return True
        try:
            from neo4j import AsyncGraphDatabase

            auth = (MEMGRAPH_USER, MEMGRAPH_PASSWORD) if MEMGRAPH_USER else None
            self._driver = AsyncGraphDatabase.driver(self._url, auth=auth)
            self._initialized = True
            logger.info("KnowledgeGraphStore initialized (url=%s, auth=%s)", self._url, bool(auth))
            return True
        except Exception as e:
            logger.warning("KnowledgeGraphStore init failed (non-fatal): %s", e)
            return False

    async def close(self) -> None:
        if self._driver:
            await self._driver.close()
            self._driver = None
            self._initialized = False

    async def upsert_entities(
        self,
        entities: list[Any],
        relationships: list[Any],
    ) -> None:
        """MERGE entities and relationships into the graph. Idempotent."""
        try:
            if not await self._ensure_initialized():
                return

            async with self._driver.session() as session:
                for entity in entities:
                    etype = _field(entity, "type", "Node")
                    eid = _field(entity, "id", "")
                    props = _field(entity, "properties", {}) or {}

                    if not _VALID_LABEL_RE.match(etype):
                        logger.warning("Skipping entity with invalid label: %s", etype)
                        continue

                    cypher = (
                        f"MERGE (n:{etype} {{id: $id}}) "
                        "ON CREATE SET n += $props, n.created_at = timestamp() "
                        "ON MATCH SET n += $props, n.last_seen = timestamp()"
                    )
                    await session.run(cypher, id=eid, props=props)

                for rel in relationships:
                    from_type = _field(rel, "from_type", "Node")
                    from_id = _field(rel, "from_id", "")
                    rel_type = _field(rel, "rel_type", "RELATED_TO")
                    to_type = _field(rel, "to_type", "Node")
                    to_id = _field(rel, "to_id", "")

                    if not all(_VALID_LABEL_RE.match(label) for label in (from_type, to_type, rel_type)):
                        logger.warning("Skipping relationship with invalid labels: %s->%s->%s", from_type, rel_type, to_type)
                        continue

                    cypher = (
                        f"MATCH (a:{from_type} {{id: $from_id}}) "
                        f"MATCH (b:{to_type} {{id: $to_id}}) "
                        f"MERGE (a)-[r:{rel_type}]->(b) "
                        "ON CREATE SET r.created_at = timestamp() "
                        "ON MATCH SET r.last_seen = timestamp()"
                    )
                    await session.run(
                        cypher, from_id=from_id, to_id=to_id,
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
        """Find entities related to a given node up to `depth` hops."""
        try:
            if not isinstance(entity_type, str) or not _VALID_LABEL_RE.match(entity_type):
                logger.warning("Rejecting query_related with invalid label: %s", entity_type)
                return []
            if not isinstance(depth, int) or isinstance(depth, bool) or not 1 <= depth <= _MAX_TRAVERSAL_DEPTH:
                logger.warning("Rejecting query_related with invalid depth: %s", depth)
                return []

            if not await self._ensure_initialized():
                return []

            cypher = (
                f"MATCH (n:{entity_type} {{id: $id}})-[r*1..{depth}]-(m) "
                "RETURN DISTINCT labels(m) AS labels, m.id AS id, properties(m) AS props"
            )
            async with self._driver.session() as session:
                result = await session.run(cypher, id=entity_id)
                records = [record.data() async for record in result]

            return records
        except Exception as e:
            logger.warning("Knowledge graph query failed (non-fatal): %s", e)
            return []

    async def has_entity(self, entity_type: str, entity_id: str) -> bool:
        """Check if an entity exists in the graph."""
        try:
            if not isinstance(entity_type, str) or not _VALID_LABEL_RE.match(entity_type):
                logger.warning("Rejecting has_entity with invalid label: %s", entity_type)
                return False

            if not await self._ensure_initialized():
                return False

            cypher = f"MATCH (n:{entity_type} {{id: $id}}) RETURN count(n) AS cnt"
            async with self._driver.session() as session:
                result = await session.run(cypher, id=entity_id)
                record = await result.single()
                return record and record["cnt"] > 0
        except Exception as e:
            logger.warning("Knowledge graph has_entity failed (non-fatal): %s", e)
            return False

    async def health_check(self) -> bool:
        """Verify Memgraph is reachable."""
        try:
            if not await self._ensure_initialized():
                return False

            async with self._driver.session() as session:
                result = await session.run("RETURN 1 AS ok")
                record = await result.single()
                return record is not None and record["ok"] == 1
        except Exception as e:
            logger.warning("Knowledge graph health check failed: %s", e)
            return False
