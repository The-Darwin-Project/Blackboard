# BlackBoard/src/routes/telemetry.py
# @ai-rules:
# 1. [Pattern]: POST / returns 410 Gone. DarwinClient telemetry push is deprecated.
# 2. [Constraint]: Do NOT add processing logic for POST. Service discovery uses K8s annotations now.
# 3. [Pattern]: GET /llm exposes QuotaPoolRegistry stats + callers/teams totals for observability (PV observation point).
"""
Telemetry endpoints.

POST / -- deprecated DarwinClient push (returns 410 Gone).
GET /llm -- LLM multi-pool quota stats (QuotaPoolRegistry) + callers/teams breakdown.
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
    """LLM quota rate limiter stats (multi-pool rolling 60s window + callers/teams breakdown)."""
    from ..agents.llm import get_quota_registry, get_token_meter

    all_stats = get_quota_registry().get_all_stats()
    meter = get_token_meter()
    global_stats = all_stats["global"]
    payload = {
        **global_stats,
        "global": global_stats,
        "pools": all_stats["pools"],
        "callers": meter.get_caller_totals(),
        "teams": meter.get_team_totals(),
    }
    return JSONResponse(status_code=200, content=payload)
