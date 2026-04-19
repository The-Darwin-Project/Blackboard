# BlackBoard/src/routes/queue.py
# @ai-rules:
# 1. [Gotcha]: GET /closed/list MUST stay before GET /{event_id} to avoid "closed" matching as event_id.
# 2. [Pattern]: POST /{event_id}/close uses blackboard.close_event() + explicit delete_slack_mapping() for Slack cleanup (Brain path uses _close_and_broadcast instead).
# 3. [Gotcha]: Pre-existing route order issue -- closed/list is after /{event_id}. Works because /closed/list is 2 segments.
# 4. [Pattern]: GET /{event_id}/report uses Brain._event_to_markdown (staticmethod) -- no Brain instance needed.
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
import logging
import time

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from ..dependencies import get_archivist, get_blackboard, get_brain
from ..models import ConversationTurn, EventDocument, EventEvidence, EventStatus
from ..state.blackboard import BlackboardState


class RejectRequest(BaseModel):
    """Typed request body for plan rejection."""
    reason: str = Field("User rejected the plan.", description="Rejection reason")
    image: Optional[str] = Field(None, description="Base64 data URI of screenshot")

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


@router.get("/active")
async def list_active_events(
    blackboard: BlackboardState = Depends(get_blackboard),
):
    """Get all active event IDs with basic metadata."""
    event_ids = await blackboard.get_active_events()
    events = []
    for eid in event_ids:
        event = await blackboard.get_event(eid)
        if event:
            events.append({
                "id": event.id,
                "source": event.source,
                "service": event.service,
                "subject_type": getattr(event, "subject_type", "service"),
                "status": event.status.value,
                "reason": event.event.reason,
                "evidence": _serialize_evidence(event),
                "turns": len(event.conversation),
                "created": event.event.timeDate,
            })
    return events


