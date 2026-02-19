# BlackBoard/src/routes/feedback.py
# @ai-rules:
# 1. [Pattern]: Thin route -- delegates to Archivist.store_feedback() for embedding + storage.
# 2. [Constraint]: No PII collected. Only event_id + turn_number + rating + optional comment.
# 3. [Pattern]: Uses Depends() for blackboard + archivist, matching existing route patterns.
"""Feedback endpoint for AI response quality tracking."""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..dependencies import get_blackboard, get_archivist
from ..state.blackboard import BlackboardState

logger = logging.getLogger(__name__)

router = APIRouter(tags=["feedback"])


class FeedbackRequest(BaseModel):
    event_id: str
    turn_number: int
    rating: str = Field(pattern=r"^(positive|negative)$")
    comment: str = Field(default="", max_length=500)


@router.post("/feedback")
async def submit_feedback(
    req: FeedbackRequest,
    blackboard: BlackboardState = Depends(get_blackboard),
    archivist=Depends(get_archivist),
) -> dict:
    """Store user feedback on an AI-generated response."""
    event = await blackboard.get_event(req.event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    turn_text = ""
    for turn in event.conversation:
        if turn.turn == req.turn_number:
            turn_text = turn.thoughts or turn.result or turn.plan or ""
            break

    if not turn_text:
        raise HTTPException(status_code=404, detail="Turn not found or empty")

    stored = await archivist.store_feedback(
        event_id=req.event_id,
        turn_number=req.turn_number,
        rating=req.rating,
        turn_text=turn_text,
        comment=req.comment,
    )

    if not stored:
        raise HTTPException(status_code=503, detail="Feedback storage unavailable")

    return {"status": "stored"}
