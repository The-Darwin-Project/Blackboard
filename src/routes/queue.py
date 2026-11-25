# BlackBoard/src/routes/queue.py
# @ai-rules:
# 1. [Gotcha]: GET /closed/list MUST stay before GET /{event_id} to avoid "closed" matching as event_id.
# 2. [Pattern]: POST /{event_id}/close uses blackboard.close_event() + explicit delete_slack_mapping() to set the 14-day archival-retention TTL on the Slack thread mapping (Brain path uses _close_and_broadcast instead). delete_slack_mapping() no longer deletes the key.
# 3. [Gotcha]: Pre-existing route order issue -- closed/list is after /{event_id}. Works because /closed/list is 2 segments.
# 4. [Pattern]: GET /{event_id}/report uses event_to_markdown from src/utils/event_markdown.
# 5. [Policy]: GET /headhunter/pending reads Redis snapshots (darwin:headhunter:snapshot:{platform}) +
#    active/waiting Blackboard events (zero HTTP calls), dropping snapshot items whose status or raw.mr_state is merged/closed.
# 6. [Pattern]: list_active_events and list_closed_events include created_by_email for BFF multi-tenant filtering.
# 7. [Pattern]: PATCH lessons/{id}/demote and verify endpoints read-modify-write Qdrant point (payload + re-embed). Legacy lessons missing channel/verification_count default to external/0.
# 8. [Pattern]: /active response includes unread_notes for sidebar badge display.
# 9. [Pattern]: Knowledge CRUD routes mirror lesson pattern. KnowledgeUpdateRequest uses extra="forbid" to enforce immutability of identity fields (topic, scope) -- Pydantic returns 422 on unknown fields.
# 10. [Pattern]: PATCH /admin/knowledge/{id} does read-modify-reembed-upsert. Only mutable fields (fact, source, confidence, valid_until) can be updated.
# 11. [Pattern]: GET /aligner/pending reads from darwin:aligner:pending ZSET + meta HASH. Pure Redis read (matching HH snapshot architecture). response_model=list[PendingAnomaly].
# 12. [Pattern]: GET /jenkins/pending mirrors aligner pattern — darwin:jenkins:pending ZSET + meta HASH. Key format: {job_name} or view-outage:{view}. response_model=list[JenkinsPendingItem]. Meta-last: target from meta.get("job_name"), not key-derived.
# 13. [Pattern]: KnowledgeRequest includes optional `service` (part of uuid5 identity). KnowledgeUpdateRequest
#     deliberately omits it -- service is immutable once a fact is created.
# 14. [Pattern]: GET /admin/{knowledge,lessons,memories} are cursor-paginated scroll endpoints:
#     {items, next_cursor, has_more} (no `total`, matching /reports/search). limit default 50,
#     le=200 on all three -- never raise this to unbounded. q/scope/channel/service filters are
#     partly Qdrant-indexed (scope/service) and partly post-fetch on the current page only
#     (channel has no payload index; q is a page-local substring match everywhere).
# 15. [Pattern]: GET /headhunter/pending merges Redis PlatformSnapshots (via get_headhunter_snapshot)
#     with Blackboard-active and waiting_approval Headhunter events (new/active/deferred/waiting_approval).
#     Per-item fetch via asyncio.gather(return_exceptions=True) -- one malformed/legacy event record
#     must not drop every other active GitHub item for the poll. _github_active_item() builds PR/Issue rows.
# 16. [Pattern]: GET /waiting_approval and GET /active both defensively drop (and SREM)
#     event ids whose event doc is missing or already CLOSED -- a zombie in EVENT_WAITING_APPROVAL
#     or EVENT_ACTIVE desynced from the event's real status. Both are symmetric halves of the
#     same partial close_event() failure mode; fixing only one set leaves the other unguarded.
#     Brain also runs a periodic sweep of both sets (see Brain._sweep_waiting_approval_zombies),
#     this is a belt-and-suspenders read guard (#240).
"""
Conversation Queue API - Event document management.

Provides endpoints for the unified group chat UI to:
- List active events
- Get event conversation timeline
- Approve pending plans
- Force-close events
- View closed events
"""
from __future__ import annotations

import asyncio
import inspect
import json
import logging
import os
import re
import time


from typing import Any, Literal, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request, Path
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from redis.exceptions import RedisError, WatchError

from ..dependencies import get_archivist, get_blackboard, get_brain
from ..auth import (
    UserContext,
    can_approve_event,
    can_override_domain,
    can_rename_event,
    require_auth,
    get_user_from_request,
    resolve_approval_identity,
)
from ..models import ConversationTurn, EventDocument, EventEvidence, EventStatus, JenkinsPendingItem, PendingAnomaly, PendingApproval
from ..state.blackboard import BlackboardState
from ..agents.headhunter_models import HeadhunterOperationError, redact_error_text
from ..utils.pii_redaction import redact_pii
from ..utils.prompt_sanitize import sanitize_title
from ..utils import vcs_approval as _vcs_approval
from ..utils.vcs_approval import (
    check_approval_sha_drift,
    extract_context_head_sha,
    resolve_live_head_sha,
)
_ORIG_RESOLVE_LIVE_HEAD_SHA = resolve_live_head_sha


class ApproveRequest(BaseModel):
    """Optional typed request body for SHA-pinned plan approval."""
    expected_sha: Optional[str] = Field(None, max_length=64, description="Confirmed HEAD SHA after drift warning")


class RejectRequest(BaseModel):
    """Typed request body for plan rejection."""
    reason: str = Field("User rejected the plan.", description="Rejection reason")
    image: Optional[str] = Field(None, description="Base64 data URI of screenshot")


class TitleUpdateRequest(BaseModel):
    """Typed request body for event title updates."""
    title: str

    @field_validator("title")
    @classmethod
    def validate_title(cls, v: str) -> str:
        collapsed = sanitize_title(v)
        if not collapsed:
            raise ValueError("Title cannot be empty or whitespace only")
        if len(collapsed) > 100:
            raise ValueError("Title cannot exceed 100 characters")
        return collapsed

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/queue", tags=["queue"])

def _serialize_evidence(event: EventDocument) -> dict:
    """Serialize evidence to dict with fallback for legacy string evidence."""
    evidence_val = event.event.evidence
    if isinstance(evidence_val, EventEvidence):
        return evidence_val.model_dump()
    return {
        "display_text": str(evidence_val),
        "source_type": event.source,
        "domain": "complicated",
        "severity": "warning",
    }


def _github_active_item(
    ctx: dict,
    *,
    number_key: str,
    title_key: str,
    url_key: str,
    action: str,
    fallback_created_at: str,
    is_issue: bool = False,
) -> dict:
    """Build a /headhunter/pending row for a Blackboard-sourced active GitHub PR/Issue event.

    number_key/title_key/url_key account for the field-name differences between
    github_context (PR: pr_number/pr_title/pr_url) and github_issue_context
    (Issue: issue_number/title/html_url) -- the two evidence shapes are mutually
    exclusive per EventEvidence's model validator (#233).
    """
    num_field = "issue_number" if is_issue else "pr_number"
    title_field = "issue_title" if is_issue else "pr_title"
    return {
        "platform": "github",
        num_field: ctx.get(number_key),
        title_field: ctx.get(title_key, ""),
        "project_path": f"{ctx.get('owner', '')}/{ctx.get('repo', '')}",
        "author": ctx.get("author", ""),
        "created_at": ctx.get("created_at") or fallback_created_at,
        "target_url": ctx.get(url_key, ""),
        "queue_position": None,
        "action": action,
        "priority": 0,
    }


def _has_active_subscription(event_id: str) -> bool:
    """Check if StateWatcher has an active subscription for this event."""
    from ..dependencies import _brain
    if _brain:
        return _brain.has_subscription(event_id)
    return False


async def _defer_timeline_fields(
    blackboard: BlackboardState,
    event_id: str,
    event: EventDocument,
) -> dict[str, float]:
    """Resolve defer timestamps via shared BlackboardState helper."""
    defer_until, defer_started_at = await blackboard.resolve_defer_timestamps(
        event_id, event,
    )
    out: dict[str, float] = {}
    if defer_until is not None:
        out["defer_until"] = defer_until
    if defer_started_at is not None:
        out["defer_started_at"] = defer_started_at
    return out


@router.get("/active")
async def list_active_events(
    blackboard: BlackboardState = Depends(get_blackboard),
):
    """Get all active event IDs with basic metadata."""
    event_ids = await blackboard.get_active_events()
    events = []
    for eid in event_ids:
        event = await blackboard.get_event(eid)
        # Defensive filter: mirrors GET /waiting_approval -- a CLOSED (or missing) event
        # id left over in EVENT_ACTIVE is the same zombie class from the other side of a
        # partial close_event() failure (#240). Evict it opportunistically.
        if not event or event.status == EventStatus.CLOSED:
            await blackboard.redis.srem(blackboard.EVENT_ACTIVE, eid)
            continue
        row = {
            "id": event.id,
            "title": getattr(event, "title", None),
            "title_source": getattr(event, "title_source", None),
            "source": event.source,
            "service": event.service,
            "subject_type": getattr(event, "subject_type", "service"),
            "status": event.status.value,
            "reason": event.event.reason,
            "evidence": _serialize_evidence(event),
            "turns": len(event.conversation),
            "created": event.event.timeDate,
            "created_by_email": event.created_by_email,
            "unread_notes": getattr(event, "unread_notes", 0) or 0,
            "subscription_active": _has_active_subscription(eid),
            "token_total": event.token_usage.get("total_tokens") if event.token_usage else None,
            "approval_requested_sha": getattr(event, "approval_requested_sha", None),
        }
        if event.status == EventStatus.DEFERRED:
            row.update(await _defer_timeline_fields(blackboard, eid, event))
        events.append(row)
    return events


