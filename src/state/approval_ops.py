# BlackBoard/src/state/approval_ops.py
# @ai-rules:
# 1. [Constraint]: Pure logic for approval turn synthesis/sweeping.
# 2. [Constraint]: Zero src.agents imports -- hexagonal boundary safe.
# 3. [Constraint]: <= 100 lines.
from __future__ import annotations

import time

from ..models import (
    ApprovalOption,
    ApprovalResolution,
    ConversationTurn,
    EventDocument,
)

def synthesize_default_options() -> list[ApprovalOption]:
    """Return fallback options for legacy approvals without explicit options."""
    return [
        ApprovalOption(id="approve", label="Approve plan", effect="approve"),
        ApprovalOption(id="reject", label="Reject plan", effect="reject"),
    ]

def sweep_dangling_approvals(
    event: EventDocument,
    outcome: str,
    resolved_by: str | None = None,
) -> list[ConversationTurn]:
    """Find and close any active request_approval turns on the event.

    Returns the list of modified turns so callers can broadcast updates.
    """
    swept = []
    for turn in event.conversation:
        if turn.pendingApproval:
            turn.pendingApproval = False
            # Synthesize a resolution if it was a structured request
            if getattr(turn, "approval_id", None):
                canonical_outcome = outcome if outcome in ("superseded", "closed", "expired") else "closed"
                turn.approval_resolution = ApprovalResolution(
                    resolved_by=resolved_by or "system",
                    outcome=canonical_outcome,
                    option_id=f"auto_{canonical_outcome}",
                    option_label=f"Auto {canonical_outcome}",
                    effect="steer" if outcome == "superseded" else "reject",
                    resolved_at=time.time(),
                )
            swept.append(turn)
    return swept

