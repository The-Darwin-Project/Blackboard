# BlackBoard/src/routes/queue.py
# @ai-rules:
# 1. [Gotcha]: GET /closed/list MUST stay before GET /{event_id} to avoid "closed" matching as event_id.
# 2. [Pattern]: POST /{event_id}/close uses blackboard.close_event() + explicit delete_slack_mapping() for Slack cleanup (Brain path uses _close_and_broadcast instead).
# 3. [Gotcha]: Pre-existing route order issue -- closed/list is after /{event_id}. Works because /closed/list is 2 segments.
# 4. [Pattern]: GET /{event_id}/report uses event_to_markdown from src/utils/event_markdown.
# 5. [Policy]: GET /headhunter/pending drops todos whose MR target.state is merged or closed only; unknown/missing state kept.
# 6. [Pattern]: list_active_events and list_closed_events include created_by_email for BFF multi-tenant filtering.
# 7. [Pattern]: PATCH lessons/{id}/demote and verify endpoints read-modify-write Qdrant point (payload + re-embed). Legacy lessons missing channel/verification_count default to external/0.
# 8. [Pattern]: /active response includes unread_notes for sidebar badge display.
# 9. [Pattern]: Knowledge CRUD routes mirror lesson pattern. KnowledgeUpdateRequest uses extra="forbid" to enforce immutability of identity fields (topic, scope) -- Pydantic returns 422 on unknown fields.
# 10. [Pattern]: PATCH /admin/knowledge/{id} does read-modify-reembed-upsert. Only mutable fields (fact, source, confidence, valid_until) can be updated.
# 11. [Pattern]: KnowledgeRequest includes optional `service` (part of uuid5 identity). KnowledgeUpdateRequest
#     deliberately omits it -- service is immutable once a fact is created.
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
from pydantic import BaseModel, ConfigDict, Field

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
        if event:
            row = {
                "id": event.id,
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
                "created_by_email": event.created_by_email,
            })
    return events


@router.get("/{event_id}/turns")
async def get_event_turns(
    event_id: str,
    role: Optional[str] = Query(None, description="Agent role for gap calculation (qe, sysadmin, developer, architect, security_analyst)"),
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

    Uses brain.append_and_broadcast to go through the standard broadcast pipeline
    (WS push to UI, Slack mirror, agent blackboard_update).
    """
    from ..dependencies import get_brain
    brain = await get_brain()
    event = await blackboard.get_event(event_id)
    if not event:
        raise HTTPException(status_code=404, detail=f"Event {event_id} not found")

    turn = ConversationTurn(
        turn=(await brain.next_turn_number(event_id)),
        actor=req.role or "agent",
        action="plan_step",
        thoughts=req.notes or f"Step {req.step_id}: {req.status}",
        taskForAgent={"step_id": req.step_id, "status": req.status},
    )
    await brain.append_and_broadcast(event_id, turn)
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

    try:
        brain = await get_brain()
        brain.clear_waiting(event_id)
        resumed = await brain.resume_if_parked(event_id)
        if not resumed:
            logger.info(f"approve_event: {event_id} was not in waiting_approval (already resumed or race)")
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

    try:
        brain = await get_brain()
        brain.clear_waiting(event_id)
        resumed = await brain.resume_if_parked(event_id)
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
    """Delete a lesson by ID."""
    try:
        archivist = await get_archivist()
    except RuntimeError:
        raise HTTPException(503, "Archivist not available")
    existing = await archivist.list_lessons(limit=500)
    if not any(p.get("payload", {}).get("lesson_id") == lesson_id for p in existing):
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
async def list_knowledge(limit: int = Query(default=100, le=1000, ge=1)):
    """List knowledge facts from Qdrant (paginated, default 100, max 1000)."""
    try:
        archivist = await get_archivist()
    except RuntimeError:
        raise HTTPException(503, "Archivist not available")
    return await archivist.list_knowledge(limit=limit)


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
        mr_state = target.get("state")
        if mr_state in ("merged", "closed"):
            continue
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
    # Attach platform discriminator to GitLab items
    for item in result:
        item["platform"] = "gitlab"
        item.setdefault("queue_position", None)

    # Append GitHub queued PRs from agent cached state (single event loop, no lock needed)
    try:
        brain = await get_brain()
        if brain and brain.headhunter and brain.headhunter._github:
            for idx, pr in enumerate(brain.headhunter._github.queued_prs, start=1):
                result.append({
                    "platform": "github",
                    "pr_number": pr.get("number"),
                    "pr_title": pr.get("title", ""),
                    "project_path": f"{pr.get('owner', '')}/{pr.get('repo', '')}",
                    "author": pr.get("user", ""),
                    "created_at": pr.get("created_at", ""),
                    "target_url": pr.get("html_url", ""),
                    "queue_position": idx,
                    "action": "queued",
                    "priority": 0,
                })
    except Exception as e:
        logger.warning(f"GitHub queued PR lookup skipped: {e}")

    # Sort after GitHub items are appended so FIFO ordering spans both platforms
    result.sort(key=lambda t: t.get("created_at", ""))
    return result
