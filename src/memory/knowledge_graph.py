# BlackBoard/src/memory/knowledge_graph.py
# @ai-rules:
# 1. [Constraint]: Uses neo4j async driver (bolt://). Justified waiver of HTTP-only precedent.
# 2. [Pattern]: Lazy init via _ensure_initialized(). Never block import or construction.
# 3. [Pattern]: All public methods fail-open (try/except, log warning, return empty). Never raises.
# 4. [Gotcha]: Memgraph is bolt-compatible but has no APOC/GDS. Use pure Cypher only.
# 5. [Constraint]: Node identity via MERGE on natural keys (name for Service, event_id for Event).
# 6. [Pattern]: Parameterized Cypher queries only. Never string-interpolate user data into Cypher.
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

_VALID_LABEL_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


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

            self._driver = AsyncGraphDatabase.driver(self._url, auth=None)
            self._initialized = True
            logger.info("KnowledgeGraphStore initialized (url=%s)", self._url)
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
                    etype = getattr(entity, "type", None) or entity.get("type", "Node")
                    eid = getattr(entity, "id", None) or entity.get("id", "")
                    props = getattr(entity, "properties", None) or entity.get("properties", {})

                    if not _VALID_LABEL_RE.match(etype):
                        logger.warning("Skipping entity with invalid label: %s", etype)
                        continue

                    cypher = (
                        f"MERGE (n:{etype} {{id: $id}}) "
                        "ON CREATE SET n += $props, n.created_at = timestamp() "
                        "ON MATCH SET n += $props, n.last_seen = timestamp()"
                    )
                    await session.run(cypher, id=eid, props=props or {})

                for rel in relationships:
                    from_type = getattr(rel, "from_type", None) or rel.get("from_type", "Node")
                    from_id = getattr(rel, "from_id", None) or rel.get("from_id", "")
                    rel_type = getattr(rel, "rel_type", None) or rel.get("rel_type", "RELATED_TO")
                    to_type = getattr(rel, "to_type", None) or rel.get("to_type", "Node")
                    to_id = getattr(rel, "to_id", None) or rel.get("to_id", "")

                    if not all(_VALID_LABEL_RE.match(l) for l in (from_type, to_type, rel_type)):
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
