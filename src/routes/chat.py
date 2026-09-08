# BlackBoard/src/routes/chat.py
"""
Chat endpoint - creates events for Brain processing.

The chat endpoint now creates events in the conversation queue.
The Brain processes them asynchronously via the event loop.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..dependencies import get_blackboard, get_brain
from ..models import ConversationTurn, EventEvidence
from ..state.blackboard import BlackboardState

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["chat"])


class ChatEventRequest(BaseModel):
    """Request to create a chat event, or reply to an existing one."""
    message: str = Field(..., description="User message or request")
    service: str = Field("general", description="Target service (or 'general')")
    event_id: str | None = Field(
        None, description="If set, append to this event instead of creating a new one"
    )


class ChatEventResponse(BaseModel):
    """Response with event ID for tracking."""
    event_id: str
    status: str = "created"


@router.post("/", response_model=ChatEventResponse)
async def create_chat_event(
    request: ChatEventRequest,
    blackboard: BlackboardState = Depends(get_blackboard),
) -> ChatEventResponse:
    """
    Create a new event from a user chat message, or -- when ``event_id`` is
    provided and still active -- append the message to that event instead.

    This mirrors the WebSocket ``user_message`` handler so the REST fallback
    (used when the dashboard's WebSocket is disconnected) does not silently
    spawn a duplicate event for a message meant to reply to the one the user
    already has open.

    The Brain will process this event asynchronously.
    Poll GET /queue/{event_id} to track conversation progress.
    """
    try:
        if request.event_id:
            existing = await blackboard.get_event(request.event_id)
            if existing:
                turn = ConversationTurn(
                    turn=len(existing.conversation) + 1,
                    actor="user",
                    action="message",
                    thoughts=request.message,
                )
                await blackboard.append_turn(request.event_id, turn)
                try:
                    brain = await get_brain()
                    brain.clear_waiting(request.event_id)
                    await brain.resume_if_parked(request.event_id)
                    brain.enqueue_for_processing(request.event_id)
                except RuntimeError:
                    pass  # Brain not initialized (unlikely in normal operation)
                logger.info(f"Chat message appended to existing event: {request.event_id}")
                return ChatEventResponse(event_id=request.event_id, status="appended")
            logger.warning(
                f"Chat event_id {request.event_id} not found; creating a new event instead"
            )

        event_id = await blackboard.create_event(
            source="chat",
            service=request.service,
            reason=request.message,
            evidence=EventEvidence(
                display_text=request.message,
                source_type="chat",
                triggered_by="dashboard",
                domain="disorder",
                severity="info",
            ),
        )
        # Add user message as the first conversation turn
        user_turn = ConversationTurn(
            turn=1,
            actor="user",
            action="message",
            thoughts=request.message,
        )
        await blackboard.append_turn(event_id, user_turn)
        logger.info(f"Chat event created: {event_id} for service {request.service}")
        return ChatEventResponse(event_id=event_id)
    except Exception as e:
        logger.error(f"Failed to create chat event: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create event: {e}")
