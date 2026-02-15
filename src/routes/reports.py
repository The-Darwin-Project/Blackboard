# BlackBoard/src/routes/reports.py
# @ai-rules:
# 1. [Gotcha]: GET /reports/ (SPA handler) MUST be first. GET /reports/list MUST stay before GET /reports/{event_id}.
# 2. [Pattern]: Reports are persisted snapshots (90-day TTL), NOT live-generated like queue/{id}/report.
# 3. [Gotcha]: GET /reports/ serves index.html so the SPA loads when browser navigates to /reports.
#    Without this, FastAPI's router intercepts the request and returns 404 (no bare /reports handler).
"""
Reports API - Persisted event report management.

Provides endpoints for the Report Viewer UI to:
- Serve SPA for /reports page (browser navigation)
- List all persisted reports (metadata only)
- Get a specific report (full markdown content)
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse

from ..dependencies import get_blackboard
from ..state.blackboard import BlackboardState

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/reports", tags=["reports"])

# SPA static dir (built React app)
_static_dir = Path(__file__).parent.parent.parent / "ui" / "dist"


@router.get("/", include_in_schema=False)
async def reports_spa():
    """Serve SPA index.html for /reports page navigation.

    When the browser navigates to /reports, FastAPI's router intercepts
    the request before the static mount. This handler serves index.html
    so React Router can render the ReportsPage component.
    """
    index = _static_dir / "index.html"
    if index.exists():
        return FileResponse(index, media_type="text/html")
    raise HTTPException(status_code=404, detail="UI not built. Run npm run build in BlackBoard/ui/")


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
