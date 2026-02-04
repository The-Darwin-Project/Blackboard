# BlackBoard/src/routes/events.py
"""
Events API endpoint for agent activity stream.

Returns architecture events from the Blackboard state for UI visualization.
"""
from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, Query

from ..dependencies import get_blackboard
from ..models import ArchitectureEvent
from ..state.blackboard import BlackboardState

router = APIRouter(prefix="/events", tags=["events"])


@router.get("/", response_model=List[ArchitectureEvent])
async def list_events(
    start_time: Optional[float] = Query(None, description="Filter events after this timestamp"),
    end_time: Optional[float] = Query(None, description="Filter events before this timestamp"),
    limit: int = Query(100, ge=1, le=1000, description="Max events to return"),
    blackboard: BlackboardState = Depends(get_blackboard),
) -> List[ArchitectureEvent]:
    """
    Get architecture events for the agent activity stream.
    
    Events are sorted by timestamp descending (most recent first).
    """
    events = await blackboard.get_events_in_range(start_time, end_time)
    
    # Sort by timestamp descending (most recent first)
    events.sort(key=lambda e: e.timestamp, reverse=True)
    
    # Apply limit
    return events[:limit]
