# BlackBoard/src/routes/events.py
"""
Events API endpoint for agent activity stream + event document access.

Returns architecture events from the Blackboard state for UI visualization.
Provides event markdown documents for ephemeral agent bootstrap.
"""
from __future__ import annotations

import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import PlainTextResponse

from ..dependencies import get_blackboard, get_brain
from ..models import ArchitectureEvent
from ..state.blackboard import BlackboardState

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/events", tags=["events"])


@router.get("/", response_model=List[ArchitectureEvent])
async def list_events(
    start_time: Optional[float] = Query(None, description="Filter events after this timestamp"),
    end_time: Optional[float] = Query(None, description="Filter events before this timestamp"),
    service: Optional[str] = Query(None, description="Filter by service name"),
    limit: int = Query(100, ge=1, le=1000, description="Max events to return"),
    blackboard: BlackboardState = Depends(get_blackboard),
) -> List[ArchitectureEvent]:
    """
    Get architecture events for the agent activity stream.
    
    Events are returned newest first (ZREVRANGEBYSCORE from Redis).
    """
    if service:
        return await blackboard.get_events_for_service(service, start_time, end_time, limit=limit)
    return await blackboard.get_events_in_range(start_time, end_time, limit=limit)


@router.get("/{event_id}/document", response_class=PlainTextResponse)
async def get_event_document(
    event_id: str,
    blackboard: BlackboardState = Depends(get_blackboard),
    brain=Depends(get_brain),
):
    """Return event markdown document for ephemeral agent bootstrap.

    Includes service metadata and architecture mermaid for full context
    parity with local sidecar volume writes (write_event_to_volume).
    """
    event = await blackboard.get_event(event_id)
    if not event:
        raise HTTPException(404, f"Event {event_id} not found")
    service_meta = await blackboard.get_service(event.service)
    mermaid = ""
    if event.source != "headhunter":
        try:
            mermaid = await blackboard.generate_mermaid()
        except Exception:
            pass
    content = brain._event_to_markdown(event, service_meta, mermaid)
    return PlainTextResponse(content=content, media_type="text/markdown")