@router.get("/waiting_approval")
async def list_waiting_approval_events(
    blackboard: BlackboardState = Depends(get_blackboard),
):
    """Get all waiting-approval event IDs with basic metadata."""
    event_ids = await blackboard.get_waiting_approval_events()
    events = []
    for eid in event_ids:
        event = await blackboard.get_event(eid)
        # Defensive filter: a closed (or missing) event id left over in the
        # waiting_approval set is a zombie -- desynced from actual event state (#240).
        # Evict it opportunistically so subsequent polls don't keep re-fetching it.
        if not event or event.status == EventStatus.CLOSED:
            await blackboard.redis.srem(blackboard.EVENT_WAITING_APPROVAL, eid)
            continue
        events.append({
            "id": event.id,
            "title": getattr(event, "title", None),
            "title_source": getattr(event, "title_source", None),
            "source": event.source,
            "service": event.service,
            "subject_type": getattr(event, "subject_type", "service"),
            "status": event.status.value,
            "reason": event.event.reason,
            "evidence": _serialize_evidence(event),
            "turns": len(event.conversation),
            "created": event.event.timeDate,
            "created_by_email": event.created_by_email,
            "approval_requested_sha": getattr(event, "approval_requested_sha", None),
        })
    return events


@router.get("/{event_id}/turns")
async def get_event_turns(
    event_id: str,
    role: Optional[str] = Query(None, description="Agent role for gap calculation (qe, sysadmin, developer, architect, security_analyst, code_reviewer)"),
    since: Optional[int] = Query(None, description="Return turns after this turn number (overrides role-based gap)"),
    blackboard: BlackboardState = Depends(get_blackboard),
):
    """Get conversation turns with agent-aware gap calculation.

    When `role` is provided (no `since`): scans backward to find the last turn
    where actor == role, returns all turns after that point.
    When `since` is provided: returns turns with turn number > since (explicit polling).
    When neither: returns the full conversation.
    """
    event = await blackboard.get_event(event_id)
    if not event:
        raise HTTPException(status_code=404, detail=f"Event {event_id} not found")

    conversation = event.conversation
    role_last_seen_turn = 0
    gap_from_turn = 0

    if since is not None:
        gap_from_turn = since
        turns = [t for t in conversation if t.turn > since]
    elif role:
        for t in reversed(conversation):
            if t.actor == role:
                role_last_seen_turn = t.turn
                break
        gap_from_turn = role_last_seen_turn
        turns = [t for t in conversation if t.turn > role_last_seen_turn]
    else:
        turns = list(conversation)

    return {
        "turns": [t.model_dump() for t in turns],
        "total": len(conversation),
        "event_status": event.status.value,
        "gap_from_turn": gap_from_turn,
        "role_last_seen_turn": role_last_seen_turn,
    }


class PlanStepRequest(BaseModel):
    """Request body for plan step status update from agent sidecar."""
    step_id: str = Field(..., description="Step ID from the plan")
    status: str = Field(..., description="in_progress, completed, blocked, red_locked, or green_verified")
    notes: str = Field("", description="What was done or why blocked")
    role: str = Field("", description="Agent role (auto-set by sidecar proxy)")
    event_id: str = Field("", description="Event ID (auto-set by sidecar proxy)")
    test_evidence: dict | None = Field(default=None, description="Test runner execution output, exit code, and failure assertion")


@router.post("/{event_id}/plan-step")
async def update_plan_step(
    event_id: str,
    req: PlanStepRequest,
    blackboard: BlackboardState = Depends(get_blackboard),
):
    """Update a plan step status. Called by agent sidecars via bb_update_plan_step MCP tool.

    Uses brain.append_and_broadcast to go through the standard broadcast pipeline
    (WS push to UI, Slack mirror, agent blackboard_update).
    """
    from ..dependencies import get_brain
    brain = await get_brain()
    event = await blackboard.get_event(event_id)
    if not event:
        raise HTTPException(status_code=404, detail=f"Event {event_id} not found")

    task_payload = {"step_id": req.step_id, "status": req.status}
    if req.test_evidence is not None:
        task_payload["test_evidence"] = req.test_evidence

    turn = ConversationTurn(
        turn=(await brain.next_turn_number(event_id)),
        actor=req.role or "agent",
        action="plan_step",
        thoughts=req.notes or f"Step {req.step_id}: {req.status}",
        taskForAgent=task_payload,
    )
    await brain.append_and_broadcast(event_id, turn)

    if req.status == "red_locked":
        await blackboard.stamp_event(event_id, red_locked_at=time.time())
    elif req.status == "green_verified":
        red_locked_at = getattr(event, "red_locked_at", None)
        if red_locked_at is not None:
            cycle_sec = max(0.0, time.time() - red_locked_at)
            await blackboard.stamp_event(event_id, atdd_cycle_sec=cycle_sec)

    return {"ok": True, "turn": turn.turn}


@router.get("/{event_id}", response_model=EventDocument)
async def get_event_document(
    event_id: str,
    blackboard: BlackboardState = Depends(get_blackboard),
):
    """Get full event document with conversation timeline."""
    event = await blackboard.get_event(event_id)
    if not event:
        raise HTTPException(status_code=404, detail=f"Event {event_id} not found")
    if not event.token_usage:
        try:
            from src.agents.llm import get_token_meter
            live = get_token_meter().peek_event(event_id)
            if live:
                event.token_usage = live
        except Exception:
            pass
    return event


