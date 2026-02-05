# BlackBoard/src/routes/chat.py
"""
Chat endpoint for Architect interaction.

Provides the interface for operators to communicate with Agent 2 (Architect).
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, HTTPException

from ..models import ChatRequest, ChatResponse
from ..dependencies import get_architect

if TYPE_CHECKING:
    from ..agents.architect import Architect

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("/", response_model=ChatResponse)
async def chat_with_architect(
    request: ChatRequest,
    architect: "Architect" = Depends(get_architect),
) -> ChatResponse:
    """
    Send a message to the Architect agent.
    
    The Architect analyzes the current topology and metrics,
    then generates a structured plan if appropriate.
    
    Supports multi-turn conversations via conversation_id:
    - First message: omit conversation_id, server generates one
    - Follow-up messages: include conversation_id from previous response
    
    Examples:
        - "Scale inventory-api to 3 replicas"
        - "What's the current state of the system?"
        - "Optimize postgres for high traffic"
    """
    try:
        response = await architect.chat(
            request.message,
            conversation_id=request.conversation_id,
        )
        
        logger.info(
            f"Architect response: {response.message[:100]}..."
            f" plan_id={response.plan_id}"
            f" conversation_id={response.conversation_id}"
        )
        
        return response
    
    except Exception as e:
        logger.error(f"Architect chat failed: {e}")
        raise HTTPException(status_code=500, detail=f"Architect error: {e}")
