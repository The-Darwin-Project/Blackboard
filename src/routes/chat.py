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

from ..dependencies import get_blackboard
from ..models import ConversationTurn, EventEvidence
from ..state.blackboard import BlackboardState

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["chat"])


class ChatEventRequest(BaseModel):
    """Request to create a chat event."""
    message: str = Field(..., description="User message or request")
    service: str = Field("general", description="Target service (or 'general')")


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
    Create a new event from user chat message.
    
    The Brain will process this event asynchronously.
    Poll GET /queue/{event_id} to track conversation progress.
    """
    try:
        event_id = await blackboard.create_event(
            source="chat",
            service=request.service,
            reason=request.message,
            evidence=EventEvidence(
                display_text=request.message,
                source_type="chat",
                domain="complicated",
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
