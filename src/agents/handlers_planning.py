# BlackBoard/src/agents/handlers_planning.py
# @ai-rules:
# 1. [Pattern]: Plan creation and progress tracking handlers.
# 2. [Constraint]: No Brain import. All state access via ToolContext protocol.
# 3. [Pattern]: Every handler returns bool (True = re-invoke LLM, False = stop).
# 4. [Constraint]: Called within per-event asyncio.Lock — MUST NOT re-acquire.
"""Plan creation and progress tracking tool handlers."""
from __future__ import annotations

import logging
import math
from typing import TYPE_CHECKING

from ..models import ConversationTurn

if TYPE_CHECKING:
    from .tool_router import ToolContext

logger = logging.getLogger("darwin.brain")

_ORCHESTRATOR_ROLES = frozenset({"brain", "architect", "headhunter", "aligner"})


def _canonical_role(value: object) -> str:
    """Canonical role key; non-string input (malformed stored payloads) yields "" instead of raising.

    Mirrors ui/src/utils/planState.ts canonicalRole.
    """
    if not isinstance(value, str):
        return ""
    return value.strip().lower().replace("-", "_").replace(" ", "_")


def _normalize_step_id(value: object) -> str | None:
    """Canonical step id: non-empty (trimmed) strings and finite numbers; anything else -> None.

    None / bool / empty / NaN / containers are rejected, so such steps and plan_step updates are dropped.
    Mirrors ui/src/utils/planState.ts normalizeStepId -- keep in sync. Integral floats render without
    ".0" (JSON 1.0 and 1 are the same id on both sides).
    """
    if isinstance(value, bool):
        return None
    if isinstance(value, str):
        return value.strip() or None
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float) and math.isfinite(value):
        return str(int(value)) if value.is_integer() and abs(value) < 2**53 else repr(value)
    return None


def _is_orchestrator_turn(t: ConversationTurn) -> bool:
    """True if the turn's actor OR its taskForAgent.source is an orchestrator role.

    Mirrors ui/src/utils/planState.ts isOrchestratorPlan so backend and UI agree.
    """
    if _canonical_role(t.actor) in _ORCHESTRATOR_ROLES:
        return True
    return _canonical_role((t.taskForAgent or {}).get("source")) in _ORCHESTRATOR_ROLES


def _is_failed_turn(t: ConversationTurn) -> bool:
    """A failed/aborted worker turn must not auto-complete a plan step (dispatch.py "Error:" convention)."""
    return t.action == "error" or (isinstance(t.result, str) and t.result.lstrip().startswith("Error:"))


def _auto_complete_step(steps: dict[str, dict], agent_role: str) -> None:
    """Complete ONE step for agent_role: prefer in_progress, else first pending. Never touches blocked/completed."""
    mine = [s for s in steps.values() if _canonical_role(s.get("agent")) == agent_role]
    target = next((s for s in mine if s["status"] == "in_progress"), None) \
        or next((s for s in mine if s["status"] == "pending"), None)
    if target is not None:
        target["status"] = "completed"


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
    step_map = [{"id": _normalize_step_id(s.get("id")) or "", "agent": s.get("agent", ""), "summary": s.get("summary", "")} for s in steps]
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
    orchestrator_found: tuple[int, ConversationTurn] | None = None
    agent_found: tuple[int, ConversationTurn] | None = None
    for idx in range(len(event_doc.conversation) - 1, -1, -1):
        t = event_doc.conversation[idx]
        if t.action == "plan" and t.taskForAgent and "steps" in t.taskForAgent:
            if _is_orchestrator_turn(t):
                if orchestrator_found is None:
                    orchestrator_found = (idx, t)
            elif agent_found is None:
                agent_found = (idx, t)
    found = orchestrator_found or agent_found
    if found is None:
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
    plan_index, plan_turn = found
    raw_steps = plan_turn.taskForAgent.get("steps")
    steps: dict[str, dict] = {}
    for s in raw_steps if isinstance(raw_steps, list) else []:
        sid = _normalize_step_id(s.get("id")) if isinstance(s, dict) else None
        if sid is not None:
            steps[sid] = {**s, "id": sid, "status": "pending"}
    # Only turns strictly AFTER the plan turn count (positional, like the UI; plus a turn-number guard for
    # colliding numbers): the plan turn itself (esp. a worker-authored fallback plan) must never complete
    # its own step, and pre-replan turns are ignored.
    plan_turn_num = plan_turn.turn
    for idx, t in enumerate(event_doc.conversation):
        if idx <= plan_index:
            continue
        if plan_turn_num is not None and t.turn is not None and t.turn <= plan_turn_num:
            continue
        if t.action == "plan_step" and t.taskForAgent:
            sid = _normalize_step_id(t.taskForAgent.get("step_id"))
            if sid is not None and sid in steps:
                step_agent = _canonical_role(steps[sid].get("agent"))
                actor = _canonical_role(t.actor)
                if step_agent and actor not in _ORCHESTRATOR_ROLES and actor != step_agent:
                    logger.warning(
                        f"Ignored plan_step update for step {sid} on {event_id}: "
                        f"actor '{actor}' does not own step (assigned to '{step_agent}')"
                    )
                    continue
                steps[sid]["status"] = t.taskForAgent.get("status", "completed")
        elif (
            (t.action == "execute" or (t.action == "plan" and not _is_orchestrator_turn(t)))
            and t.actor
            and not _is_failed_turn(t)
        ):
            actor = _canonical_role(t.actor)
            if actor and actor not in _ORCHESTRATOR_ROLES:
                _auto_complete_step(steps, actor)
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
