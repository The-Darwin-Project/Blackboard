# BlackBoard/src/routes/knowledge_graph_api.py
# @ai-rules:
# 1. [Constraint]: Read-only endpoints. No require_auth (matches /topology/graph pattern).
# 2. [Pattern]: Fail-open — returns [] or {} when KG store is unavailable, never 503.
# 3. [Pattern]: Uses get_kg_store() dependency from dependencies.py.
# 4. [Constraint]: list_services + get_service_detail delegate to KGStore methods (no raw SQL here).
"""
Knowledge Graph REST API.

Exposes Postgres-backed KG service entities and relationship data
for the Cortex UI's Knowledge Ring integration.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException

from ..dependencies import get_kg_store

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/knowledge-graph", tags=["knowledge-graph"])


@router.get("/services")
async def list_services():
    """List Service entities from the Knowledge Graph (last 7 days)."""
    store = await get_kg_store()
    if not store:
        return []
    services = await store.list_services()
    return [
        {
            "entity_id": s["entity_id"],
            "properties": s.get("properties") or {},
            "last_seen": str(s.get("last_seen", "")),
            "relationship_count": s.get("relationship_count", 0),
        }
        for s in services
    ]


@router.get("/services/{entity_id}")
async def get_service_detail(entity_id: str):
    """Get a single service with all its relationships."""
    store = await get_kg_store()
    if not store:
        raise HTTPException(404, "Knowledge Graph not available")
    detail = await store.get_service_detail(entity_id)
    if not detail:
        raise HTTPException(404, f"Service '{entity_id}' not found")
    rels = []
    for r in detail.get("relationships", []):
        rels.append({
            "rel_type": r.get("rel_type", ""),
            "entity_type": r.get("entity_type", ""),
            "entity_id": r.get("entity_id", ""),
            "direction": "outgoing" if r.get("entity_type") != "Service" else "incoming",
            "properties": r.get("properties") or {},
        })
    return {
        "entity_id": detail["entity_id"],
        "properties": detail.get("properties") or {},
        "last_seen": detail.get("last_seen", ""),
        "relationships": rels,
    }


@router.get("/stats")
async def get_stats():
    """Aggregate counts by entity type and relationship type."""
    store = await get_kg_store()
    if not store:
        return {"entities": {}, "relationships": {}, "last_updated": None}
    return await store.get_stats()
