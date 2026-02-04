# BlackBoard/src/routes/metrics.py
"""
Metrics history endpoints.

Provides the Resources Consumption Chart (Visualization #2).
"""
from __future__ import annotations

import logging
from typing import List

from fastapi import APIRouter, Depends, Query

from ..models import ChartData, MetricPoint
from ..state import BlackboardState
from ..dependencies import get_blackboard

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/metrics", tags=["metrics"])


@router.get("/{service}")
async def get_current_metrics(
    service: str,
    blackboard: BlackboardState = Depends(get_blackboard),
) -> dict:
    """
    Get current metrics for a service.
    
    Returns the most recent CPU, memory, and error_rate values.
    """
    metrics = await blackboard.get_current_metrics(service)
    
    return {
        "service": service,
        "metrics": metrics,
    }


@router.get("/{service}/history")
async def get_metric_history(
    service: str,
    metric: str = Query("cpu", description="Metric name: cpu, memory, or error_rate"),
    range_seconds: int = Query(3600, description="Time range in seconds (default 1 hour)"),
    blackboard: BlackboardState = Depends(get_blackboard),
) -> dict:
    """
    Get metric history for a service.
    
    Returns time-series data points within the specified range.
    """
    import time
    
    end_time = time.time()
    start_time = end_time - range_seconds
    
    points = await blackboard.get_metric_history(
        service, metric, start_time, end_time
    )
    
    return {
        "service": service,
        "metric": metric,
        "range_seconds": range_seconds,
        "data_points": len(points),
        "data": [{"timestamp": p.timestamp, "value": p.value} for p in points],
    }


@router.get("/chart")
async def get_chart_data(
    services: List[str] = Query(..., description="Service names to include"),
    metrics: List[str] = Query(
        ["cpu", "memory", "error_rate"],
        description="Metrics to include"
    ),
    range_seconds: int = Query(3600, description="Time range in seconds"),
    blackboard: BlackboardState = Depends(get_blackboard),
) -> ChartData:
    """
    Get aggregated data for the Resources Consumption Chart.
    
    This is Visualization #2 - combines metric series with architecture events
    for correlation analysis.
    
    Example:
        GET /metrics/chart?services=inventory-api&services=postgres&range_seconds=3600
    """
    return await blackboard.get_chart_data(
        services=services,
        metrics=metrics,
        range_seconds=range_seconds,
    )
