# BlackBoard/src/routes/queue.py
"""
Conversation Queue API - Event document management.

Provides endpoints for the unified group chat UI to:
- List active events
- Get event conversation timeline
- Approve pending plans
- View closed events
"""
from __future__ import annotations

import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from ..dependencies import get_blackboard
from ..models import ConversationTurn, EventDocument
from ..state.blackboard import BlackboardState

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/queue", tags=["queue"])


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
    logger.info(f"User approved event {event_id}")
    return {"status": "approved", "event_id": event_id}


@router.post("/{event_id}/reject")
async def reject_event(
    event_id: str,
    body: dict = None,
    blackboard: BlackboardState = Depends(get_blackboard),
):
    """Reject a pending plan in an event conversation."""
    event = await blackboard.get_event(event_id)
    if not event:
        raise HTTPException(status_code=404, detail=f"Event {event_id} not found")

    reason = (body or {}).get("reason", "User rejected the plan.")
    turn = ConversationTurn(
        turn=len(event.conversation) + 1,
        actor="user",
        action="reject",
        thoughts=reason,
    )
    await blackboard.append_turn(event_id, turn)
    logger.info(f"User rejected event {event_id}: {reason}")
    return {"status": "rejected", "event_id": event_id}


@router.get("/closed/list")
async def list_closed_events(
    limit: int = Query(50, ge=1, le=200),
    blackboard: BlackboardState = Depends(get_blackboard),
):
    """Get recently closed events."""
    import time
    # Get closed events from last 24h
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
                "turns": len(event.conversation),
            })
    return events
