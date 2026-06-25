# BlackBoard/src/agents/handlers_planning.py
# @ai-rules:
# 1. [Pattern]: Plan creation and progress tracking handlers.
# 2. [Constraint]: No Brain import. All state access via ToolContext protocol.
# 3. [Pattern]: Every handler returns bool (True = re-invoke LLM, False = stop).
# 4. [Constraint]: Called within per-event asyncio.Lock — MUST NOT re-acquire.
"""Plan creation and progress tracking tool handlers."""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from ..models import ConversationTurn

if TYPE_CHECKING:
    from .tool_router import ToolContext

logger = logging.getLogger("darwin.brain")


async def handle_create_plan(
    ctx: ToolContext, event_id: str, args: dict, response_parts: list[dict] | None,
) -> bool:
    steps = args.get("steps", [])
    reasoning = args.get("reasoning", "")
    if not steps:
        logger.warning(f"create_plan called with no steps for {event_id}")
        turn = ConversationTurn(
            turn=(await ctx.next_turn_number(event_id)),
            actor="brain",
            action="tool_result",
            thoughts="Plan creation needs at least one step with an assigned participant and objective. "
                     "Review the conversation to identify which agents should act and on what.",
            waitingFor="create_plan",
            response_parts=response_parts,
        )
        await ctx.append_and_broadcast(event_id, turn)
        return True
    plan_lines = [f"## Plan\n\n{reasoning}\n"]
    for s in steps:
        plan_lines.append(f"{s.get('id', '?')}. **{s.get('agent', '?')}**: {s.get('summary', '')}")
    plan_md = "\n".join(plan_lines)
    step_map = [{"id": str(s.get("id", "")), "agent": s.get("agent", ""), "summary": s.get("summary", "")} for s in steps]
    turn = ConversationTurn(
        turn=(await ctx.next_turn_number(event_id)),
        actor="brain",
        action="plan",
        plan=plan_md,
        thoughts=f"Plan created: {len(steps)} steps. {reasoning}",
        taskForAgent={"steps": step_map, "source": "brain"},
        waitingFor="create_plan",
        response_parts=response_parts,
    )
    await ctx.append_and_broadcast(event_id, turn)
    logger.info(f"Brain chalked plan for {event_id}: {len(steps)} steps")
    return True


async def handle_get_plan_progress(
    ctx: ToolContext, event_id: str, args: dict, response_parts: list[dict] | None,
) -> bool:
    bb = ctx.get_blackboard()
    event_doc = await bb.get_event(event_id)
    if not event_doc:
        turn = ConversationTurn(
            turn=(await ctx.next_turn_number(event_id)),
            actor="brain",
            action="tool_result",
            thoughts="Event data is temporarily unavailable. "
                     "Wait for the next update from the conversation.",
            response_parts=response_parts,
        )
        await ctx.append_and_broadcast(event_id, turn)
        return False
    plan_turn = None
    for t in reversed(event_doc.conversation):
        if t.action == "plan" and t.taskForAgent and "steps" in t.taskForAgent:
            plan_turn = t
            break
    if not plan_turn:
        turn = ConversationTurn(
            turn=(await ctx.next_turn_number(event_id)),
            actor="brain", action="tool_result",
            waitingFor="get_plan_progress",
            evidence="## Plan Progress\n\nNo plan has been created for this event yet. "
                     "If a plan is needed, create one first with the appropriate agents and steps.",
            response_parts=response_parts,
        )
        await ctx.append_and_broadcast(event_id, turn)
        return False
    steps = {s["id"]: {**s, "status": "pending"} for s in plan_turn.taskForAgent["steps"]}
    for t in event_doc.conversation:
        if t.action == "plan_step" and t.taskForAgent and "step_id" in t.taskForAgent:
            sid = t.taskForAgent["step_id"]
            if sid in steps:
                steps[sid]["status"] = t.taskForAgent.get("status", "completed")
    progress = list(steps.values())
    done = sum(1 for s in progress if s["status"] == "completed")
    summary = f"## Plan Progress\n\n{done}/{len(progress)} steps completed:\n\n"
    for s in progress:
        icon = {"completed": "- [x]", "in_progress": "- [~]", "blocked": "- [!]"}.get(s["status"], "- [ ]")
        summary += f"{icon} Step {s['id']}: {s.get('summary', '')} ({s.get('agent', '?')}) -- {s['status']}\n"
    turn = ConversationTurn(
        turn=(await ctx.next_turn_number(event_id)),
        actor="brain", action="tool_result",
        waitingFor="get_plan_progress",
        evidence=summary.strip(),
        response_parts=response_parts,
    )
    await ctx.append_and_broadcast(event_id, turn)
    return True


# ---------------------------------------------------------------------------
# Registry registration
# ---------------------------------------------------------------------------
from .tool_router import HANDLER_REGISTRY

HANDLER_REGISTRY["create_plan"] = handle_create_plan
HANDLER_REGISTRY["get_plan_progress"] = handle_get_plan_progress