@router.get("/{event_id}/turns")
async def get_event_turns(
    event_id: str,
    role: Optional[str] = Query(None, description="Agent role for gap calculation (qe, sysadmin, developer, architect)"),
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
    status: str = Field(..., description="in_progress, completed, or blocked")
    notes: str = Field("", description="What was done or why blocked")
    role: str = Field("", description="Agent role (auto-set by sidecar proxy)")
    event_id: str = Field("", description="Event ID (auto-set by sidecar proxy)")


@router.post("/{event_id}/plan-step")
async def update_plan_step(
    event_id: str,
    req: PlanStepRequest,
    blackboard: BlackboardState = Depends(get_blackboard),
):
    """Update a plan step status. Called by agent sidecars via bb_update_plan_step MCP tool.

    Uses brain._append_and_broadcast to go through the standard broadcast pipeline
    (WS push to UI, Slack mirror, agent blackboard_update).
    """
    from ..dependencies import get_brain
    brain = await get_brain()
    event = await blackboard.get_event(event_id)
    if not event:
        raise HTTPException(status_code=404, detail=f"Event {event_id} not found")

    turn = ConversationTurn(
        turn=(await brain._next_turn_number(event_id)),
        actor=req.role or "agent",
        action="plan_step",
        thoughts=req.notes or f"Step {req.step_id}: {req.status}",
        taskForAgent={"step_id": req.step_id, "status": req.status},
    )
    await brain._append_and_broadcast(event_id, turn)
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
    return event


@router.post("/{event_id}/approve")
async def approve_event(
    event_id: str,
    blackboard: BlackboardState = Depends(get_blackboard),
):
    """Approve a pending plan in an event conversation."""
    event = await blackboard.get_event(event_id)
    if not event:
        raise HTTPException(status_code=404, detail=f"Event {event_id} not found")

    turn = ConversationTurn(
        turn=len(event.conversation) + 1,
        actor="user",
        action="approve",
        thoughts="User approved the plan.",
    )
    await blackboard.append_turn(event_id, turn)

    # Atomically transition status so the Brain picks it up
    await blackboard.transition_event_status(
        event_id, from_status="waiting_approval", to_status=EventStatus.ACTIVE,
    )

    # Clear wait_for_user state so Brain re-processes with approval
    try:
        brain = await get_brain()
        brain.clear_waiting(event_id)
    except RuntimeError:
        pass  # Brain not initialized (unlikely in normal operation)

    logger.info(f"User approved event {event_id}")
    return {"status": "approved", "event_id": event_id}


@router.post("/{event_id}/reject")
async def reject_event(
    event_id: str,
    body: RejectRequest = RejectRequest(),
    blackboard: BlackboardState = Depends(get_blackboard),
):
    """Reject a pending plan in an event conversation."""
    event = await blackboard.get_event(event_id)
    if not event:
        raise HTTPException(status_code=404, detail=f"Event {event_id} not found")

    # Server-side image size guard (~1MB)
    if body.image and len(body.image) > 1_400_000:
        raise HTTPException(status_code=413, detail="Image too large (max 1MB)")

    turn = ConversationTurn(
        turn=len(event.conversation) + 1,
        actor="user",
        action="reject",
        thoughts=body.reason,
        image=body.image,
    )
    await blackboard.append_turn(event_id, turn)

    # Atomically transition status so the Brain re-processes with rejection feedback
    await blackboard.transition_event_status(
        event_id, from_status="waiting_approval", to_status=EventStatus.ACTIVE,
    )

    # Clear wait_for_user state so Brain re-processes with rejection
    try:
        brain = await get_brain()
        brain.clear_waiting(event_id)
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
    except RuntimeError:
        pass  # Brain not initialized
    await blackboard.close_event(event_id, close_summary, close_reason="user_closed")
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
    # Archive to deep memory (same path as Brain._close_and_broadcast)
    try:
        brain = await get_brain()
        archivist = brain.agents.get("_archivist_memory")
        if archivist and hasattr(archivist, "archive_event"):
            closed_event = await blackboard.get_event(event_id)
            if closed_event:
                await archivist.archive_event(closed_event)
    except Exception as e:
        logger.warning(f"Deep memory archive failed for {event_id} (non-fatal): {e}")
    logger.info(f"User force-closed event {event_id}: {body.reason}")
    return {"status": "closed", "event_id": event_id}


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
    mermaid = ""
    if event.source != "headhunter" and getattr(event, "subject_type", "service") != "kargo_stage":
        try:
            mermaid = await blackboard.generate_mermaid()
        except Exception:
            pass

    from ..agents.brain import Brain
    content = Brain._event_to_markdown(event, service_meta, mermaid)

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
    closed_ids = await blackboard.redis.zrevrangebyscore(
        blackboard.EVENT_CLOSED,
        max=time.time(),
        min=time.time() - 86400,
        start=0,
        num=limit,
    )
    events = []
    for eid in closed_ids:
        event = await blackboard.get_event(eid)
        if event:
            events.append({
                "id": event.id,
                "source": event.source,
                "service": event.service,
                "subject_type": getattr(event, "subject_type", "service"),
                "status": event.status.value,
                "reason": event.event.reason,
                "evidence": _serialize_evidence(event),
                "turns": len(event.conversation),
                "created": event.event.timeDate,
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

    closed_ids = await blackboard.redis.zrange(blackboard.EVENT_CLOSED, 0, -1)
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
    corrected_root_cause: str
    corrected_fix_action: str
    correction_note: str = ""


class LessonRequest(BaseModel):
    title: str
    pattern: str
    anti_pattern: str = ""
    keywords: list[str] = Field(default_factory=list)
    event_references: list[str] = Field(default_factory=list)


@router.get("/admin/memories")
async def list_memories():
    """List all archived event memories from Qdrant."""
    try:
        archivist = await get_archivist()
    except RuntimeError:
        raise HTTPException(503, "Archivist not available")
    return await archivist.list_memories()


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
async def list_lessons():
    """List all lessons learned from Qdrant."""
    try:
        archivist = await get_archivist()
    except RuntimeError:
        raise HTTPException(503, "Archivist not available")
    return await archivist.list_lessons()


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
    )
    if not lesson_id:
        raise HTTPException(503, "Failed to store lesson")
    return {"status": "stored", "lesson_id": lesson_id}


@router.delete("/admin/lessons/{lesson_id}")
async def delete_lesson(lesson_id: str):
    """Delete a lesson by ID."""
    try:
        archivist = await get_archivist()
    except RuntimeError:
        raise HTTPException(503, "Archivist not available")
    success = await archivist.delete_lesson(lesson_id)
    if not success:
        raise HTTPException(503, "Failed to delete lesson")
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
        from ..agents.brain import Brain
        for eid in req.event_ids[:10]:
            event = await blackboard.get_event(eid)
            if event:
                event_reports[eid] = Brain._event_to_markdown(event)

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


@router.get("/headhunter/pending")
async def headhunter_pending_todos():
    """Return pending GitLab todos that the Headhunter would process next.

    Lightweight read-only endpoint for UI observability. No events created.
    Returns empty list if Headhunter is disabled or GitLab is unavailable.
    """
    import os
    import httpx

    gitlab_host = os.getenv("GITLAB_HOST", "")
    if not gitlab_host or os.getenv("HEADHUNTER_ENABLED", "false").lower() != "true":
        return []

    from ..agents.headhunter import V1_ACTIONABLE, ACTION_PRIORITY
    try:
        from ..utils.gitlab_token import get_gitlab_auth
        auth = get_gitlab_auth()
        if not auth:
            return []
        token = auth.get_token()
    except Exception:
        return []

    try:
        async with httpx.AsyncClient(verify=False, timeout=15) as client:
            resp = await client.get(
                f"https://{gitlab_host}/api/v4/todos",
                headers={"PRIVATE-TOKEN": token},
                params={"state": "pending", "type": "MergeRequest", "sort": "asc"},
            )
            if not resp.is_success:
                return []
            todos = resp.json()
    except Exception:
        return []

    result = []
    for todo in todos:
        action = todo.get("action_name", "")
        if action not in V1_ACTIONABLE:
            continue
        target = todo.get("target", {})
        project = todo.get("project", {})
        result.append({
            "todo_id": todo.get("id"),
            "action": action,
            "priority": ACTION_PRIORITY.get(action, 99),
            "mr_iid": target.get("iid"),
            "mr_title": target.get("title", ""),
            "project_path": project.get("path_with_namespace", ""),
            "author": target.get("author", {}).get("username", ""),
            "pipeline_status": target.get("pipeline", {}).get("status", "unknown") if target.get("pipeline") else "unknown",
            "created_at": todo.get("created_at", ""),
            "target_url": todo.get("target_url", ""),
        })
    result.sort(key=lambda t: t.get("created_at", ""))
    return result
