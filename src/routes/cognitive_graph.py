# BlackBoard/src/routes/cognitive_graph.py
# @ai-rules:
# 1. [Constraint]: Read-only endpoints. No mutations to Qdrant or Redis heat counters.
# 2. [Pattern]: Returns 503 when PulseTracker or Archivist unavailable (feature flag off).
# 3. [Pattern]: /api/cognitive-graph merges Qdrant neurons with Redis heat counters.
# 4. [Pattern]: /api/pulses filters by event_id or since timestamp.
# 5. [Pattern]: /api/cortex/shadow endpoints read shadow intervention logs from Redis LIST keys.
# 6. [Pattern]: /api/cortex/status reads live_adapter from app.state for UI hydration on mount.
# 7. [Pattern]: /api/cortex/handoff-reports and /api/cortex/proposals read from Redis LIST keys
#    (darwin:cortex:handoff_reports, darwin:cortex:proposals). JSON-parsed, tolerant of bad entries.
"""
Cognitive Graph REST API.

Provides endpoints for the Cortex UI to load the neural topology
(Qdrant neurons + heat counters) and query pulse history.
"""
from __future__ import annotations

import json
import logging
import time

from fastapi import APIRouter, HTTPException, Query, Request
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
    knowledge = await archivist.list_knowledge(limit=500) if hasattr(archivist, "list_knowledge") else []

    neurons = []
    for p in lessons:
        nid = f"lesson:{p.get('id', '')}"
        payload = p.get("payload", {})
        title = payload.get("title", "")
        channel = payload.get("channel", "")
        label = f"{title} [{channel}]" if title and channel else title
        neurons.append({
            "id": nid,
            "type": "lesson",
            "label": label,
            "payload": payload,
            "heat": heat.get(nid, 0),
        })
    for p in memories:
        nid = f"memory:{p.get('id', '')}"
        payload = p.get("payload", {})
        symptom = payload.get("symptom", "")
        service = payload.get("service", "")
        label = f"{service}: {symptom}" if service and symptom else symptom
        neurons.append({
            "id": nid,
            "type": "memory",
            "label": label,
            "payload": payload,
            "heat": heat.get(nid, 0),
        })
    for p in knowledge:
        nid = f"knowledge:{p.get('id', '')}"
        payload = p.get("payload", {})
        topic = payload.get("topic", "")
        scope = payload.get("scope", "")
        label = f"{topic} [{scope}]" if topic and scope else topic
        neurons.append({
            "id": nid,
            "type": "knowledge",
            "label": label,
            "payload": payload,
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


@router.get("/cortex/activity")
async def get_cortex_activity(
    event_id: Optional[str] = Query(None, description="Filter by event ID"),
    limit: int = Query(50, ge=1, le=500),
):
    """Return recent pulse batches for UI backfill on mount/reconnect."""
    pulse_tracker = await get_pulse_tracker()
    if not pulse_tracker:
        raise HTTPException(503, "PulseTracker not enabled (PULSE_TRACKING_ENABLED=false)")

    batches = await pulse_tracker.get_batches(
        event_id=event_id,
        count=limit,
        latest=True,
    )
    return {"batches": batches, "count": len(batches)}


@router.get("/cortex/status")
async def get_cortex_status(request: Request):
    """Return current JARVIS session state so UI can hydrate on mount."""
    live_adapter = getattr(request.app.state, "live_adapter", None)
    if not live_adapter:
        return {"status": "disabled", "model": None, "shadow": None, "last_pulse_time": None}
    return {
        "status": "watching" if live_adapter._session else "disconnected",
        "model": live_adapter._model,
        "shadow": live_adapter._shadow,
        "last_pulse_time": live_adapter._last_pulse_time or None,
    }


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

    index_key = f"{SHADOW_KEY_PREFIX}_index"
    event_ids = await redis.smembers(index_key)
    all_entries: list[dict] = []
    for event_id in event_ids:
        eid = event_id if isinstance(event_id, str) else event_id.decode()
        raw_items = await redis.lrange(f"{SHADOW_KEY_PREFIX}{eid}", -limit, -1)
        for raw in raw_items:
            try:
                entry = json.loads(raw)
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

    key = f"{SHADOW_KEY_PREFIX}{event_id}"
    raw_items = await redis.lrange(key, -limit, -1)
    entries = []
    for raw in raw_items:
        try:
            entry = json.loads(raw)
            entry["event_id"] = event_id
            entries.append(entry)
        except Exception:
            pass
    return {"interventions": entries, "count": len(entries)}


# =============================================================================
# JARVIS Memory Endpoints (handoff reports + proposals)
# =============================================================================

@router.get("/cortex/handoff-reports")
async def get_handoff_reports(limit: int = 100):
    """Return accumulated JARVIS session handoff reports from Redis."""
    from ..dependencies import get_blackboard
    try:
        blackboard = await get_blackboard()
    except RuntimeError:
        raise HTTPException(503, "Blackboard not available")
    redis = blackboard.redis
    raw = await redis.lrange("darwin:cortex:handoff_reports", -limit, -1)
    reports = []
    for entry in raw:
        try:
            reports.append(json.loads(entry))
        except (json.JSONDecodeError, TypeError):
            continue
    reports.sort(key=lambda r: r.get("timestamp", 0), reverse=True)
    return {"reports": reports, "count": len(reports)}


@router.get("/cortex/proposals")
async def get_proposals(limit: int = 100):
    """Return JARVIS enhancement proposals from Redis.

    Proposals have no TTL (intentional) -- they persist until explicitly
    dismissed by an operator or converted to events.
    """
    from ..dependencies import get_blackboard
    try:
        blackboard = await get_blackboard()
    except RuntimeError:
        raise HTTPException(503, "Blackboard not available")
    redis = blackboard.redis
    raw = await redis.lrange("darwin:cortex:proposals", -limit, -1)
    proposals = []
    for entry in raw:
        try:
            proposals.append(json.loads(entry))
        except (json.JSONDecodeError, TypeError):
            continue
    proposals.sort(key=lambda r: r.get("timestamp", 0), reverse=True)
    return {"proposals": proposals, "count": len(proposals)}
