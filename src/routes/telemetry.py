# BlackBoard/src/routes/telemetry.py
# @ai-rules:
# 1. [Pattern]: POST / returns 410 Gone. DarwinClient telemetry push is deprecated.
# 2. [Constraint]: Do NOT add processing logic for POST. Service discovery uses K8s annotations now.
# 3. [Pattern]: GET /llm exposes QuotaTracker stats for observability (PV observation point).
"""
Telemetry endpoints.

POST / -- deprecated DarwinClient push (returns 410 Gone).
GET /llm -- LLM quota rate limiter stats (QuotaTracker).
"""
from __future__ import annotations

import logging

from fastapi import APIRouter
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/telemetry", tags=["telemetry"])


@router.post("/")
async def receive_telemetry() -> JSONResponse:
    """Return 410 Gone -- DarwinClient telemetry is deprecated."""
    logger.warning("DEPRECATED: DarwinClient telemetry POST received. Returning 410 Gone.")
    return JSONResponse(
        status_code=410,
        content={"error": "DarwinClient telemetry is deprecated. Use darwin.io/* pod annotations."},
    )


@router.get("/llm")
async def llm_stats() -> JSONResponse:
    """LLM quota rate limiter stats (rolling 60s window)."""
    from ..agents.llm import get_quota_tracker

    tracker = get_quota_tracker()
    if tracker is None:
        return JSONResponse(
            status_code=503,
            content={"error": "QuotaTracker not initialized (no Gemini adapter created yet)"},
        )
    return JSONResponse(content=tracker.get_stats())