@router.patch("/{event_id}/title")
async def update_event_title(
    request: Request,
    event_id: str,
    req: TitleUpdateRequest,
    blackboard: BlackboardState = Depends(get_blackboard),
    brain = Depends(get_brain),
) -> dict:
    """Rename an event.

    Permitted for event creator or approver/admin on chat/slack events.
    """
    event = await blackboard.get_event(event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    if event.status in (EventStatus.CLOSED, EventStatus.RESOLVED):
        raise HTTPException(status_code=409, detail="Cannot rename closed event")

    user = get_user_from_request(request)
    from .. import auth
    auth_enabled = bool(auth.DEX_ENABLED or auth.TRUSTED_PROXY_ENABLED)
    if auth_enabled and not user.email:
        raise HTTPException(status_code=401, detail="Authentication required")

    if not can_rename_event(
        event.created_by_email,
        user.email,
        event.source,
        user.roles,
        auth_enabled=auth_enabled,
    ):
        logger.warning(
            "[Audit] Denied title rename: user=%s event=%s source=%s",
            user.email, event_id, event.source,
        )
        raise HTTPException(status_code=403, detail="Forbidden")

    if req.title == getattr(event, "title", None):
        if getattr(event, "title_source", None) != "user":
            await blackboard.stamp_event(event_id, title=req.title, title_source="user")
        return {
            "id": event_id,
            "title": req.title,
            "title_source": "user",
        }

    await blackboard.stamp_event(event_id, title=req.title, title_source="user")
    logger.info("[Audit] Event %s renamed by %s (len=%d)", event_id, user.email, len(req.title))
    await brain.broadcast({
        "type": "event_title_updated",
        "event_id": event_id,
        "title": req.title,
        "title_source": "user",
    })
    return {"id": event_id, "title": req.title, "title_source": "user"}


@router.get("/{event_id}/approval")
async def get_event_approval(
    event_id: str,
    blackboard: BlackboardState = Depends(get_blackboard),
):
    """Return approval status and live stamped metadata for Developer sidecar verification."""
    event = await blackboard.get_event(event_id)
    if not event:
        raise HTTPException(status_code=404, detail=f"Event {event_id} not found")

    status_str = event.status.value if hasattr(event.status, "value") else str(event.status)
    is_approved = bool(event.approved_by) and status_str not in (
        EventStatus.WAITING_APPROVAL.value,
        EventStatus.CLOSED.value,
        EventStatus.RESOLVED.value,
    )
    raw_req = getattr(event, "approval_requested_sha", None)
    req_sha = raw_req if isinstance(raw_req, str) and raw_req else None
    ctx_sha = extract_context_head_sha(event)
    sha_drifted = bool(req_sha and isinstance(ctx_sha, str) and ctx_sha and ctx_sha != req_sha)
    return {
        "approved": is_approved,
        "approved_by": event.approved_by,
        "approved_mr_id": event.approved_mr_id,
        "approved_mr_sha": event.approved_mr_sha,
        "approval_requested_sha": req_sha,
        "sha_drifted": sha_drifted,
        "event_id": event.id,
        "status": status_str,
    }


from .approval_decision_helpers import ApprovalDecisionOutcome, DecisionRequest, validate_image_attachment
from .approval_decision import execute_approval_decision


def _map_decision_error_response(outcome: ApprovalDecisionOutcome):
    """Map non-ok ApprovalDecisionOutcome to HTTP status / JSONResponse."""
    if outcome.kind == "image_too_large":
        return JSONResponse(status_code=413, content={"code": outcome.kind, "detail": outcome.message})
    if outcome.kind == "invalid_image":
        return JSONResponse(status_code=422, content={"code": outcome.kind, "detail": f"invalid_image: {outcome.message}"})
    if outcome.kind == "not_found":
        return JSONResponse(status_code=404, content={"code": outcome.kind, "detail": outcome.message})
    if outcome.kind in ("closed", "not_waiting", "stale_approval", "ambiguous_options"):
        return JSONResponse(status_code=409, content={"code": outcome.kind, "detail": outcome.message})
    if outcome.kind in ("sha_drift", "sha_unresolvable"):
        return JSONResponse(
            status_code=409,
            content={
                "code": outcome.kind,
                "detail": outcome.message,
                "approval_requested_sha": outcome.expected_sha,
                "live_sha": outcome.actual_sha,
            },
        )
    if outcome.kind == "auth_rejected":
        return JSONResponse(status_code=403, content={"code": outcome.kind, "detail": outcome.message})
    if outcome.kind == "invalid_image":
        raise HTTPException(status_code=422, detail=f"invalid_image: {outcome.message}")
    return JSONResponse(status_code=400, content={"code": outcome.kind, "detail": outcome.message})


@router.post("/{event_id}/approve")
async def approve_event(
    event_id: str,
    request: Request,
    body: Optional[ApproveRequest] = Body(default=None),
    blackboard: BlackboardState = Depends(get_blackboard),
):
    """Approve a pending plan in an event conversation.

    `user` is intentionally NOT a function parameter: FastAPI has no way to recognize a
    plain dataclass like UserContext as anything other than a request-body model when it
    lacks a Depends()/Body() marker, so declaring it here would let a caller POST
    {"email": "...", "roles": [...]} and self-assign identity/roles, bypassing auth and
    the RBAC gate below entirely. Identity is always resolved server-side from the request.
    """
    event = await blackboard.get_event(event_id)
    if not event:
        raise HTTPException(status_code=404, detail=f"Event {event_id} not found")

    from .. import auth  # module reference (not the stale module-level DEX_ENABLED/
    # TRUSTED_PROXY_ENABLED import above) so tests monkeypatching src.auth.DEX_ENABLED
    # are observed -- `from ..auth import DEX_ENABLED` at module load time freezes the
    # value at import time and would never see a later monkeypatch.
    user = get_user_from_request(request)

    auth_enabled = bool(auth.DEX_ENABLED or auth.TRUSTED_PROXY_ENABLED)
    if auth_enabled and not user.email:
        raise HTTPException(status_code=401, detail="Authentication required")

    if not can_approve_event(user, event, auth_enabled=auth_enabled):
        logger.warning(
            "Forbidden approval attempt on event %s by user %s (roles=%s)",
            event_id, user.email, user.roles,
        )
        raise HTTPException(status_code=403, detail="Forbidden: User not authorized to approve this event")

    expected_sha = body.expected_sha if isinstance(body, ApproveRequest) else None
    if isinstance(getattr(event, "pending_approval", None), PendingApproval):
        try:
            brain = await get_brain()
        except RuntimeError:
            brain = None
        _resolver = resolve_live_head_sha if resolve_live_head_sha is not _ORIG_RESOLVE_LIVE_HEAD_SHA else None
        outcome = await execute_approval_decision(
            blackboard=blackboard,
            brain=brain,
            event_id=event_id,
            user=user,
            auth_enabled=auth_enabled,
            req=DecisionRequest(expected_sha=expected_sha),
            legacy_mode="approve",
            head_sha_resolver=_resolver,
        )
        if outcome.kind != "ok":
            return _map_decision_error_response(outcome)
        updated = await blackboard.get_event(event_id)
        return {
            "status": "approved",
            "event_id": event_id,
            "approved_by": user.email or user.label,
            "approved_mr_id": getattr(updated, "approved_mr_id", None) if updated else None,
            "approved_mr_sha": getattr(updated, "approved_mr_sha", None) if updated else None,
        }

    try:
        _resolver = resolve_live_head_sha if resolve_live_head_sha is not _ORIG_RESOLVE_LIVE_HEAD_SHA else _vcs_approval.resolve_live_head_sha
        mr_id, mr_sha = await _resolver(event)
    except Exception as exc:
        logger.warning("approve_event: resolve_live_head_sha failed for %s (%s)", event_id, type(exc).__name__)
        mr_id, mr_sha = None, None
    fresh_event = await blackboard.get_event(event_id)
    if not fresh_event:
        raise HTTPException(status_code=404, detail=f"Event {event_id} not found")
    drift = check_approval_sha_drift(fresh_event, mr_sha, expected_sha=expected_sha)
    if not drift.allowed:
        return JSONResponse(
            status_code=409,
            content={
                "detail": drift.detail,
                "code": drift.code,
                "approval_requested_sha": drift.approval_requested_sha,
                "live_sha": drift.live_sha,
            },
        )

    clean_by, clean_name = resolve_approval_identity(user.email, user.label)
    raw_fresh_req = getattr(fresh_event, "approval_requested_sha", None)
    fresh_req_sha = raw_fresh_req if isinstance(raw_fresh_req, str) else None

    # Stamp approval metadata onto EventDocument (atomic CAS)
    stamp_res = blackboard.stamp_event(
        event_id,
        _expected_requested_sha=fresh_req_sha,
        approved_by=clean_by,
        approved_mr_id=mr_id,
        approved_mr_sha=mr_sha,
        approval_requested_sha=None,
    )
    stamped = await stamp_res if inspect.isawaitable(stamp_res) else stamp_res
    if stamped is False:
        return JSONResponse(
            status_code=409,
            content={
                "detail": "Event state changed concurrently; please refresh and retry.",
                "code": "closed",
                "approval_requested_sha": fresh_req_sha,
                "live_sha": mr_sha,
            },
        )

    thought_msg = "User approved the plan."
    if mr_id and mr_sha:
        thought_msg = f"User approved plan for MR/PR !{mr_id} at HEAD {mr_sha[:8]}."

    turn = ConversationTurn(
        turn=len(fresh_event.conversation) + 1,
        actor="user",
        action="approve",
        thoughts=thought_msg,
        user_name=clean_name,
        approved_by=clean_by,
        approved_mr_id=mr_id,
        approved_mr_sha=mr_sha,
    )
    await blackboard.append_turn(event_id, turn)

    try:
        brain = await get_brain()
        brain.clear_waiting(event_id)
        resumed = await brain.resume_if_parked(event_id)
        brain.enqueue_for_processing(event_id)
        if not resumed:
            logger.info(f"approve_event: {event_id} was not in waiting_approval (already resumed or race)")
    except RuntimeError:
        pass  # Brain not initialized (unlikely in normal operation)

    logger.info(f"User {user.label} approved event {event_id} (mr_id={mr_id}, sha={mr_sha})")
    return {
        "status": "approved",
        "event_id": event_id,
        "approved_by": user.email or user.label,
        "approved_mr_id": mr_id,
        "approved_mr_sha": mr_sha,
    }


@router.post("/{event_id}/reject")
async def reject_event(
    event_id: str,
    request: Request,
    body: RejectRequest = RejectRequest(),
    blackboard: BlackboardState = Depends(get_blackboard),
):
    """Reject a pending plan in an event conversation.

    Gated by the same can_approve_event() check as approve_event: rejecting a plan is the
    same state transition (brain.resume_if_parked / enqueue_for_processing) that approval
    requires authorization for, so an unauthenticated/unauthorized caller must not be able
    to reject another user's pending plan either.
    """
    event = await blackboard.get_event(event_id)
    if not event:
        raise HTTPException(status_code=404, detail=f"Event {event_id} not found")

    from .. import auth  # see approve_event -- module reference so monkeypatched
    # src.auth.DEX_ENABLED/TRUSTED_PROXY_ENABLED are observed, not the frozen import above.
    user = get_user_from_request(request)
    auth_enabled = bool(auth.DEX_ENABLED or auth.TRUSTED_PROXY_ENABLED)
    if auth_enabled and not user.email:
        raise HTTPException(status_code=401, detail="Authentication required")

    if not can_approve_event(user, event, auth_enabled=auth_enabled):
        logger.warning(
            "Forbidden rejection attempt on event %s by user %s (roles=%s)",
            event_id, user.email, user.roles,
        )
        raise HTTPException(status_code=403, detail="Forbidden: User not authorized to reject this event")

    if body.image:
        img_err = validate_image_attachment(body.image)
        if img_err == "image_too_large":
            raise HTTPException(status_code=413, detail="Image too large (max 1MB)")
        elif img_err:
            raise HTTPException(status_code=422, detail=f"invalid_image: {img_err}")

    if isinstance(getattr(event, "pending_approval", None), PendingApproval):
        try:
            brain = await get_brain()
        except RuntimeError:
            brain = None
        outcome = await execute_approval_decision(
            blackboard=blackboard,
            brain=brain,
            event_id=event_id,
            user=user,
            auth_enabled=auth_enabled,
            req=DecisionRequest(reject_reason=body.reason, image=body.image),
            legacy_mode="reject",
            head_sha_resolver=None,
        )
        if outcome.kind != "ok":
            return _map_decision_error_response(outcome)
        return {"status": "rejected", "event_id": event_id}

    # A rejection supersedes any prior approval stamp on this event -- otherwise
    # GET /{event_id}/approval keeps reporting approved=true with a stale approved_mr_sha
    # from an earlier (now-superseded) plan revision at the same commit SHA.
    if (
        event.approved_by
        or event.approved_mr_id
        or event.approved_mr_sha
        or getattr(event, "approval_requested_sha", None)
    ):
        clear_res = blackboard.stamp_event(
            event_id,
            approved_by=None,
            approved_mr_id=None,
            approved_mr_sha=None,
            approval_requested_sha=None,
        )
        if inspect.isawaitable(clear_res):
            await clear_res

    turn = ConversationTurn(
        turn=len(event.conversation) + 1,
        actor="user",
        action="reject",
        thoughts=body.reason,
        image=body.image,
    )
    await blackboard.append_turn(event_id, turn)

    try:
        brain = await get_brain()
        brain.clear_waiting(event_id)
        resumed = await brain.resume_if_parked(event_id)
        brain.enqueue_for_processing(event_id)
        if not resumed:
            logger.info(f"reject_event: {event_id} was not in waiting_approval (already resumed or race)")
    except RuntimeError:
        pass  # Brain not initialized (unlikely in normal operation)

    logger.info(f"User rejected event {event_id}: {body.reason}")
    return {"status": "rejected", "event_id": event_id}


class CloseRequest(BaseModel):
    """Typed request body for user force-close."""
    reason: str = Field("User force-closed the event.", description="Close reason")


@router.post("/{event_id}/close")
async def close_event_by_user(
    event_id: str,
    body: CloseRequest = CloseRequest(),
    blackboard: BlackboardState = Depends(get_blackboard),
):
    """Force-close an event from the UI. Uses existing close_event state machine."""
    event = await blackboard.get_event(event_id)
    if not event:
        raise HTTPException(status_code=404, detail=f"Event {event_id} not found")
    if event.status == EventStatus.CLOSED:
        raise HTTPException(status_code=409, detail="Event already closed")

    close_summary = f"User force-closed: {body.reason}"
    # Cancel any running agent task before closing (prevents orphaned CLI processes)
    try:
        brain = await get_brain()
        await brain.cancel_active_task(event_id, f"User force-close: {body.reason}")
        brain.cancel_subscription(event_id)
        brain.clear_cycle_id(event_id)
        brain.clear_waiting(event_id)
        brain.cleanup_jarvis_event_state(event_id)
    except RuntimeError:
        pass  # Brain not initialized
    token_usage = None
    try:
        from src.agents.llm import get_token_meter
        token_usage = get_token_meter().drain_event(event_id)
    except Exception:
        pass
    await blackboard.close_event(event_id, close_summary, close_reason="user_closed", token_usage=token_usage)
    # Clean up Slack thread mapping if event had Slack context
    if event.slack_channel_id and event.slack_thread_ts:
        await blackboard.delete_slack_mapping(event.slack_channel_id, event.slack_thread_ts)
    # Persist report snapshot (non-fatal)
    try:
        await blackboard.persist_report(event_id)
    except Exception as e:
        logger.warning(f"Report persistence failed for {event_id} (non-fatal): {e}")
    # Write to ops journal so Brain has temporal context for this closure
    await blackboard.append_journal(
        event.service,
        f"{event.event.reason} -- user force-closed. {body.reason}"
    )
    # Archive to deep memory (fire-and-forget, same path as Brain._close_and_broadcast)
    try:
        brain = await get_brain()
        archivist = brain.agents.get("_archivist_memory")
        if archivist and hasattr(archivist, "archive_event"):
            closed_event = await blackboard.get_event(event_id)
            if closed_event:
                asyncio.create_task(archivist.archive_event(closed_event))
    except Exception as e:
        logger.warning(f"Deep memory archive failed for {event_id} (non-fatal): {e}")
    logger.info(f"User force-closed event {event_id}: {body.reason}")
    return {"status": "closed", "event_id": event_id}


class EnforceCasualRequest(BaseModel):
    reason: str = Field(
        "User enforced casual domain.", max_length=2000, description="Override reason"
    )


@router.post("/{event_id}/enforce-casual")
async def enforce_casual_domain(
    event_id: str,
    body: EnforceCasualRequest = EnforceCasualRequest(),
    blackboard: BlackboardState = Depends(get_blackboard),
    user: UserContext = Depends(require_auth),
):
    """Force event domain to casual from the UI (human override).

    Requires authentication. Source-restricted server-side to chat/slack.
    """
    event = await blackboard.get_event(event_id)
    if not event:
        raise HTTPException(status_code=404, detail=f"Event {event_id} not found")
    if event.status == EventStatus.CLOSED:
        raise HTTPException(status_code=409, detail="Cannot modify a closed event")
    # Ownership check (codereview finding: auth-rbac) -- require_auth only proves the
    # caller is *someone*, not that they own this event. can_override_domain is strictly
    # deny-by-default: unowned/automated events (created_by_email=None) can NEVER be
    # forced to casual. Only the event creator can override domain.
    if not can_override_domain(event.created_by_email, user.email):
        logger.warning(
            "[Audit] Denied domain override: event_id=%s caller_email=%s owner_email=%s",
            event_id, user.email, event.created_by_email,
        )
        raise HTTPException(status_code=403, detail="Not authorized to override this event's domain")
    if event.source not in ("chat", "slack"):
        raise HTTPException(status_code=400, detail="Casual domain override is only valid for chat/slack events")

    try:
        brain = await get_brain()
    except RuntimeError:
        raise HTTPException(status_code=503, detail="Brain not available")

    applied = await brain.enforce_domain_override(event_id, "casual", body.reason, user.label)
    if not applied:
        # Same 409 as the pre-check above -- Brain's own re-check inside the lock
        # covers the identical "closed" condition (TOCTOU window) plus the
        # deferred/ineligible-status case; a client can't usefully distinguish
        # these, so they share one message (codereview finding, C2).
        raise HTTPException(status_code=409, detail="Cannot modify a closed event")

    return {"status": "enforced", "event_id": event_id, "domain": "casual"}


@router.get("/{event_id}/report")
async def get_event_report(
    event_id: str,
    blackboard: BlackboardState = Depends(get_blackboard),
):
    """Get full event report as Markdown with service metadata and architecture."""
    event = await blackboard.get_event(event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    service_meta = await blackboard.get_service(event.service)

    from ..utils.event_markdown import event_to_markdown
    content = event_to_markdown(event, service_meta, "")

    # Add journal context
    journal = await blackboard.get_journal(event.service)
    if journal:
        content += "\n\n## Service Ops Journal\n\n"
        for entry in journal:
            content += f"- {entry}\n"

    return {"markdown": content, "event_id": event_id}


@router.get("/closed/list")
async def list_closed_events(
    limit: int = Query(50, ge=1, le=200),
    blackboard: BlackboardState = Depends(get_blackboard),
):
    """Get recently closed events."""
    closed_ids = await blackboard.get_recently_closed_event_ids(
        limit=limit, since_seconds=86400,
    )
    events = []
    for eid in closed_ids:
        event = await blackboard.get_event(eid)
        if event:
            events.append({
                "id": event.id,
                "title": getattr(event, "title", None),
                "title_source": getattr(event, "title_source", None),
                "source": event.source,
                "service": event.service,
                "subject_type": getattr(event, "subject_type", "service"),
                "status": event.status.value,
                "reason": event.event.reason,
                "evidence": _serialize_evidence(event),
                "turns": len(event.conversation),
                "created": event.event.timeDate,
                "created_by_email": event.created_by_email,
                "token_total": event.token_usage.get("total_tokens") if event.token_usage else None,
            })
    return events


@router.post("/admin/rebuild-deep-memory")
async def rebuild_deep_memory(
    blackboard: BlackboardState = Depends(get_blackboard),
):
    """Re-archive all closed events to Qdrant deep memory.

    Idempotent: Archivist uses deterministic uuid5 point IDs so
    re-running upserts over existing vectors without duplication.
    Rate-limited to ~2 calls/sec to respect Gemini Flash API quotas.
    """
    try:
        archivist = await get_archivist()
    except RuntimeError:
        raise HTTPException(503, "Archivist not available")

    closed_ids = await blackboard.get_all_closed_event_ids()
    if not closed_ids:
        return {"archived": 0, "skipped": 0, "failed": 0, "total": 0}

    archived, skipped, failed = 0, 0, 0
    for eid in closed_ids:
        event = await blackboard.get_event(eid)
        if not event or not event.conversation:
            skipped += 1
            continue
        try:
            await archivist.archive_event(event)
            archived += 1
            await asyncio.sleep(0.5)
        except Exception as e:
            logger.warning(f"Rebuild archive failed for {eid}: {e}")
            failed += 1
            if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
                await asyncio.sleep(5)

    logger.info(
        f"Deep memory rebuild: {archived} archived, "
        f"{skipped} skipped, {failed} failed (total {len(closed_ids)})"
    )
    return {
        "archived": archived,
        "skipped": skipped,
        "failed": failed,
        "total": len(closed_ids),
    }


# =============================================================================
# Admin: Corrective Memory + Lessons Learned
# =============================================================================


class CorrectMemoryRequest(BaseModel):
    event_id: str
    corrected_root_cause: str = Field(max_length=5000)
    corrected_fix_action: str = Field(max_length=5000)
    correction_note: str = Field(default="", max_length=2000)


class LessonRequest(BaseModel):
    title: str = Field(max_length=500)
    pattern: str = Field(max_length=5000)
    anti_pattern: str = Field(default="", max_length=5000)
    keywords: list[str] = Field(default_factory=list)
    event_references: list[str] = Field(default_factory=list)
    channel: str = Field(default="external", pattern=r"^(external|experience)$")


@router.get("/admin/memories")
async def scroll_memories(
    limit: int = Query(default=50, ge=1, le=200),
    cursor: Optional[str] = Query(default=None, max_length=500, description="Opaque cursor from a prior page's next_cursor"),
    service: Optional[str] = Query(default=None, max_length=200, description="Filter by service (indexed)"),
    q: Optional[str] = Query(default=None, max_length=200, description="Substring match on symptom/service, applied to this page only"),
):
    """One page of archived event memories from Qdrant. Envelope: {items, next_cursor, has_more}."""
    try:
        archivist = await get_archivist()
    except RuntimeError:
        raise HTTPException(503, "Archivist not available")
    qdrant_filter = {"must": [{"key": "service", "match": {"value": service}}]} if service else None
    result = await archivist.scroll_memories(limit=limit, offset=cursor, filter=qdrant_filter)
    items = result.get("items", [])
    if q:
        ql = q.lower()
        items = [
            p for p in items
            if ql in str(p.get("payload", {}).get("symptom", "")).lower()
            or ql in str(p.get("payload", {}).get("service", "")).lower()
        ]
    next_offset = result.get("next_offset")
    return {"items": items, "next_cursor": next_offset, "has_more": next_offset is not None}


@router.get("/admin/memories/{event_id}")
async def get_memory(event_id: str):
    """Get a single event memory by event_id."""
    try:
        archivist = await get_archivist()
    except RuntimeError:
        raise HTTPException(503, "Archivist not available")
    result = await archivist.get_memory(event_id)
    if not result:
        raise HTTPException(404, f"Memory not found for {event_id}")
    return result


@router.post("/admin/correct-memory")
async def correct_memory(req: CorrectMemoryRequest):
    """Overwrite a contaminated event memory with corrected root cause."""
    try:
        archivist = await get_archivist()
    except RuntimeError:
        raise HTTPException(503, "Archivist not available")
    success = await archivist.correct_memory(
        event_id=req.event_id,
        corrected_root_cause=req.corrected_root_cause,
        corrected_fix_action=req.corrected_fix_action,
        correction_note=req.correction_note,
    )
    if not success:
        raise HTTPException(404, f"Event {req.event_id} not found in deep memory")
    return {"status": "corrected", "event_id": req.event_id}


@router.get("/admin/lessons")
async def scroll_lessons(
    limit: int = Query(default=50, ge=1, le=200),
    cursor: Optional[str] = Query(default=None, max_length=500, description="Opaque cursor from a prior page's next_cursor"),
    channel: Optional[str] = Query(default=None, max_length=200, description="Filter by channel (external/experience) -- no Qdrant index, applied to this page only"),
    q: Optional[str] = Query(default=None, max_length=200, description="Substring match on title/pattern, applied to this page only"),
):
    """One page of lessons learned from Qdrant. Envelope: {items, next_cursor, has_more}."""
    try:
        archivist = await get_archivist()
    except RuntimeError:
        raise HTTPException(503, "Archivist not available")
    result = await archivist.scroll_lessons(limit=limit, offset=cursor)
    items = result.get("items", [])
    if channel:
        items = [
            p for p in items
            if p.get("payload", {}).get("channel", "external") == channel
        ]
    if q:
        ql = q.lower()
        items = [
            p for p in items
            if ql in str(p.get("payload", {}).get("title", "")).lower()
            or ql in str(p.get("payload", {}).get("pattern", "")).lower()
        ]
    next_offset = result.get("next_offset")
    return {"items": items, "next_cursor": next_offset, "has_more": next_offset is not None}


@router.get("/admin/lessons/{lesson_id}")
async def get_lesson(lesson_id: str):
    """Get a single lesson by lesson_id."""
    try:
        archivist = await get_archivist()
    except RuntimeError:
        raise HTTPException(503, "Archivist not available")
    result = await archivist.get_lesson(lesson_id)
    if not result:
        raise HTTPException(404, f"Lesson {lesson_id} not found")
    return result


@router.post("/admin/lessons")
async def create_lesson(req: LessonRequest):
    """Store a new lesson learned."""
    try:
        archivist = await get_archivist()
    except RuntimeError:
        raise HTTPException(503, "Archivist not available")
    lesson_id = await archivist.store_lesson(
        title=req.title,
        pattern=req.pattern,
        anti_pattern=req.anti_pattern,
        keywords=req.keywords,
        event_references=req.event_references,
        channel=req.channel,
    )
    if not lesson_id:
        raise HTTPException(503, "Failed to store lesson")
    return {"status": "stored", "lesson_id": lesson_id}


CHANNEL_DEMOTION = {"external": "experience"}


@router.patch("/admin/lessons/{lesson_id}/demote")
async def demote_lesson(lesson_id: str):
    """Demote a lesson: external -> experience.

    Returns 409 if already at experience (lowest).
    Missing channel field on legacy lessons defaults to 'external'.
    """
    try:
        archivist = await get_archivist()
    except RuntimeError:
        raise HTTPException(503, "Archivist not available")

    if not await archivist._ensure_initialized():
        raise HTTPException(503, "Archivist storage not available")

    points = await archivist._vector_store.get_points(
        "darwin_lessons",
        [lesson_id],
    )
    if not points:
        raise HTTPException(404, f"Lesson {lesson_id} not found")

    payload = points[0].get("payload", {})
    current_channel = payload.get("channel", "external")
    new_channel = CHANNEL_DEMOTION.get(current_channel)
    if not new_channel:
        raise HTTPException(409, f"Lesson already at lowest channel ({current_channel})")

    payload["channel"] = new_channel

    embed_text = (
        f"{payload.get('title', '')} {payload.get('pattern', '')} "
        f"{payload.get('anti_pattern', '')} {' '.join(payload.get('keywords', []))}"
    )
    vector = await archivist._embed(embed_text)

    await archivist._vector_store.upsert(
        collection="darwin_lessons",
        point_id=lesson_id,
        vector=vector,
        payload=payload,
    )
    logger.info(f"Lesson {lesson_id} demoted: {current_channel} -> {new_channel}")
    return {"status": "demoted", "lesson_id": lesson_id, "channel": new_channel}


@router.patch("/admin/lessons/{lesson_id}/verify")
async def verify_lesson(lesson_id: str):
    """Increment verification_count for a lesson. Auto-promotes experience→external at count >= 3.

    Missing verification_count on legacy lessons defaults to 0.
    """
    try:
        archivist = await get_archivist()
    except RuntimeError:
        raise HTTPException(503, "Archivist not available")

    if not await archivist._ensure_initialized():
        raise HTTPException(503, "Archivist storage not available")

    points = await archivist._vector_store.get_points(
        "darwin_lessons",
        [lesson_id],
    )
    if not points:
        raise HTTPException(404, f"Lesson {lesson_id} not found")

    payload = points[0].get("payload", {})
    new_count = payload.get("verification_count", 0) + 1
    payload["verification_count"] = new_count

    promoted = False
    if new_count >= 3 and payload.get("channel") == "experience":
        payload["channel"] = "external"
        payload["promoted_at"] = time.time()
        promoted = True
        logger.info(f"Lesson {lesson_id} promoted: experience → external (verification_count={new_count})")

    embed_text = (
        f"{payload.get('title', '')} {payload.get('pattern', '')} "
        f"{payload.get('anti_pattern', '')} {' '.join(payload.get('keywords', []))}"
    )
    vector = await archivist._embed(embed_text)

    await archivist._vector_store.upsert(
        collection="darwin_lessons",
        point_id=lesson_id,
        vector=vector,
        payload=payload,
    )
    logger.info(f"Lesson {lesson_id} verified: count={new_count}")
    result = {"status": "verified", "lesson_id": lesson_id, "verification_count": new_count}
    if promoted:
        result["promoted"] = True
        result["channel"] = "external"
    return result


@router.delete("/admin/lessons/{lesson_id}")
async def delete_lesson(lesson_id: str):
    """Delete a lesson by ID.

    Uses get_lesson() (direct point lookup) rather than scanning list_lessons(limit=500) --
    the old scan silently 404'd on any lesson beyond the 500th stored.
    """
    try:
        archivist = await get_archivist()
    except RuntimeError:
        raise HTTPException(503, "Archivist not available")
    existing = await archivist.get_lesson(lesson_id)
    if not existing:
        raise HTTPException(404, f"Lesson {lesson_id} not found")
    success = await archivist.delete_lesson(lesson_id)
    if not success:
        raise HTTPException(503, "Failed to delete lesson from Qdrant")
    return {"status": "deleted", "lesson_id": lesson_id}


class LessonExtractionRequest(BaseModel):
    document: str
    event_ids: list[str] = Field(default_factory=list)
    context_notes: str = ""


class LessonApplyRequest(BaseModel):
    lessons: list[LessonRequest] = Field(default_factory=list)
    corrections: list[CorrectMemoryRequest] = Field(default_factory=list)


@router.post("/admin/lessons/extract")
async def extract_lessons(
    req: LessonExtractionRequest,
    blackboard: BlackboardState = Depends(get_blackboard),
):
    """Extract structured lessons + corrections from a raw document using Claude.

    Optionally cross-references Darwin event reports for richer extraction.
    """
    try:
        archivist = await get_archivist()
    except RuntimeError:
        raise HTTPException(503, "Archivist not available")

    event_reports: dict[str, str] = {}
    if req.event_ids:
        from ..utils.event_markdown import event_to_markdown
        for eid in req.event_ids[:10]:
            event = await blackboard.get_event(eid)
            if event:
                event_reports[eid] = event_to_markdown(event)

    result = await archivist.extract_lessons(
        document=req.document,
        event_reports=event_reports or None,
        context_notes=req.context_notes,
    )
    if "error" in result:
        raise HTTPException(422, result)
    return result


@router.post("/admin/lessons/apply")
async def apply_lessons(req: LessonApplyRequest):
    """Store confirmed lessons and apply confirmed corrections in one call."""
    try:
        archivist = await get_archivist()
    except RuntimeError:
        raise HTTPException(503, "Archivist not available")

    stored_lessons = 0
    applied_corrections = 0

    for lesson in req.lessons:
        lid = await archivist.store_lesson(
            title=lesson.title,
            pattern=lesson.pattern,
            anti_pattern=lesson.anti_pattern,
            keywords=lesson.keywords,
            event_references=lesson.event_references,
            channel=lesson.channel,
        )
        if lid:
            stored_lessons += 1

    for correction in req.corrections:
        ok = await archivist.correct_memory(
            event_id=correction.event_id,
            corrected_root_cause=correction.corrected_root_cause,
            corrected_fix_action=correction.corrected_fix_action,
            correction_note=correction.correction_note,
        )
        if ok:
            applied_corrections += 1

    return {
        "stored_lessons": stored_lessons,
        "applied_corrections": applied_corrections,
    }


# =============================================================================
# Admin: Knowledge Base
# =============================================================================


class KnowledgeRequest(BaseModel):
    topic: str = Field(..., min_length=1, max_length=200)
    fact: str = Field(..., min_length=1, max_length=2000)
    scope: str = Field(..., pattern=r"^(convention|ownership|historical|relationship)$")
    source: str = Field(..., min_length=1, max_length=200)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    valid_until: float | None = None
    service: str | None = Field(default=None, max_length=200, pattern=r"^[a-zA-Z0-9_\-.]+$")


class KnowledgeUpdateRequest(BaseModel):
    # service is immutable (part of uuid5 identity) -- set at creation, not updatable.
    model_config = ConfigDict(extra="forbid")
    fact: str | None = Field(default=None, max_length=2000)
    source: str | None = Field(default=None, max_length=200)
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    valid_until: float | None = None


@router.post("/admin/knowledge")
async def create_knowledge(req: KnowledgeRequest):
    """Store a knowledge fact (upsert: one fact per topic+scope)."""
    try:
        archivist = await get_archivist()
    except RuntimeError:
        raise HTTPException(503, "Archivist not available")
    knowledge_id = await archivist.store_knowledge(**req.model_dump())
    if not knowledge_id:
        raise HTTPException(503, "Failed to store knowledge fact")
    return {"status": "stored", "knowledge_id": knowledge_id}


@router.get("/admin/knowledge")
async def scroll_knowledge(
    limit: int = Query(default=50, ge=1, le=200),
    cursor: Optional[str] = Query(default=None, max_length=500, description="Opaque cursor from a prior page's next_cursor"),
    scope: Optional[str] = Query(default=None, max_length=200, description="Filter by scope (indexed)"),
    service: Optional[str] = Query(default=None, max_length=200, description="Filter by service (indexed)"),
    q: Optional[str] = Query(default=None, max_length=200, description="Substring match on topic/fact, applied to this page only"),
):
    """One page of knowledge facts from Qdrant. Envelope: {items, next_cursor, has_more}.

    Never `limit=0` -- cursor absence just means "first page". ge=1/le=200 stays
    tight (the old le=1000 + a client-side default=100 was a double clamp that
    masked the unread tail; this pagination contract replaces it, not raises it).
    """
    try:
        archivist = await get_archivist()
    except RuntimeError:
        raise HTTPException(503, "Archivist not available")
    conditions = []
    if scope:
        conditions.append({"key": "scope", "match": {"value": scope}})
    if service:
        conditions.append({"key": "service", "match": {"value": service}})
    qdrant_filter = {"must": conditions} if conditions else None
    result = await archivist.scroll_knowledge(limit=limit, offset=cursor, filter=qdrant_filter)
    items = result.get("items", [])
    if q:
        ql = q.lower()
        items = [
            p for p in items
            if ql in str(p.get("payload", {}).get("topic", "")).lower()
            or ql in str(p.get("payload", {}).get("fact", "")).lower()
        ]
    next_offset = result.get("next_offset")
    return {"items": items, "next_cursor": next_offset, "has_more": next_offset is not None}


@router.get("/admin/knowledge/{knowledge_id}")
async def get_knowledge(knowledge_id: str):
    """Get a single knowledge fact by ID."""
    try:
        archivist = await get_archivist()
    except RuntimeError:
        raise HTTPException(503, "Archivist not available")
    result = await archivist.get_knowledge(knowledge_id)
    if not result:
        raise HTTPException(404, f"Knowledge {knowledge_id} not found")
    return result


@router.delete("/admin/knowledge/{knowledge_id}")
async def delete_knowledge(knowledge_id: str):
    """Delete a knowledge fact by ID."""
    try:
        archivist = await get_archivist()
    except RuntimeError:
        raise HTTPException(503, "Archivist not available")
    success = await archivist.delete_knowledge(knowledge_id)
    if not success:
        raise HTTPException(404, f"Knowledge {knowledge_id} not found")
    return {"status": "deleted", "knowledge_id": knowledge_id}


@router.patch("/admin/knowledge/{knowledge_id}")
async def update_knowledge(knowledge_id: str, req: KnowledgeUpdateRequest):
    """Update mutable fields of a knowledge fact (re-embeds + upserts).

    Identity fields (topic, scope) are immutable. KnowledgeUpdateRequest with
    extra='forbid' returns 422 if the client sends them.
    """
    try:
        archivist = await get_archivist()
    except RuntimeError:
        raise HTTPException(503, "Archivist not available")

    updates = req.model_dump(exclude_unset=True)
    if not updates:
        return {"status": "no_changes", "knowledge_id": knowledge_id}

    success = await archivist.update_knowledge(knowledge_id, **updates)
    if not success:
        raise HTTPException(404, f"Knowledge {knowledge_id} not found")
    return {"status": "updated", "knowledge_id": knowledge_id}


@router.get("/aligner/pending", response_model=list[PendingAnomaly])
async def aligner_pending_items(
    blackboard: BlackboardState = Depends(get_blackboard),
):
    """Pending anomalies in the Aligner dwell queue."""
    members = await blackboard.redis.zrange(
        "darwin:aligner:pending", 0, -1, withscores=True
    )
    result = []
    for member, score in members:
        meta_json = await blackboard.redis.hget(
            "darwin:aligner:pending:meta", member
        )
        meta = {} if meta_json is None else json.loads(meta_json)
        target, scope = member.split("|", 1) if "|" in member else (member, "unknown")
        result.append({"key": member, "target": target, "first_seen": score, **meta})
    return result


@router.get("/jenkins/pending", response_model=list[JenkinsPendingItem])
async def jenkins_pending_items(
    blackboard: BlackboardState = Depends(get_blackboard),
):
    """Pending CI signals in the Jenkins dwell queue.

    Key format: {job_name} or view-outage:{view}.
    """
    members = await blackboard.redis.zrange(
        "darwin:jenkins:pending", 0, -1, withscores=True
    )
    result = []
    for member, score in members:
        meta_json = await blackboard.redis.hget(
            "darwin:jenkins:pending:meta", member
        )
        meta = {} if meta_json is None else json.loads(meta_json)
        result.append({
            "key": member,
            "target": meta.get("job_name") or member,
            "first_seen": score,
            **meta,
        })
    return result


_HH_SEGMENT_RE = re.compile(r"^[A-Za-z0-9_.-]+$")
_HH_GITLAB_PATH_RE = re.compile(r"^[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)*$")
_HH_OPERATOR_DEBOUNCE_S = 10.0
_hh_last_poll_ts: float | None = None
_hh_last_breaker_reset_ts: dict[str, float] = {}
_hh_last_item_action_ts: dict[tuple[str, str, int], float] = {}
_ACTIVE_HH_EVENT_STATUSES = frozenset({
    EventStatus.NEW.value,
    EventStatus.ACTIVE.value,
    EventStatus.DEFERRED.value,
    EventStatus.WAITING_APPROVAL.value,
})


class HeadhunterItemActionRequest(BaseModel):
    """Strict request model for operator queue item actions (no arbitrary URLs)."""

    model_config = ConfigDict(extra="forbid")

    platform: Literal["gitlab", "github"]
    project_id: Optional[int | str] = None
    owner: Optional[str] = Field(None, max_length=200)
    repo: Optional[str] = Field(None, max_length=200)
    item_number: int = Field(..., ge=1)
    is_issue: bool = False

    @field_validator("owner", "repo")
    @classmethod
    def _validate_gh_segment(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        if v in (".", "..") or not _HH_SEGMENT_RE.fullmatch(v):
            raise ValueError("Invalid repository/owner segment")
        return v

    @field_validator("project_id")
    @classmethod
    def _validate_project_id(cls, v: Optional[int | str]) -> Optional[int | str]:
        if v is None:
            return None
        if isinstance(v, bool):
            raise ValueError("project_id cannot be bool")
        if isinstance(v, int):
            if v < 1:
                raise ValueError("project_id must be >= 1")
            return v
        raw = str(v).strip()
        if (
            not raw
            or ".." in raw
            or any(ch in raw for ch in ("?", "#", "@"))
            or any(ch.isspace() for ch in raw)
            or any(seg in (".", "..") for seg in raw.split("/"))
            or not _HH_GITLAB_PATH_RE.fullmatch(raw)
        ):
            raise ValueError("Invalid GitLab project_id")
        return raw

    @model_validator(mode="after")
    def _validate_platform_target(self) -> "HeadhunterItemActionRequest":
        if self.platform == "github":
            if not self.owner or not self.repo:
                raise ValueError("owner and repo are required for GitHub actions")
        elif self.project_id is None and not (self.owner and self.repo):
            raise ValueError("project_id (or owner/repo) is required for GitLab actions")
        return self


def _redact_hh_error(raw: object) -> str | None:
    if raw is None:
        return None
    s = str(raw).strip()
    if not s:
        return None
    return redact_error_text(redact_pii(s), max_len=200)


def _safe_int_val(val: Any) -> int | None:
    if val is None or isinstance(val, bool):
        return None
    try:
        return int(val)
    except (TypeError, ValueError):
        return None


def _snap_attr(obj: object, key: str, default: Any = None) -> Any:
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _extract_snapshot_items(snap: object) -> list[Any]:
    if snap is None:
        return []
    raw_items = _snap_attr(snap, "items", None)
    return list(raw_items) if isinstance(raw_items, list) else []


def _snapshot_item_to_pending_row(item: Any, platform: str, action_priority: dict[str, int]) -> dict | None:
    status = str(_snap_attr(item, "status", None) or ("pending" if platform == "gitlab" else "queued"))
    raw = _snap_attr(item, "raw", None)
    raw_dict = raw if isinstance(raw, dict) else {}
    mr_state = str(raw_dict.get("mr_state") or "")
    if status in ("merged", "closed") or mr_state in ("merged", "closed"):
        return None

    item_id = _snap_attr(item, "item_id", None)
    project_ref = str(_snap_attr(item, "project_ref", "") or "")
    title = str(_snap_attr(item, "title", "") or "")
    author = str(_snap_attr(item, "author", "") or "")
    url = str(_snap_attr(item, "url", "") or "")
    ci_status = str(_snap_attr(item, "ci_status", "") or "") or "unknown"
    queue_position = _snap_attr(item, "queue_position", None)
    enqueued_at = str(_snap_attr(item, "enqueued_at", "") or "")

    if platform == "gitlab":
        action = str(raw_dict.get("action") or ("queued" if status == "queued" else "review_requested"))
        return {
            "platform": "gitlab",
            "queue_position": queue_position,
            "todo_id": raw_dict.get("todo_id"),
            "action": action,
            "status": status,
            "priority": action_priority.get(action, 99),
            "mr_iid": item_id,
            "mr_title": title,
            "project_path": project_ref,
            "project_id": raw_dict.get("project_id"),
            "author": author,
            "pipeline_status": ci_status,
            "created_at": enqueued_at,
            "target_url": url,
        }

    kind = str(_snap_attr(item, "item_kind", "pr") or "pr")
    is_issue = kind == "issue"
    action = str(raw_dict.get("action") or ("queued" if status == "queued" else "pending"))
    row = {
        "platform": "github",
        "issue_number" if is_issue else "pr_number": item_id,
        "issue_title" if is_issue else "pr_title": title,
        "project_path": project_ref,
        "author": author,
        "created_at": enqueued_at,
        "target_url": url,
        "queue_position": queue_position,
        "action": action,
        "status": status,
        "priority": 0,
    }
    if not is_issue:
        row["check_status"] = ci_status
    return row


def _pending_row_keys(row: dict) -> list[tuple]:
    plat = row.get("platform")
    if plat == "gitlab":
        iid = _safe_int_val(row.get("mr_iid"))
        if iid is None:
            return []
        keys: list[tuple] = []
        pid = row.get("project_id")
        if pid is not None and str(pid):
            keys.append(("gitlab", "mr", f"pid:{pid}", iid))
        ppath = str(row.get("project_path") or "").strip().lower()
        if ppath:
            keys.append(("gitlab", "mr", f"path:{ppath}", iid))
        return keys or [("gitlab", "mr", "", iid)]
    ppath = str(row.get("project_path") or "").strip().lower()
    issue_num = _safe_int_val(row.get("issue_number"))
    if issue_num is not None:
        return [("github", "issue", ppath, issue_num)]
    pr_num = _safe_int_val(row.get("pr_number"))
    if pr_num is not None:
        return [("github", "pr", ppath, pr_num)]
    return []


async def _read_headhunter_snapshot_safe(blackboard: BlackboardState | None, platform: str) -> object:
    if blackboard is None or not hasattr(blackboard, "get_headhunter_snapshot"):
        return None
    try:
        return await blackboard.get_headhunter_snapshot(platform)
    except Exception as exc:
        logger.warning("Headhunter %s snapshot read skipped (%s)", platform, type(exc).__name__)
        return None


def _require_headhunter_operator(request: Request, action: str) -> None:
    from .. import auth

    auth_enabled = bool(auth.DEX_ENABLED or auth.TRUSTED_PROXY_ENABLED)
    if not auth_enabled:
        return
    user = auth.get_user_from_request(request)
    if not user or not getattr(user, "email", None):
        logger.warning("[Audit] Denied Headhunter operator %s: unauthenticated", action)
        raise HTTPException(status_code=401, detail="Authentication required")
    allowed_groups = {
        str(g).strip().lower() for g in (auth.OBS_ADMIN_GROUPS or ()) if str(g).strip()
    } | {
        str(g).strip().lower() for g in (auth.APPROVER_GROUPS or ()) if str(g).strip()
    }
    user_roles = {str(r).strip().lower() for r in (user.roles or ()) if str(r).strip()}
    if not allowed_groups or not (user_roles & allowed_groups):
        logger.warning(
            "[Audit] Denied Headhunter operator %s for %s (roles=%s)",
            action, user.email, user.roles,
        )
        raise HTTPException(status_code=403, detail="Forbidden: Headhunter operator group membership required")
    logger.info("[Audit] Allowed Headhunter operator %s for %s", action, user.email)


async def _get_headhunter_or_503():
    try:
        brain = await get_brain()
    except RuntimeError:
        raise HTTPException(status_code=503, detail="Brain not initialized")
    hh = brain.agents.get("_headhunter") if brain else None
    if hh is None:
        raise HTTPException(status_code=503, detail="Headhunter not initialized")
    return hh


async def _acquire_hh_poll_lock(hh: Any) -> tuple[bool, asyncio.Lock | None]:
    lock = getattr(hh, "_poll_lock", None)
    if lock is None:
        return True, None
    try:
        await asyncio.wait_for(lock.acquire(), timeout=5.0)
    except asyncio.TimeoutError:
        return False, None
    return True, lock


def _busy_lock_response() -> JSONResponse:
    return JSONResponse(
        status_code=409,
        content={"detail": "Headhunter poll cycle is currently busy; retry shortly."},
        headers={"Retry-After": "5"},
    )


def _match_snapshot_item(snap: object, req: HeadhunterItemActionRequest) -> tuple[Any, dict] | None:
    for item in _extract_snapshot_items(snap):
        status = str(_snap_attr(item, "status", "") or "")
        raw = _snap_attr(item, "raw", None)
        raw_dict = raw if isinstance(raw, dict) else {}
        mr_state = str(raw_dict.get("mr_state") or "")
        if status in ("merged", "closed") or mr_state in ("merged", "closed"):
            continue
        item_id = _safe_int_val(_snap_attr(item, "item_id", None))
        if item_id is None or item_id != req.item_number:
            continue
        kind = str(_snap_attr(item, "item_kind", "") or "")
        proj_ref = str(_snap_attr(item, "project_ref", "") or "")
        if req.platform == "github":
            expected_kind = "issue" if req.is_issue else "pr"
            if kind != expected_kind:
                continue
            if proj_ref.lower() == f"{req.owner}/{req.repo}".lower():
                return item, raw_dict
        else:
            if kind and kind != "mr":
                continue
            raw_pid = raw_dict.get("project_id")
            if req.project_id is not None:
                if raw_pid is not None and str(raw_pid) == str(req.project_id):
                    return item, raw_dict
                if proj_ref.lower() == str(req.project_id).lower():
                    return item, raw_dict
            elif req.owner and req.repo and proj_ref.lower() == f"{req.owner}/{req.repo}".lower():
                return item, raw_dict
    return None


@router.get("/headhunter/pending")
async def headhunter_pending_todos():
    """Return pending/queued/active Headhunter items via pure Redis reads (zero HTTP calls)."""
    from ..agents.headhunter import ACTION_PRIORITY

    gitlab_enabled = os.getenv("HEADHUNTER_ENABLED", "false").lower() == "true"
    show_github_block = gitlab_enabled or os.getenv("HEADHUNTER_GITHUB_ENABLED", "false").lower() == "true"
    if not gitlab_enabled and not show_github_block:
        return []

    try:
        blackboard = await get_blackboard()
    except RuntimeError:
        return []

    enabled_platforms: list[str] = []
    if gitlab_enabled:
        enabled_platforms.append("gitlab")
    if show_github_block:
        enabled_platforms.append("github")

    snapshot_rows: list[dict] = []
    for plat in enabled_platforms:
        snap = await _read_headhunter_snapshot_safe(blackboard, plat)
        for item in _extract_snapshot_items(snap):
            try:
                row = _snapshot_item_to_pending_row(item, plat, ACTION_PRIORITY)
                if row is not None:
                    snapshot_rows.append(row)
            except Exception as exc:
                logger.warning("Skipping malformed %s snapshot item (%s)", plat, type(exc).__name__)

    status_map: dict[str, str] = {}
    waiting_ids: list[str] = []
    try:
        raw_status = await blackboard.get_active_events_with_status()
        if isinstance(raw_status, dict):
            status_map = dict(raw_status)
    except Exception as exc:
        logger.warning("Headhunter active-event lookup skipped: %s", exc)
    if hasattr(blackboard, "get_waiting_approval_events"):
        try:
            raw_wait = await blackboard.get_waiting_approval_events()
            if isinstance(raw_wait, (list, tuple, set)):
                waiting_ids = list(raw_wait)
        except Exception as exc:
            logger.warning("Headhunter waiting_approval lookup skipped: %s", exc)

    event_status_by_id: dict[str, str] = dict(status_map)
    for wid in waiting_ids:
        event_status_by_id[wid] = EventStatus.WAITING_APPROVAL.value

    bb_rows: list[dict] = []
    if event_status_by_id:
        eids = list(event_status_by_id)
        fetched = await asyncio.gather(
            *(blackboard.get_event(eid) for eid in eids),
            return_exceptions=True,
        )
        for eid, fetched_event in zip(eids, fetched):
            if isinstance(fetched_event, Exception):
                logger.warning("Skipping active event %s (fetch/parse failed): %s", eid, fetched_event)
                continue
            event = fetched_event
            if not event or event.source != "headhunter":
                continue
            actual_status = event.status.value if hasattr(event.status, "value") else str(event.status)
            if actual_status == EventStatus.CLOSED.value or actual_status not in _ACTIVE_HH_EVENT_STATUSES:
                continue
            ev_status = event_status_by_id.get(eid, actual_status)
            if ev_status not in _ACTIVE_HH_EVENT_STATUSES:
                continue
            evidence = event.event.evidence if event.event else None
            gl_ctx = getattr(evidence, "gitlab_context", None) if evidence else None
            gh_ctx = getattr(evidence, "github_context", None) if evidence else None
            gh_issue_ctx = getattr(evidence, "github_issue_context", None) if evidence else None

            row: dict | None = None
            if gl_ctx and gitlab_enabled and isinstance(gl_ctx, dict):
                row = {
                    "platform": "gitlab",
                    "queue_position": None,
                    "todo_id": gl_ctx.get("todo_id"),
                    "action": ev_status,
                    "status": ev_status,
                    "priority": 0,
                    "mr_iid": gl_ctx.get("mr_iid"),
                    "mr_title": gl_ctx.get("mr_title") or "",
                    "project_path": gl_ctx.get("project_path") or "",
                    "project_id": gl_ctx.get("project_id"),
                    "author": gl_ctx.get("author") or "",
                    "pipeline_status": gl_ctx.get("pipeline_status") or "unknown",
                    "created_at": gl_ctx.get("todo_created_at") or gl_ctx.get("created_at") or event.event.timeDate,
                    "target_url": gl_ctx.get("target_url") or "",
                }
            elif gh_ctx and show_github_block and isinstance(gh_ctx, dict):
                row = _github_active_item(
                    gh_ctx, number_key="pr_number", title_key="pr_title", url_key="pr_url",
                    action=ev_status, fallback_created_at=event.event.timeDate, is_issue=False,
                )
                row["status"] = ev_status
                row["check_status"] = gh_ctx.get("check_status") or "unknown"
            elif gh_issue_ctx and show_github_block and isinstance(gh_issue_ctx, dict):
                row = _github_active_item(
                    gh_issue_ctx, number_key="issue_number", title_key="title", url_key="html_url",
                    action=ev_status, fallback_created_at=event.event.timeDate, is_issue=True,
                )
                row["status"] = ev_status

            if row is not None:
                bb_rows.append(row)

    pid_to_path: dict[int, str] = {}
    path_to_pid: dict[str, int] = {}
    for row in bb_rows + snapshot_rows:
        if row.get("platform") != "gitlab":
            continue
        pid_val = _safe_int_val(row.get("project_id"))
        ppath_val = str(row.get("project_path") or "").strip().lower()
        if pid_val is not None and pid_val > 0 and ppath_val and ppath_val != str(pid_val):
            pid_to_path.setdefault(pid_val, ppath_val)
            path_to_pid.setdefault(ppath_val, pid_val)

    def _normalized_row_keys(row: dict) -> list[tuple]:
        if row.get("platform") == "gitlab":
            pid_val = _safe_int_val(row.get("project_id"))
            ppath_val = str(row.get("project_path") or "").strip().lower()
            patched = row
            if (pid_val is None or pid_val <= 0) and ppath_val in path_to_pid:
                patched = {**patched, "project_id": path_to_pid[ppath_val]}
            if (not ppath_val or (pid_val is not None and ppath_val == str(pid_val))) and pid_val in pid_to_path:
                patched = {**patched, "project_path": pid_to_path[pid_val]}
            return _pending_row_keys(patched)
        return _pending_row_keys(row)

    result = list(bb_rows)
    seen_snap_keys: set[tuple] = set()
    for row in bb_rows:
        seen_snap_keys.update(_normalized_row_keys(row))
    for row in snapshot_rows:
        rkeys = _normalized_row_keys(row)
        if any(k in seen_snap_keys for k in rkeys):
            continue
        result.append(row)
        seen_snap_keys.update(rkeys)

    result.sort(key=lambda t: t.get("created_at") or "")
    return result


@router.get("/headhunter/status")
async def headhunter_platform_status():
    """Return per-platform Headhunter poll & circuit-breaker telemetry from Redis snapshots."""
    try:
        blackboard = await get_blackboard()
    except RuntimeError:
        blackboard = None

    hh = None
    try:
        brain = await get_brain()
        hh = brain.agents.get("_headhunter") if brain else None
    except RuntimeError:
        pass

    env_enabled = {
        "gitlab": os.getenv("HEADHUNTER_ENABLED", "false").lower() == "true",
        "github": os.getenv("HEADHUNTER_GITHUB_ENABLED", "false").lower() == "true",
    }

    platforms: dict[str, dict[str, Any]] = {}
    for plat in ("gitlab", "github"):
        snap = await _read_headhunter_snapshot_safe(blackboard, plat)
        live_cb = getattr(hh, "_breakers", {}).get(plat) if hh is not None else None
        if snap is not None:
            enabled = bool(_snap_attr(snap, "enabled", env_enabled[plat]))
            pending_count = _safe_int_val(_snap_attr(snap, "pending_count", 0)) or 0
            queued_count = _safe_int_val(_snap_attr(snap, "queued_count", 0)) or 0
            last_poll_at = _snap_attr(snap, "last_poll_at", None)
            partial_error = _redact_hh_error(_snap_attr(snap, "partial_error", None))
            raw_brk = _snap_attr(snap, "breaker", None)
            breaker = {
                "state": str(_snap_attr(raw_brk, "state", "closed") or "closed") if raw_brk is not None else "closed",
                "consecutive_failures": (
                    _safe_int_val(_snap_attr(raw_brk, "consecutive_failures", 0)) or 0
                ) if raw_brk is not None else 0,
                "next_retry_at": _snap_attr(raw_brk, "next_retry_at", None) if raw_brk is not None else None,
                "last_error": _redact_hh_error(_snap_attr(raw_brk, "last_error", None)) if raw_brk is not None else None,
            }
        else:
            enabled = env_enabled[plat]
            pending_count = 0
            queued_count = 0
            last_poll_at = None
            partial_error = None
            breaker = {
                "state": "closed",
                "consecutive_failures": 0,
                "next_retry_at": None,
                "last_error": None,
            }
        if live_cb is not None:
            breaker = {
                "state": str(getattr(live_cb, "state", "closed") or "closed"),
                "consecutive_failures": _safe_int_val(getattr(live_cb, "consecutive_failures", 0)) or 0,
                "next_retry_at": getattr(live_cb, "next_retry_at", None),
                "last_error": _redact_hh_error(getattr(live_cb, "last_error", None)),
            }
        platforms[plat] = {
            "enabled": enabled,
            "pending_count": pending_count,
            "queued_count": queued_count,
            "last_poll_at": last_poll_at,
            "partial_error": partial_error,
            "breaker": breaker,
        }
    return {"platforms": platforms}


@router.post("/headhunter/poll")
async def trigger_headhunter_poll(request: Request):
    """Trigger an immediate non-blocking Headhunter poll cycle (10s debounced, RBAC gated)."""
    global _hh_last_poll_ts
    _require_headhunter_operator(request, "poll")
    hh = await _get_headhunter_or_503()
    acquired, lock = await _acquire_hh_poll_lock(hh)
    if not acquired:
        return _busy_lock_response()
    try:
        now = time.monotonic()
        if _hh_last_poll_ts is not None and (now - _hh_last_poll_ts) < _HH_OPERATOR_DEBOUNCE_S:
            return JSONResponse(status_code=202, content={"triggered": False, "debounced": True})
        hh.trigger_poll()
        _hh_last_poll_ts = time.monotonic()
        return JSONResponse(status_code=202, content={"triggered": True, "debounced": False})
    finally:
        if lock is not None:
            lock.release()


@router.post("/headhunter/breaker/{platform}/reset")
async def reset_headhunter_breaker(
    platform: Literal["gitlab", "github"],
    request: Request,
):
    """Manually reset a platform circuit breaker to closed and wake the poll loop."""
    _require_headhunter_operator(request, f"breaker_reset:{platform}")
    hh = await _get_headhunter_or_503()
    acquired, lock = await _acquire_hh_poll_lock(hh)
    if not acquired:
        return _busy_lock_response()
    try:
        now = time.monotonic()
        last_ts = _hh_last_breaker_reset_ts.get(platform)
        if last_ts is not None and (now - last_ts) < _HH_OPERATOR_DEBOUNCE_S:
            return JSONResponse(
                status_code=202,
                content={"reset": False, "debounced": True, "platform": platform},
            )
    finally:
        if lock is not None:
            lock.release()

    await hh.reset_breaker(platform)
    _hh_last_breaker_reset_ts[platform] = time.monotonic()
    return {"reset": True, "debounced": False, "platform": platform, "state": "closed"}


@router.post("/headhunter/items/{action}")
async def headhunter_item_action(
    action: Literal["promote", "dismiss", "requeue"],
    req: HeadhunterItemActionRequest,
    request: Request,
):
    """Operator control for a queued/pending Headhunter item (exact snapshot membership required)."""
    _require_headhunter_operator(request, f"item_{action}:{req.platform}:{req.item_number}")
    try:
        blackboard = await get_blackboard()
    except RuntimeError:
        raise HTTPException(status_code=503, detail="Blackboard not initialized")

    try:
        snap = (
            await blackboard.get_headhunter_snapshot(req.platform)
            if hasattr(blackboard, "get_headhunter_snapshot")
            else None
        )
    except RedisError as exc:
        logger.warning("Headhunter %s snapshot lookup failed (%s)", req.platform, type(exc).__name__)
        raise HTTPException(status_code=503, detail="Blackboard state temporarily unavailable")

    matched = _match_snapshot_item(snap, req)
    if matched is None:
        raise HTTPException(
            status_code=404,
            detail=f"Item {req.platform}#{req.item_number} not found in active Headhunter queue/pending snapshot",
        )
    matched_item, matched_raw = matched

    hh = await _get_headhunter_or_503()
    acquired, lock = await _acquire_hh_poll_lock(hh)
    if not acquired:
        return _busy_lock_response()
    debounce_key = (action, req.platform, req.item_number)
    try:
        now = time.monotonic()
        last_ts = _hh_last_item_action_ts.get(debounce_key)
        if last_ts is not None and (now - last_ts) < _HH_OPERATOR_DEBOUNCE_S:
            return JSONResponse(
                status_code=202 if action == "promote" else 200,
                content={"ok": False, "debounced": True, "action": action, "platform": req.platform},
            )
    finally:
        if lock is not None:
            lock.release()

    try:
        result = await hh.operate_item(action, req, matched_item, matched_raw, blackboard)
    except HeadhunterOperationError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)
    except WatchError:
        raise HTTPException(status_code=409, detail="Concurrent queue modification; retry")
    except RedisError as exc:
        logger.warning("Headhunter %s Redis mutation failed (%s)", action, type(exc).__name__)
        raise HTTPException(status_code=503, detail="Blackboard state temporarily unavailable")

    _hh_last_item_action_ts[debounce_key] = time.monotonic()
    if action == "promote":
        return JSONResponse(status_code=202, content=result)
    return result

@router.post("/{event_id}/decision")
async def post_approval_decision(
    request: Request,
    decision: DecisionRequest,
    event_id: str = Path(..., description="Event ID"),
    blackboard: BlackboardState = Depends(get_blackboard),
    brain = Depends(get_brain),
):
    """Submit a structured multi-option approval decision or write-in."""
    from .. import auth

    user = auth.get_user_from_request(request)
    auth_enabled = bool(auth.DEX_ENABLED or auth.TRUSTED_PROXY_ENABLED)
    if auth_enabled and not user.email:
        raise HTTPException(status_code=401, detail="Authentication required")

    outcome = await execute_approval_decision(
        blackboard=blackboard,
        brain=brain,
        event_id=event_id,
        user=user,
        auth_enabled=auth_enabled,
        req=decision,
        head_sha_resolver=None,
    )
    if outcome.kind != "ok":
        return _map_decision_error_response(outcome)
    return {"code": "ok"}
