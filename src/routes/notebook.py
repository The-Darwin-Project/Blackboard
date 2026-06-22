# BlackBoard/src/routes/notebook.py
# @ai-rules:
# 1. [Pattern]: Follows timekeeper.py pattern -- APIRouter with prefix, Depends(get_blackboard), require_auth on mutations.
# 2. [Constraint]: PATCH validates category via Pydantic Literal; extra="forbid" rejects unknown fields.
# 3. [Gotcha]: During Nightwatcher drain (~seconds per 12h cycle), PATCH/DELETE may 404 -- acceptable UX.
"""Field Notes Notebook API -- CRUD for FRIDAY's qualitative knowledge capture."""
from __future__ import annotations

import logging
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from ..auth import UserContext, require_auth
from ..dependencies import get_blackboard
from ..state.blackboard import BlackboardState

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/notebook", tags=["notebook"])

CategoryType = Literal["env-quirk", "correction", "cross-event", "workflow", "convention"]


class NotePatchRequest(BaseModel):
    content: Optional[str] = Field(None, max_length=2000)
    category: Optional[CategoryType] = None
    model_config = ConfigDict(extra="forbid")


@router.get("")
async def get_notebook(
    blackboard: BlackboardState = Depends(get_blackboard),
):
    """Return all field notes sorted by timestamp."""
    notes = await blackboard.get_notes()
    return {"notes": notes, "count": len(notes)}


@router.patch("/{note_id}")
async def update_notebook_note(
    note_id: str,
    body: NotePatchRequest,
    user: UserContext = Depends(require_auth),
    blackboard: BlackboardState = Depends(get_blackboard),
):
    """Update a note's content and/or category."""
    success = await blackboard.update_note(
        note_id, content=body.content, category=body.category,
    )
    if not success:
        raise HTTPException(404, "Note not found")
    return {"status": "updated"}


@router.delete("/{note_id}")
async def delete_notebook_note(
    note_id: str,
    user: UserContext = Depends(require_auth),
    blackboard: BlackboardState = Depends(get_blackboard),
):
    """Delete a field note."""
    success = await blackboard.delete_note(note_id)
    if not success:
        raise HTTPException(404, "Note not found")
    return {"status": "deleted"}
