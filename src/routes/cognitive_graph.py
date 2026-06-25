# BlackBoard/src/routes/cognitive_graph.py
# @ai-rules:
# 1. [Constraint]: Read-only endpoints EXCEPT proposal dismiss (operator lifecycle action).
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

import logging
import time

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from typing import Optional

from ..auth import UserContext, require_auth
from ..dependencies import get_archivist, get_brain, get_pulse_tracker

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

    try:
        brain = await get_brain()
        if brain and brain.skill_loader:
            skill_nodes = brain.skill_loader.list_skills_for_graph()
            for s in skill_nodes:
                nid = s["id"]
                neurons.append({
                    "id": nid,
                    "type": "skill",
                    "payload": {
                        "label": s["label"],
                        "phase_folder": s["phase_folder"],
                        "tag_type": s["tag_type"],
                    },
                    "heat": heat.get(nid, 0),
                })
    except Exception:
        logger.warning("Failed to load skill neurons for graph", exc_info=True)

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

    event_ids = await blackboard.get_shadow_event_ids()
    all_entries: list[dict] = []
    for eid in event_ids:
        entries = await blackboard.get_shadow_interventions(eid, limit)
        all_entries.extend(entries)

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

    entries = await blackboard.get_shadow_interventions(event_id, limit)
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

    reports = await blackboard.get_handoff_reports(limit)
    return {"reports": reports, "count": len(reports)}



@router.get("/cortex/proposals")
async def get_proposals(limit: int = 100, include_dismissed: bool = False):
    """Return JARVIS enhancement proposals from Redis.

    Proposals have no TTL (intentional) -- they persist until explicitly
    dismissed by an operator or converted to events.
    """
    from ..dependencies import get_blackboard
    try:
        blackboard = await get_blackboard()
    except RuntimeError:
        raise HTTPException(503, "Blackboard not available")

    proposals = await blackboard.get_proposals(limit, include_dismissed)
    return {"proposals": proposals, "count": len(proposals)}


class DismissRequest(BaseModel):
    timestamps: list[float] = Field(..., min_length=1)
    reason: str | None = None


@router.post("/cortex/proposals/dismiss")
async def dismiss_proposals(body: DismissRequest, user: UserContext = Depends(require_auth)):
    """Mark proposals as dismissed by timestamp.

    Dismissed proposals are filtered from GET by default (use ?include_dismissed=true to see them).
    """
    from ..dependencies import get_blackboard
    try:
        blackboard = await get_blackboard()
    except RuntimeError:
        raise HTTPException(503, "Blackboard not available")
    count = await blackboard.dismiss_proposals(body.timestamps)
    logger.info("Proposals dismissed by %s: %d proposals", user.email, count)
    return {"dismissed": count}
