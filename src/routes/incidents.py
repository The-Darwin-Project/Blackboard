# BlackBoard/src/routes/incidents.py
# @ai-rules:
# 1. [Pattern]: Read-only endpoint. Adapter handles caching + filtering.
# 2. [Pattern]: Returns [] when Jira incident adapter not configured -- graceful degradation.
# 3. [Pattern]: Adapter returns normalized dicts directly -- no key remapping needed.
# 4. [Constraint]: Gets adapter from request.app.state.incident_adapter (DI from main.py).
"""
Incidents API -- lists Darwin-created Jira incidents via JQL read-back.
"""
from __future__ import annotations

import logging
import os

from fastapi import APIRouter, Request

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/incidents", tags=["incidents"])


@router.get("/list")
async def list_incidents(request: Request) -> list[dict]:
    """List Darwin-created incidents from Jira, filtered by configured label."""
    adapter = getattr(request.app.state, "incident_adapter", None)
    if not adapter:
        return []
    try:
        label = os.getenv("JIRA_INCIDENT_LABEL_FILTER", "")
        return await adapter.list_incidents(label_filter=label)
    except Exception as e:
        logger.warning("Failed to fetch incidents from Jira: %s", e)
        return []
