# BlackBoard/src/routes/flow.py
# @ai-rules:
# 1. [Pattern]: Flow observability endpoints (/flow, /flow/history, /flow/{event_id}) extracted from main.py.
# 2. [Gotcha]: Reads dependencies._blackboard / dependencies.get_brain() at call time (via `from .. import dependencies`)
#    so tests patching dependencies._blackboard / dependencies._brain observe overrides cleanly.
# 3. [Constraint]: Static route /flow/history MUST stay registered before /flow/{event_id}.
"""Flow observability routes (leading indicators and value-stream timing)."""
from __future__ import annotations

import logging
import os

from fastapi import APIRouter, HTTPException, Query

from .. import dependencies
from ..models import FlowMetricsResponse, FlowSnapshot

logger = logging.getLogger(__name__)

router = APIRouter(tags=["flow"])


@router.get("/flow", response_model=FlowMetricsResponse)
async def get_flow_metrics() -> FlowMetricsResponse:
    """Flow health metrics -- leading indicators for system throughput.

    Separate from /health (which stays zero-Redis for K8s probes).
    Returns queue depth, active events, and per-role agent utilization.
    """
    blackboard = dependencies._blackboard
    flow = {"queue_depth": 0, "active_events": 0}
    if blackboard is not None:
        flow = await blackboard.get_flow_metrics()

    busy = 0
    idle = 0
    by_role: dict[str, dict[str, int]] = {}
    try:
        registry, _ = dependencies.get_registry_and_bridge()
        if registry:
            agents = await registry.list_agents()
            for a in agents:
                role = a.get("role", "unknown")
                if role not in by_role:
                    by_role[role] = {"busy": 0, "idle": 0}
                if a.get("busy"):
                    busy += 1
                    by_role[role]["busy"] += 1
                else:
                    idle += 1
                    by_role[role]["idle"] += 1
    except Exception:
        pass

    staleness_guards: list[dict] = []
    active_subs = 0
    brain = None
    try:
        brain = await dependencies.get_brain()
        if brain:
            staleness_guards = brain.get_staleness_guard_metrics()
            active_subs = brain.get_active_subscription_count()
    except Exception:
        pass

    # Read latest persisted snapshot for enriched fields (O(1) Redis op)
    latest = None
    try:
        if blackboard is not None:
            latest = await blackboard.get_latest_flow_snapshot()
    except Exception as exc:
        logger.warning("Flow enrichment from snapshot failed: %s", exc)

    hh_pending, hh_gl_pending, hh_gh_pending, hh_gl_breaker, hh_gh_breaker = 0, 0, 0, "closed", "closed"
    aligner_pending_count = 0
    wip_used = 0
    wip_cap = int(os.getenv("MAX_ACTIVE_EVENTS", "20"))
    try:
        if brain is None:
            brain = await dependencies.get_brain()
        hh = brain.agents.get("_headhunter") if brain else None
        if hh:
            hh_pending, hh_gl_pending, hh_gh_pending, hh_gl_breaker, hh_gh_breaker = (
                hh.pending_count,
                hh.gitlab_pending_count,
                hh.github_pending_count,
                hh.gitlab_breaker_state,
                hh.github_breaker_state,
            )
        aligner_ref = brain.agents.get("_aligner") if brain else None
        if aligner_ref:
            aligner_pending_count = aligner_ref.pending_count
        if brain:
            wip_used = await brain.count_global_wip()
    except Exception:
        pass
    wip_utilization_pct = (wip_used / wip_cap * 100) if wip_cap > 0 else 0.0
    wip_available = max(0, wip_cap - wip_used)

    jenkins_pending = 0
    jenkins_breaker_open = False
    jenkins_view_unhealthy = False
    try:
        jenkins_ref = brain.agents.get("_jenkins_observer") if brain else None
        if jenkins_ref:
            jenkins_pending = jenkins_ref.pending_count
            jenkins_breaker_open = jenkins_ref.breaker_open
            jenkins_view_unhealthy = jenkins_ref.view_unhealthy
    except Exception:
        pass

    return FlowMetricsResponse(
        queue_depth=flow["queue_depth"],
        active_events=flow["active_events"],
        busy_agents=busy,
        idle_agents=idle,
        active_subscriptions=active_subs,
        avg_event_age_sec=latest.avg_event_age_sec if latest else 0.0,
        deferred_events=latest.deferred_events if latest else 0,
        waiting_approval_events=flow.get("waiting_approval_events", 0),
        headhunter_pending=hh_pending,
        headhunter_gitlab_pending=hh_gl_pending,
        headhunter_github_pending=hh_gh_pending,
        headhunter_gitlab_breaker=hh_gl_breaker,
        headhunter_github_breaker=hh_gh_breaker,
        aligner_pending=aligner_pending_count,
        jenkins_pending=jenkins_pending,
        jenkins_breaker_open=jenkins_breaker_open,
        jenkins_view_unhealthy=jenkins_view_unhealthy,
        wip_used=wip_used,
        wip_cap=wip_cap,
        wip_utilization_pct=round(wip_utilization_pct, 1),
        wip_available=wip_available,
        avg_reconcile_ms=latest.avg_reconcile_ms if latest else 0.0,
        token_total_60s=latest.token_total_delta if latest else 0,
        token_calls_60s=latest.token_calls_delta if latest else 0,
        snapshot_timestamp=latest.timestamp if latest else None,
        agents_by_role=by_role,
        staleness_guards=staleness_guards,
    )


@router.get("/flow/history", response_model=list[FlowSnapshot])
async def get_flow_history(
    range_seconds: int = Query(3600, ge=60, le=604800),
) -> list[FlowSnapshot]:
    """Time-series flow snapshots with server-side downsampling for large ranges."""
    blackboard = dependencies._blackboard
    if blackboard is None:
        return []
    return await blackboard.get_flow_history(range_seconds=range_seconds)


@router.get("/flow/{event_id}")
async def get_event_flow(event_id: str) -> dict:
    """Value stream breakdown for a single event."""
    blackboard = dependencies._blackboard
    if blackboard is None:
        raise HTTPException(status_code=503, detail="Blackboard not initialized")

    event = await blackboard.get_event(event_id)
    if not event:
        raise HTTPException(status_code=404, detail=f"Event {event_id} not found")

    t = {
        "queued_at": event.queued_at,
        "processing_started_at": event.processing_started_at,
        "last_dispatched_at": event.last_dispatched_at,
        "last_completed_at": event.last_completed_at,
        "closed_at": event.closed_at,
    }

    def delta(a: str, b: str) -> float | None:
        va, vb = t.get(a), t.get(b)
        return round(vb - va, 3) if va is not None and vb is not None else None

    agent_turns = sum(
        1 for turn in event.conversation
        if turn.actor in ("architect", "sysadmin", "developer", "qe", "security_analyst", "code_reviewer", "explorer")
    )

    return {
        "event_id": event_id,
        "timestamps": t,
        "intervals": {
            "queue_wait_s": delta("queued_at", "processing_started_at"),
            "routing_s": delta("processing_started_at", "last_dispatched_at"),
            "execution_s": delta("last_dispatched_at", "last_completed_at"),
            "total_lead_time_s": delta("queued_at", "closed_at"),
        },
        "agent_turns": agent_turns,
    }
