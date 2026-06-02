# BlackBoard/src/routes/observations.py
# @ai-rules:
# 1. [Pattern]: Follows queue.py pattern -- APIRouter with prefix, Depends(get_blackboard).
# 2. [Constraint]: Read-only endpoint. All writes go through Brain tool calls only.
"""Observation series API -- exposes FRIDAY's numeric observations per event."""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException

from ..dependencies import get_blackboard
from ..state.blackboard import BlackboardState

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/queue", tags=["observations"])


@router.get("/{event_id}/observations")
async def get_event_observations(
    event_id: str,
    blackboard: BlackboardState = Depends(get_blackboard),
):
    """Return all observation series for an event (UI Insights tab)."""
    event = await blackboard.get_event(event_id)
    if not event:
        raise HTTPException(status_code=404, detail=f"Event {event_id} not found")
    return await blackboard.list_observations(event_id)
