# BlackBoard/src/routes/cognitive_graph.py
# @ai-rules:
# 1. [Constraint]: Read-only endpoints. No mutations to Qdrant or Redis heat counters.
# 2. [Pattern]: Returns 503 when PulseTracker or Archivist unavailable (feature flag off).
# 3. [Pattern]: /api/cognitive-graph merges Qdrant neurons with Redis heat counters.
# 4. [Pattern]: /api/pulses filters by event_id or since timestamp.
# 5. [Pattern]: /api/cortex/shadow endpoints read shadow intervention logs from Redis LIST keys.
"""
Cognitive Graph REST API.

Provides endpoints for the Cortex UI to load the neural topology
(Qdrant neurons + heat counters) and query pulse history.
"""
from __future__ import annotations

import logging
import time

from fastapi import APIRouter, HTTPException, Query
from typing import Optional

from ..dependencies import get_archivist, get_pulse_tracker

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["cognitive-graph"])


@router.get("/cognitive-graph")
async def get_cognitive_graph():
    """Load all neurons (lessons + memories) with heat counters for initial graph render."""
    try:
        archivist = await get_archivist()
    except RuntimeError:
        raise HTTPException(503, "Archivist not available")

    pulse_tracker = await get_pulse_tracker()
    heat = await pulse_tracker.get_heat() if pulse_tracker else {}

    lessons = await archivist.list_lessons(limit=500)
    memories = await archivist.list_memories(limit=500)

    neurons = []
    for p in lessons:
        nid = f"lesson:{p.get('id', '')}"
        neurons.append({
            "id": nid,
            "type": "lesson",
            "payload": p.get("payload", {}),
            "heat": heat.get(nid, 0),
        })
    for p in memories:
        nid = f"memory:{p.get('id', '')}"
        neurons.append({
            "id": nid,
            "type": "memory",
            "payload": p.get("payload", {}),
            "heat": heat.get(nid, 0),
        })

    return {"neurons": neurons, "total": len(neurons)}


@router.get("/pulses")
async def get_pulses(
    event_id: Optional[str] = Query(None, description="Filter by event ID"),
    since: Optional[float] = Query(None, description="Unix timestamp -- return pulses after this time"),
    limit: int = Query(200, ge=1, le=1000),
):
    """Query pulse log history, optionally filtered by event or time window."""
    pulse_tracker = await get_pulse_tracker()
    if not pulse_tracker:
        raise HTTPException(503, "PulseTracker not enabled (PULSE_TRACKING_ENABLED=false)")

    since_id = None
    if since:
        since_ms = int(since * 1000)
        since_id = f"{since_ms}-0"

    batches = await pulse_tracker.get_batches(
        event_id=event_id,
        since=since_id,
        count=limit,
    )
    return {"batches": batches, "count": len(batches)}


# =============================================================================
# Cortex Shadow Endpoints (System 2 shadow mode interventions)
# =============================================================================

SHADOW_KEY_PREFIX = "darwin:cortex:shadow:"


@router.get("/cortex/shadow")
async def get_all_shadow_interventions(
    limit: int = Query(50, ge=1, le=500),
):
    """Return recent shadow interventions across all events."""
    from ..dependencies import get_blackboard
    try:
        blackboard = await get_blackboard()
    except RuntimeError:
        raise HTTPException(503, "Blackboard not available")
    redis = blackboard.redis

    import json as _json
    index_key = f"{SHADOW_KEY_PREFIX}_index"
    event_ids = await redis.smembers(index_key)
    all_entries: list[dict] = []
    for event_id in event_ids:
        eid = event_id if isinstance(event_id, str) else event_id.decode()
        raw_items = await redis.lrange(f"{SHADOW_KEY_PREFIX}{eid}", -limit, -1)
        for raw in raw_items:
            try:
                entry = _json.loads(raw)
                entry["event_id"] = eid
                all_entries.append(entry)
            except Exception:
                pass

    all_entries.sort(key=lambda e: e.get("timestamp", 0), reverse=True)
    return {"interventions": all_entries[:limit], "count": len(all_entries[:limit])}


@router.get("/cortex/shadow/{event_id}")
async def get_event_shadow_interventions(
    event_id: str,
    limit: int = Query(50, ge=1, le=500),
):
    """Return shadow interventions for a specific event."""
    from ..dependencies import get_blackboard
    try:
        blackboard = await get_blackboard()
    except RuntimeError:
        raise HTTPException(503, "Blackboard not available")
    redis = blackboard.redis

    import json as _json
    key = f"{SHADOW_KEY_PREFIX}{event_id}"
    raw_items = await redis.lrange(key, -limit, -1)
    entries = []
    for raw in raw_items:
        try:
            entry = _json.loads(raw)
            entry["event_id"] = event_id
            entries.append(entry)
        except Exception:
            pass
    return {"interventions": entries, "count": len(entries)}
