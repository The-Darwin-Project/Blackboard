# BlackBoard/src/routes/telemetry.py
# @ai-rules:
# 1. [Pattern]: This route returns 410 Gone. DarwinClient telemetry push is deprecated.
# 2. [Constraint]: Do NOT add processing logic. Service discovery uses K8s annotations now.
"""
DEPRECATED telemetry ingestion endpoint.

DarwinClient telemetry push is deprecated. Service discovery and metrics
are handled by the K8s Observer via darwin.io/* pod annotations.
This endpoint returns HTTP 410 Gone to inform legacy clients.
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
