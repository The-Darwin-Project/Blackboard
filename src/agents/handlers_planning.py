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

_ORCHESTRATOR_ROLES = frozenset({"brain", "architect", "headhunter", "aligner"})


def _canonical_role(role: str | None) -> str:
    return (role or "").strip().lower().replace("-", "_").replace(" ", "_")


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
    orchestrator_turn = None
    agent_turn = None
    for t in reversed(event_doc.conversation):
        if t.action == "plan" and t.taskForAgent and isinstance(t.taskForAgent, dict) and "steps" in t.taskForAgent:
            source = _canonical_role(t.taskForAgent.get("source") or t.actor)
            if source in _ORCHESTRATOR_ROLES:
                if not orchestrator_turn:
                    orchestrator_turn = t
            else:
                if not agent_turn:
                    agent_turn = t
    plan_turn = orchestrator_turn or agent_turn
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
    raw_steps = plan_turn.taskForAgent.get("steps") if isinstance(plan_turn.taskForAgent, dict) else None
    steps = {str(s.get("id")): {**s, "status": "pending"} for s in (raw_steps or []) if isinstance(s, dict) and "id" in s}
    # Process updates on or after the plan turn
    plan_turn_num = plan_turn.turn if plan_turn.turn is not None else 0
    for t in event_doc.conversation:
        if (t.turn is not None and t.turn < plan_turn_num):
            continue
        if t.action == "plan_step" and t.taskForAgent and isinstance(t.taskForAgent, dict) and "step_id" in t.taskForAgent:
            sid = str(t.taskForAgent["step_id"])
            if sid in steps:
                step_agent = _canonical_role(steps[sid].get("agent"))
                actor = _canonical_role(t.actor)
                if step_agent and actor not in _ORCHESTRATOR_ROLES and actor != step_agent:
                    continue
                steps[sid]["status"] = t.taskForAgent.get("status", "completed")
        elif (t.action == "execute" or (t.action == "plan" and _canonical_role(t.actor) not in _ORCHESTRATOR_ROLES)) and t.actor:
            actor = _canonical_role(t.actor)
            if actor and actor not in _ORCHESTRATOR_ROLES:
                for s in steps.values():
                    s_agent = _canonical_role(s.get("agent"))
                    if s_agent == actor and s.get("status") in ("pending", "in_progress"):
                        s["status"] = "completed"
                        break
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
