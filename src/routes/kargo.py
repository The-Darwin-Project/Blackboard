# BlackBoard/src/routes/kargo.py
# @ai-rules:
# 1. [Pattern]: Lightweight read-only endpoint. Returns cached observer state, no K8s API calls.
# 2. [Constraint]: get_kargo_observer returns None when KARGO_OBSERVER_ENABLED=false -- endpoint returns [].
# 3. [Pattern]: No prefix on router -- full path in decorator. Matches /api/agents pattern in main.py.
# 4. [Pattern]: KargoStageSnapshot response model enforces contract at API boundary (observer stores plain dicts).
"""Kargo stage status REST endpoint -- polling fallback for WS-only kargo_stages_update."""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from ..dependencies import get_kargo_observer, get_brain

logger = logging.getLogger(__name__)


class KargoStageSnapshot(BaseModel):
    """Response model matching KargoObserver._failure_details values."""
    project: str
    stage: str
    promotion: str
    freight: str = ""
    phase: str
    message: str = ""
    failed_step: str = ""
    mr_url: str = ""
    service: str
    started_at: str = ""
    finished_at: str = ""


router = APIRouter(tags=["kargo"])


@router.get("/api/kargo/stages", response_model=list[KargoStageSnapshot])
async def list_failed_stages(
    observer=Depends(get_kargo_observer),
) -> list[KargoStageSnapshot]:
    """Return current failed Kargo stage snapshots from the observer cache."""
    if not observer:
        try:
            brain = await get_brain()
            observer = brain.agents.get("_kargo_observer")
        except RuntimeError:
            pass
    if not observer:
        return []
    return [KargoStageSnapshot(**s) for s in observer.get_failed_stages()]
