# BlackBoard/src/routes/queue.py
# @ai-rules:
# 1. [Gotcha]: GET /closed/list MUST stay before GET /{event_id} to avoid "closed" matching as event_id.
# 2. [Pattern]: POST /{event_id}/close uses blackboard.close_event() -- same state machine as Brain.
# 3. [Gotcha]: Pre-existing route order issue -- closed/list is after /{event_id}. Works because /closed/list is 2 segments.
# 4. [Pattern]: GET /{event_id}/report uses Brain._event_to_markdown (staticmethod) -- no Brain instance needed.
"""
Conversation Queue API - Event document management.

Provides endpoints for the unified group chat UI to:
- List active events
- Get event conversation timeline
- Approve pending plans
- Force-close events
- View closed events
"""
from __future__ import annotations

import logging
import time

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from ..dependencies import get_blackboard, get_brain
from ..models import ConversationTurn, EventDocument, EventEvidence, EventStatus
from ..state.blackboard import BlackboardState


class RejectRequest(BaseModel):
    """Typed request body for plan rejection."""
    reason: str = Field("User rejected the plan.", description="Rejection reason")
    image: Optional[str] = Field(None, description="Base64 data URI of screenshot")

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/queue", tags=["queue"])


def _serialize_evidence(event: EventDocument) -> dict:
    """Serialize evidence to dict with fallback for legacy string evidence."""
    evidence_val = event.event.evidence
    if isinstance(evidence_val, EventEvidence):
        return evidence_val.model_dump()
    return {
        "display_text": str(evidence_val),
        "source_type": event.source,
        "domain": "complicated",
        "severity": "warning",
    }


@router.get("/active")
async def list_active_events(
    blackboard: BlackboardState = Depends(get_blackboard),
):
    """Get all active event IDs with basic metadata."""
    event_ids = await blackboard.get_active_events()
    events = []
    for eid in event_ids:
        event = await blackboard.get_event(eid)
        if event:
            events.append({
                "id": event.id,
                "source": event.source,
                "service": event.service,
                "status": event.status.value,
                "reason": event.event.reason,
                "evidence": _serialize_evidence(event),
                "turns": len(event.conversation),
                "created": event.event.timeDate,
            })
    return events


@router.get("/{event_id}", response_model=EventDocument)
async def get_event_document(
    event_id: str,
    blackboard: BlackboardState = Depends(get_blackboard),
):
    """Get full event document with conversation timeline."""
    event = await blackboard.get_event(event_id)
    if not event:
        raise HTTPException(status_code=404, detail=f"Event {event_id} not found")
    return event


@router.post("/{event_id}/approve")
async def approve_event(
    event_id: str,
    blackboard: BlackboardState = Depends(get_blackboard),
):
    """Approve a pending plan in an event conversation."""
    event = await blackboard.get_event(event_id)
    if not event:
        raise HTTPException(status_code=404, detail=f"Event {event_id} not found")

    turn = ConversationTurn(
        turn=len(event.conversation) + 1,
        actor="user",
        action="approve",
        thoughts="User approved the plan.",
    )
    await blackboard.append_turn(event_id, turn)

    # Atomically transition status so the Brain picks it up
    await blackboard.transition_event_status(
        event_id, from_status="waiting_approval", to_status=EventStatus.ACTIVE,
    )

    # Clear wait_for_user state so Brain re-processes with approval
    try:
        brain = await get_brain()
        brain.clear_waiting(event_id)
    except RuntimeError:
        pass  # Brain not initialized (unlikely in normal operation)

    logger.info(f"User approved event {event_id}")
    return {"status": "approved", "event_id": event_id}


