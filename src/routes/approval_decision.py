# BlackBoard/src/routes/approval_decision.py
# @ai-rules:
# 1. [Constraint]: Core approval decision orchestrator. <= 100 lines.
# 2. [Constraint]: Pure routing/validation logic, no FastAPI dependencies.
from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING
from redis.exceptions import WatchError
from ..auth import UserContext, can_approve_event, resolve_approval_identity
from ..models import ApprovalResolution, ConversationTurn, EventStatus, WRITE_IN_OPTION_ID
from ..state.approval_ops import synthesize_default_options
from ..utils import vcs_approval as _vcs_approval
from ..utils.prompt_sanitize import sanitize_user_input_text
from ..utils.vcs_approval import check_approval_sha_drift
from .approval_decision_helpers import ApprovalDecisionOutcome, DecisionRequest, resolve_selected_option, validate_image_attachment

if TYPE_CHECKING:
    from ..state.ports import BlackboardState, EventRepository
    from ..ports import BrainLifecyclePort

logger = logging.getLogger(__name__)

async def execute_approval_decision(*, blackboard: "BlackboardState | EventRepository", brain: "BrainLifecyclePort | None", event_id: str, user: UserContext, auth_enabled: bool | None = None, req: DecisionRequest | None = None, legacy_mode: str | None = None, reject_reason: str | None = None, source: str = "web", head_sha_resolver=None) -> ApprovalDecisionOutcome:
    """Execute an approval decision with validation, drift checks, and atomic commit."""
    event = await blackboard.get_event(event_id)
    if not event: return ApprovalDecisionOutcome(kind="not_found", message=f"Event {event_id} not found")
    if auth_enabled and not user.email: return ApprovalDecisionOutcome(kind="auth_rejected", message="Authentication required")
    if not can_approve_event(user, event, auth_enabled):
        logger.warning("Forbidden approval decision attempt on %s by %s (source=%s)", event_id, user.email or user.user_id, source)
        return ApprovalDecisionOutcome(kind="auth_rejected", message="Insufficient permissions")
    if event.status in (EventStatus.CLOSED, EventStatus.RESOLVED): return ApprovalDecisionOutcome(kind="closed", message=f"Event {event_id} is closed")
    if event.status != EventStatus.WAITING_APPROVAL: return ApprovalDecisionOutcome(kind="not_waiting", message=f"Event {event_id} is not waiting for approval")
    pending = event.pending_approval
    options = pending.options if pending else synthesize_default_options()
    option_id = (req.option_id if req else None) or legacy_mode
    msg = (req.message or req.write_in_text or req.reject_reason) if req else reject_reason
    img = req.image if req else None
    selected, err = resolve_selected_option(options, option_id, legacy_mode, msg, has_image=bool(img))
    if err: return err
    img_err = validate_image_attachment(img)
    if img_err == "image_too_large": return ApprovalDecisionOutcome(kind="image_too_large", message="Image too large (max 1MB)")
    elif img_err: return ApprovalDecisionOutcome(kind="invalid_image", message=img_err)
    clean_msg = sanitize_user_input_text(msg) if msg else None
    ident, label = resolve_approval_identity(user.email, user.display_name, fallback=user.user_id)
    live_mr_id, live_sha_str = None, None
    if selected["effect"] == "approve":
        resolver = head_sha_resolver or _vcs_approval.resolve_live_head_sha
        try:
            live_tuple = await resolver(event)
            if live_tuple: live_mr_id, live_sha_str = live_tuple
        except Exception: live_mr_id, live_sha_str = None, None
        drift = check_approval_sha_drift(event, live_sha_str, expected_sha=req.expected_sha if req else None)
        if not drift.allowed: return ApprovalDecisionOutcome(kind=drift.code, message=drift.detail, expected_sha=drift.approval_requested_sha, actual_sha=drift.live_sha)
    req_turn = next((t for t in reversed(event.conversation) if getattr(t, "pendingApproval", False)), None)
    if not req_turn: return ApprovalDecisionOutcome(kind="not_waiting", message="No active approval turn found")
    current_apv = pending.approval_id if pending else getattr(req_turn, "approval_id", None)
    if req and req.approval_id and current_apv and req.approval_id != current_apv: return ApprovalDecisionOutcome(kind="stale_approval", message="Stale approval request; refresh and retry")
    is_writein = option_id == WRITE_IN_OPTION_ID
    res = ApprovalResolution(
        approval_id=current_apv, outcome="write_in" if is_writein else "option",
        option_id=selected["id"], option_label=selected["label"], effect=selected["effect"],
        write_in_text=clean_msg if is_writein else None, resolved_by=label or ident or "system", resolved_at=time.time(),
    )
    user_turn = ConversationTurn(
        turn=len(event.conversation) + 1, actor="user",
        action="write_in" if is_writein else ("approve" if selected["effect"] == "approve" else ("reject" if selected["effect"] == "reject" else "select_option")),
        thoughts=clean_msg, image=img, source=source, user_name=label,
        selected_option_id=selected["id"], selected_option_label=selected["label"],
    )
    try:
        commit = await blackboard.resolve_approval_decision(
            event_id=event_id, approval_id=(req.approval_id if req and req.approval_id else (current_apv or "")), effect=selected["effect"],
            expected_sha=req.expected_sha if req else None, user_turn=user_turn, resolution=res,
            approved_by=ident or label or "system", approved_mr_id=live_mr_id, approved_mr_sha=live_sha_str,
        )
    except WatchError:
        return ApprovalDecisionOutcome(kind="stale_approval", message="Concurrent approval modification; refresh and retry")
    if commit.code == "sha_conflict": return ApprovalDecisionOutcome(kind="sha_drift", message="Live HEAD SHA differs from requested SHA", expected_sha=event.approval_requested_sha, actual_sha=live_sha_str)
    if commit.code != "ok": return ApprovalDecisionOutcome(kind=commit.code, message=f"Commit failed: {commit.code}")
    logger.info("[Audit] Approval decision on %s by %s: option=%s effect=%s source=%s", event_id, ident or label or "system", selected["id"], selected["effect"], source)
    if brain: await brain.complete_approval_resume(event_id, commit.request_turn, commit.user_turn)
    else: logger.warning("Brain Lifecycle Port missing; cannot complete approval resume")
    return ApprovalDecisionOutcome(kind="ok", message="Decision applied", turn=commit.user_turn, request_turn=commit.request_turn)
