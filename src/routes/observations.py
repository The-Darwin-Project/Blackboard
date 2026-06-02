# BlackBoard/src/routes/observations.py
# @ai-rules:
# 1. [Pattern]: Follows queue.py pattern -- APIRouter with prefix, Depends(get_blackboard).
# 2. [Constraint]: Read-only endpoint. All writes go through Brain tool calls only.
# 3. [Pattern]: Two routers -- global (/api/observations) and event-scoped (/api/queue/{id}/observations).
"""Observation series API -- exposes FRIDAY's numeric observations."""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from ..dependencies import get_blackboard
from ..state.blackboard import BlackboardState

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/queue", tags=["observations"])
global_router = APIRouter(prefix="/api/observations", tags=["observations"])


@global_router.get("")
async def get_global_observations(
    name: Optional[str] = Query(None, description="Filter by observation name"),
    service: Optional[str] = Query(None, description="Filter by service"),
    blackboard: BlackboardState = Depends(get_blackboard),
):
    """Return all observation series across all events (global 7-day timeline)."""
    return await blackboard.list_observations(service=service, name=name)


@router.get("/{event_id}/observations")
async def get_event_observations(
    event_id: str,
    blackboard: BlackboardState = Depends(get_blackboard),
):
    """Return all observation series for a specific event (drill-down)."""
    event = await blackboard.get_event(event_id)
    if not event:
        raise HTTPException(status_code=404, detail=f"Event {event_id} not found")
    return await blackboard.list_observations(event_id=event_id)
