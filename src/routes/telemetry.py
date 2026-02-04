# BlackBoard/src/routes/telemetry.py
"""
Telemetry ingestion endpoint.

Receives telemetry from self-aware applications (e.g., Darwin Store).
Schema defined in DESIGN.md section 4.1.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, HTTPException

from ..models import TelemetryPayload
from ..state import BlackboardState
from ..dependencies import get_blackboard

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/telemetry", tags=["telemetry"])


@router.post("/", status_code=200)
async def receive_telemetry(
    payload: TelemetryPayload,
    blackboard: BlackboardState = Depends(get_blackboard),
) -> dict:
    """
    Receive telemetry from a self-aware application.
    
    Updates all Blackboard layers:
    - Structure: Service nodes and dependency edges
    - Metadata: Health metrics and version
    - History: Time-series metrics for charting
    """
    try:
        await blackboard.process_telemetry(payload)
        
        logger.info(
            f"Telemetry received: {payload.service} v{payload.version} "
            f"cpu={payload.metrics.cpu:.1f}% error_rate={payload.metrics.error_rate:.2f}%"
        )
        
        return {
            "status": "accepted",
            "service": payload.service,
            "dependencies_count": len(payload.topology.dependencies),
        }
    
    except Exception as e:
        logger.error(f"Telemetry processing failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
