# BlackBoard/src/routes/shifts.py
# @ai-rules:
# 1. [Pattern]: Read-only endpoints. Blackboard handles persistence + caching.
# 2. [Pattern]: Route gated on DEX_ENABLED (same as TimeKeeper). Reads are open when route is mounted.
# 3. [Pattern]: /shifts/current computes next sweep time from croniter for live status.
"""
Shifts API -- Nightwatcher shift reports for the Shifts UI.

Provides endpoints for the weekly calendar, shift detail view,
and live current-shift status (pending count + next sweep time).
"""
from __future__ import annotations

import logging
import os
import time
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from ..dependencies import get_blackboard
from ..state.blackboard import BlackboardState

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/shifts", tags=["shifts"])


@router.get("/current")
async def get_current_shift(
    blackboard: BlackboardState = Depends(get_blackboard),
) -> dict:
    """Live shift status: pending count and next sweep time."""
    pending = await blackboard.count_pending_escalations()
    cron_expr = os.getenv("NIGHTWATCHER_SWEEP_CRON", "0 6,18 * * *")
    next_sweep = ""
    try:
        from croniter import croniter
        next_fire = croniter(cron_expr, time.time()).get_next(float)
        from datetime import datetime, timezone
        next_sweep = datetime.fromtimestamp(next_fire, tz=timezone.utc).isoformat()
    except Exception:
        pass
    return {
        "pending_count": pending,
        "next_sweep_utc": next_sweep,
        "enabled": os.getenv("NIGHTWATCHER_ENABLED", "false").lower() == "true",
    }


@router.get("/list")
async def list_shifts(
    week: Optional[str] = Query(None, description="ISO week (e.g., 2026-W18)"),
    days: int = Query(7, ge=1, le=30, description="Number of days to look back"),
    blackboard: BlackboardState = Depends(get_blackboard),
) -> list[dict]:
    """List shift report metadata for a week or date range."""
    if week:
        try:
            from datetime import datetime
            monday = datetime.strptime(week + "-1", "%G-W%V-%u")
            from_ts = monday.timestamp()
            to_ts = from_ts + 7 * 86400
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid ISO week: {week}")
    else:
        to_ts = time.time()
        from_ts = to_ts - days * 86400
    return await blackboard.list_shift_reports(from_ts, to_ts)


@router.get("/{date}/{window}")
async def get_shift_detail(
    date: str,
    window: str,
    blackboard: BlackboardState = Depends(get_blackboard),
) -> dict:
    """Full shift report with incidents, investigations, and manifest."""
    if window not in ("morning", "evening"):
        raise HTTPException(status_code=400, detail="Window must be 'morning' or 'evening'")
    report = await blackboard.get_shift_report(date, window)
    if not report:
        raise HTTPException(status_code=404, detail=f"No shift report for {date}/{window}")
    return report.model_dump()
