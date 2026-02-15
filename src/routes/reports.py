# BlackBoard/src/routes/reports.py
# @ai-rules:
# 1. [Gotcha]: GET /reports/list MUST stay before GET /reports/{event_id} to avoid "list" matching as event_id.
# 2. [Pattern]: Reports are persisted snapshots (90-day TTL), NOT live-generated like queue/{id}/report.
"""
Reports API - Persisted event report management.

Provides endpoints for the Report Viewer UI to:
- List all persisted reports (metadata only)
- Get a specific report (full markdown content)
"""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from ..dependencies import get_blackboard
from ..state.blackboard import BlackboardState

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/list")
async def list_reports(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    service: Optional[str] = Query(None, description="Filter by service name"),
    blackboard: BlackboardState = Depends(get_blackboard),
):
    """Get all persisted report metadata, sorted newest first."""
    return await blackboard.list_reports(limit=limit, offset=offset, service=service)


@router.get("/{event_id}")
async def get_report(
    event_id: str,
    blackboard: BlackboardState = Depends(get_blackboard),
):
    """Get a persisted report by event ID (full markdown content)."""
    report = await blackboard.get_report(event_id)
    if not report:
        raise HTTPException(status_code=404, detail=f"Report for {event_id} not found or expired")
    return report