@router.post("/{event_id}/reject")
async def reject_event(
    event_id: str,
    body: RejectRequest = RejectRequest(),
    blackboard: BlackboardState = Depends(get_blackboard),
):
    """Reject a pending plan in an event conversation."""
    event = await blackboard.get_event(event_id)
    if not event:
        raise HTTPException(status_code=404, detail=f"Event {event_id} not found")

    # Server-side image size guard (~1MB)
    if body.image and len(body.image) > 1_400_000:
        raise HTTPException(status_code=413, detail="Image too large (max 1MB)")

    turn = ConversationTurn(
        turn=len(event.conversation) + 1,
        actor="user",
        action="reject",
        thoughts=body.reason,
        image=body.image,
    )
    await blackboard.append_turn(event_id, turn)

    # Atomically transition status so the Brain re-processes with rejection feedback
    await blackboard.transition_event_status(
        event_id, from_status="waiting_approval", to_status=EventStatus.ACTIVE,
    )

    # Clear wait_for_user state so Brain re-processes with rejection
    try:
        brain = await get_brain()
        brain.clear_waiting(event_id)
    except RuntimeError:
        pass  # Brain not initialized (unlikely in normal operation)

    logger.info(f"User rejected event {event_id}: {body.reason}")
    return {"status": "rejected", "event_id": event_id}


class CloseRequest(BaseModel):
    """Typed request body for user force-close."""
    reason: str = Field("User force-closed the event.", description="Close reason")


@router.post("/{event_id}/close")
async def close_event_by_user(
    event_id: str,
    body: CloseRequest = CloseRequest(),
    blackboard: BlackboardState = Depends(get_blackboard),
):
    """Force-close an event from the UI. Uses existing close_event state machine."""
    event = await blackboard.get_event(event_id)
    if not event:
        raise HTTPException(status_code=404, detail=f"Event {event_id} not found")
    if event.status == EventStatus.CLOSED:
        raise HTTPException(status_code=409, detail="Event already closed")

    close_summary = f"User force-closed: {body.reason}"
    # Cancel any running agent task before closing (prevents orphaned CLI processes)
    try:
        brain = await get_brain()
        await brain.cancel_active_task(event_id, f"User force-close: {body.reason}")
    except RuntimeError:
        pass  # Brain not initialized
    await blackboard.close_event(event_id, close_summary)
    # Write to ops journal so Brain has temporal context for this closure
    await blackboard.append_journal(
        event.service,
        f"{event.event.reason} -- user force-closed. {body.reason}"
    )
    logger.info(f"User force-closed event {event_id}: {body.reason}")
    return {"status": "closed", "event_id": event_id}


@router.get("/{event_id}/report")
async def get_event_report(
    event_id: str,
    blackboard: BlackboardState = Depends(get_blackboard),
):
    """Get full event report as Markdown with service metadata and architecture."""
    event = await blackboard.get_event(event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    service_meta = await blackboard.get_service(event.service)
    mermaid = ""
    try:
        mermaid = await blackboard.generate_mermaid()
    except Exception:
        pass

    # Reuse Brain's markdown format (extracted as @staticmethod)
    from ..agents.brain import Brain
    content = Brain._event_to_markdown(event, service_meta, mermaid)

    # Add journal context
    journal = await blackboard.get_journal(event.service)
    if journal:
        content += "\n\n## Service Ops Journal\n\n"
        for entry in journal:
            content += f"- {entry}\n"

    return {"markdown": content, "event_id": event_id}


@router.get("/closed/list")
async def list_closed_events(
    limit: int = Query(50, ge=1, le=200),
    blackboard: BlackboardState = Depends(get_blackboard),
):
    """Get recently closed events."""
    closed_ids = await blackboard.redis.zrevrangebyscore(
        blackboard.EVENT_CLOSED,
        max=time.time(),
        min=time.time() - 86400,
        start=0,
        num=limit,
    )
    events = []
    for eid in closed_ids:
        event = await blackboard.get_event(eid)
        if event:
            events.append({
                "id": event.id,
                "source": event.source,
                "service": event.service,
                "status": event.status.value,
                "reason": event.event.reason,
                "evidence": _serialize_evidence(event),
                "turns": len(event.conversation),
                "created": event.event.timeDate,
            })
    return events
