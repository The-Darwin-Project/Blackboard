# BlackBoard/src/routes/kargo.py
# @ai-rules:
# 1. [Pattern]: Lightweight read-only endpoint. Returns cached observer state, no K8s API calls.
# 2. [Constraint]: Returns [] when KARGO_OBSERVER_ENABLED=false (brain.agents has no _kargo_observer).
# 3. [Pattern]: No prefix on router -- full path in decorator. Matches /api/agents pattern in main.py.
# 4. [Pattern]: KargoStageSnapshot response model enforces contract at API boundary (observer stores plain dicts).
# 5. [Pattern]: Reads observer from brain.agents (instance dict), NOT from dependencies.py module global.
#    Same approach as headhunter/pending endpoint. Module globals via Depends() have a known reliability
#    issue where _kargo_observer is None despite set_kargo_observer() being called in lifespan.
"""Kargo stage status REST endpoint -- polling fallback for WS-only kargo_stages_update."""
from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from ..dependencies import get_brain

router = APIRouter(tags=["kargo"])


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


@router.get("/api/kargo/stages", response_model=list[KargoStageSnapshot])
async def list_failed_stages() -> list[KargoStageSnapshot]:
    """Return current failed Kargo stage snapshots from the observer cache."""
    try:
        brain = await get_brain()
    except RuntimeError:
        return []
    observer = brain.agents.get("_kargo_observer")
    if not observer:
        return []
    return [KargoStageSnapshot(**s) for s in observer.get_failed_stages()]


@router.get("/api/kargo/debug")
async def kargo_debug() -> dict:
    """Diagnostic endpoint to trace observer state from within the running process."""
    from ..dependencies import _kargo_observer, _brain
    result: dict = {
        "di_kargo_observer_is_none": _kargo_observer is None,
        "di_brain_is_none": _brain is None,
    }
    try:
        brain = await get_brain()
        result["get_brain_ok"] = True
        result["brain_agents_keys"] = list(brain.agents.keys())
        observer = brain.agents.get("_kargo_observer")
        result["brain_agents_observer_is_none"] = observer is None
        if observer:
            stages = observer.get_failed_stages()
            result["get_failed_stages_count"] = len(stages)
            result["failure_details_count"] = len(getattr(observer, "_failure_details", {}))
            result["reported_failures_count"] = len(getattr(observer, "_reported_failures", {}))
            if stages:
                result["first_stage_keys"] = list(stages[0].keys())
    except RuntimeError as e:
        result["get_brain_ok"] = False
        result["get_brain_error"] = str(e)
    return result
