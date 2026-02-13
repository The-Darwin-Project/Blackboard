# BlackBoard/src/routes/telemetry.py
"""
Telemetry ingestion endpoint.

Receives telemetry from self-aware applications (e.g., Darwin Store).
Schema defined in DESIGN.md section 4.1.

IMPORTANT: Telemetry is processed through the Aligner agent for:
- Service discovery events
- Anomaly detection (high CPU, memory, error rate)
- Closed-loop triggering of Architect
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, HTTPException

from ..models import TelemetryPayload
from ..agents import Aligner
from ..dependencies import get_aligner

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/telemetry", tags=["telemetry"])


@router.post("/", status_code=200)
async def receive_telemetry(
    payload: TelemetryPayload,
    aligner: Aligner = Depends(get_aligner),
) -> dict:
    """
    Receive telemetry from a self-aware application.
    
    Processed through the Aligner agent which:
    - Applies filter rules for noise reduction
    - Detects new services (SERVICE_DISCOVERED events)
    - Detects anomalies (HIGH_CPU, HIGH_MEMORY, HIGH_ERROR_RATE)
    - Triggers Architect analysis on anomalies (closed-loop)
    - Updates all Blackboard layers
    """
    logger.warning("DEPRECATED: DarwinClient telemetry received. Use darwin.io/* annotations instead. "
                   "This endpoint will be removed in a future release.")
    try:
        processed = await aligner.process_telemetry(payload)
        
        logger.info(
            f"Telemetry received: {payload.service} v{payload.version} "
            f"cpu={payload.metrics.cpu:.1f}% error_rate={payload.metrics.error_rate:.2f}%"
            f" (processed={processed})"
        )
        
        return {
            "status": "accepted" if processed else "filtered",
            "service": payload.service,
            "dependencies_count": len(payload.topology.dependencies),
        }
    
    except Exception as e:
        logger.error(f"Telemetry processing failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
