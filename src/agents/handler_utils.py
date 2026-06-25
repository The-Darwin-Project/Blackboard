# BlackBoard/src/agents/handler_utils.py
# @ai-rules:
# 1. [Pattern]: Shared utilities for tool handler modules. Leaf module — no circular imports.
# 2. [Constraint]: No Brain import. No handler logic. Only helpers used by multiple handler files.
# 3. [Pattern]: Import ConversationTurn from ..models, ToolContext from .tool_router (TYPE_CHECKING).
"""Shared utilities for tool handler modules."""
from __future__ import annotations

from typing import TYPE_CHECKING

from ..models import ConversationTurn

if TYPE_CHECKING:
    from .tool_router import ToolContext


def _safe_int(val, *, default: int | None = None) -> int | None:
    if val is None or isinstance(val, bool):
        return default
    try:
        result = int(val)
        return result if result > 0 else default
    except (ValueError, TypeError, OverflowError):
        return default


async def emit_tool_result(
    ctx: "ToolContext", event_id: str, *,
    tool_name: str = "",
    thoughts: str = "",
    evidence: str = "",
    response_parts: "list[dict] | None" = None,
) -> None:
    """Build and broadcast a standard tool_result ConversationTurn.

    Covers the two most common field combinations (thoughts-only and evidence-only).
    Handlers with special fields (result, taskForAgent, plan, pendingApproval,
    timestamp) should construct ConversationTurn manually.
    """
    turn = ConversationTurn(
        turn=(await ctx.next_turn_number(event_id)),
        actor="brain",
        action="tool_result",
        thoughts=thoughts or None,
        evidence=evidence or None,
        waitingFor=tool_name or None,
        response_parts=response_parts,
    )
    await ctx.append_and_broadcast(event_id, turn)
