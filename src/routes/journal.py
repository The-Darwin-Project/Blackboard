# BlackBoard/src/routes/journal.py
# @ai-rules:
# 1. [Pattern]: Read-only endpoints wrapping blackboard.get_journal / get_recent_journal_entries.
# 2. [Constraint]: No mutations. Journal writes happen via blackboard.append_journal in Brain/routes.
# 3. [Pattern]: Mounted at /api/journal prefix in main.py.
"""
Service Ops Journal API — exposes per-service and cross-service operational history
to agent sidecars via the Journal MCP proxy.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends

from ..dependencies import get_blackboard
from ..state.blackboard import BlackboardState

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/journal", tags=["journal"])


@router.get("/")
async def get_all_journal(
    blackboard: BlackboardState = Depends(get_blackboard),
):
    """Get recent ops journal entries across all services."""
    entries = await blackboard.get_recent_journal_entries()
    return {"entries": entries}


@router.get("/{service_name}")
async def get_service_journal(
    service_name: str,
    blackboard: BlackboardState = Depends(get_blackboard),
):
    """Get ops journal entries for a specific service."""
    entries = await blackboard.get_journal(service_name)
    return {"service": service_name, "entries": entries}
