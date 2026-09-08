# BlackBoard/src/routes/chat.py
# @ai-rules:
# 1. [Pattern]: Append-to-existing-event ownership check mirrors queue.py's
#    enforce_casual_domain (created_by_email pattern), but uses
#    get_user_from_request (graceful anonymous fallback) instead of
#    Depends(require_auth). require_auth hard-401s anonymous callers, which
#    would make this route unreachable in the default DEX_ENABLED=false
#    deployment (see knowledge_graph_api.py's ai-rule) -- chat must keep
#    working with no auth configured. Only deny when the target event has a
#    recorded owner that differs from the caller; events with no recorded
#    owner (default/no-Dex deployment) remain open, same as pre-existing
#    single-tenant behavior.
# 2. [Pattern]: Brain-notification failures around the append-to-existing
#    path are caught broadly (Exception, not just RuntimeError) and logged
#    as non-fatal -- same fire-and-forget convention as queue.py's
#    persist_report/archive_event. The turn is already durably persisted by
#    append_turn before this block runs, so letting a transient error (e.g.
#    Redis WatchError/ConnectionError from resume_if_parked) escape to the
#    outer except-Exception-500 would make a REST-fallback client retry and
#    append a second duplicate turn (no idempotency key exists here).
"""
Chat endpoint - creates events for Brain processing.

The chat endpoint now creates events in the conversation queue.
The Brain processes them asynchronously via the event loop.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from ..auth import get_user_from_request
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
    http_request: Request,
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
    user = get_user_from_request(http_request)
    try:
        if request.event_id:
            existing = await blackboard.get_event(request.event_id)
            if existing:
                if existing.created_by_email and existing.created_by_email != user.email:
                    logger.warning(
                        "Denied chat append to event %s: caller %s is not the owner",
                        request.event_id, user.email,
                    )
                    raise HTTPException(
                        status_code=403, detail="Not authorized to post to this event"
                    )
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
                except Exception as e:
                    logger.warning(
                        "Brain notification failed for %s (non-fatal): %s",
                        request.event_id, e,
                    )
                logger.info("Chat message appended to existing event: %s", request.event_id)
                return ChatEventResponse(event_id=request.event_id, status="appended")
            logger.warning(
                "Chat event_id %s not found; creating a new event instead", request.event_id
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
            created_by_email=user.email,
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
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create chat event: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create event: {e}")
