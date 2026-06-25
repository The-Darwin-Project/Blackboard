# BlackBoard/src/agents/handlers_verification.py
# @ai-rules:
# 1. [Pattern]: Verification and phase transition handlers.
# 2. [Constraint]: No Brain import. All state access via ToolContext protocol.
# 3. [Pattern]: Every handler returns bool (True = re-invoke LLM, False = stop).
# 4. [Constraint]: Called within per-event asyncio.Lock — MUST NOT re-acquire.
"""Verification and phase transition tool handlers."""
from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING

from ..models import ConversationTurn, _resolve_phase

if TYPE_CHECKING:
    from .tool_router import ToolContext

logger = logging.getLogger("darwin.brain")


async def handle_set_phase(
    ctx: ToolContext, event_id: str, args: dict, response_parts: list[dict] | None,
) -> bool:
    phase = _resolve_phase(args.get("phase", "triage"))
    reasoning = args.get("reasoning", "")
    bb = ctx.get_blackboard()
    event_doc = await bb.get_event(event_id)
    current_phase = _resolve_phase(event_doc.brain_phase) if event_doc else None
    if current_phase is not None and phase == current_phase:
        logger.debug(f"set_phase: confirmed {phase} for {event_id}")
        if event_doc and event_doc.brain_phase != phase:
            await bb.update_event_phase(event_id, phase)
        turn = ConversationTurn(
            turn=(await ctx.next_turn_number(event_id)),
            actor="brain",
            action="phase",
            thoughts=f"Phase: {phase.upper()} (confirmed). {reasoning}",
            waitingFor="set_phase",
            response_parts=response_parts,
            timestamp=time.time(),
        )
        await ctx.append_and_broadcast(event_id, turn)
        return True
    await bb.update_event_phase(event_id, phase)
    thoughts = f"Phase: {phase.upper()}. {reasoning}"
    logger.info(f"Phase transition: {current_phase} -> {phase} for {event_id} ({reasoning})")
    turn = ConversationTurn(
        turn=(await ctx.next_turn_number(event_id)),
        actor="brain",
        action="phase",
        thoughts=thoughts,
        waitingFor="set_phase",
        response_parts=response_parts,
        timestamp=time.time(),
    )
    await ctx.append_and_broadcast(event_id, turn)
    await ctx.broadcast({
        "type": "phase_updated",
        "event_id": event_id,
        "phase": phase,
    })
    await ctx.emit_pulse(event_id, [(f"phase:{phase}", "phase")])
    return True


async def handle_re_trigger_aligner(
    ctx: ToolContext, event_id: str, args: dict, response_parts: list[dict] | None,
) -> bool:
    service = args.get("service", "")
    condition = args.get("check_condition", "")
    aligner = ctx.get_agent_instance("_aligner")
    if not aligner or not service:
        turn = ConversationTurn(
            turn=(await ctx.next_turn_number(event_id)),
            actor="brain",
            action="tool_result",
            thoughts="Service health data is not available for this event. "
                     "Consider checking the ops journal for recent entries, "
                     "or dispatching an agent to investigate directly.",
            response_parts=response_parts,
        )
        await ctx.append_and_broadcast(event_id, turn)
        return False
    try:
        state = await aligner.check_state(service)
    except Exception as e:
        logger.warning(f"re_trigger_aligner check_state failed for {service}: {e}")
        turn = ConversationTurn(
            turn=(await ctx.next_turn_number(event_id)),
            actor="brain",
            action="tool_result",
            thoughts="Service health check failed. "
                     "Consider deferring briefly and retrying, "
                     "or dispatching an agent to investigate directly.",
            response_parts=response_parts,
        )
        await ctx.append_and_broadcast(event_id, turn)
        return False
    verify_turn = ConversationTurn(
        turn=(await ctx.next_turn_number(event_id)),
        actor="brain",
        action="verify",
        thoughts=f"Re-triggering Aligner to check: {condition}",
        evidence=f"target_service:{service}",
    )
    await ctx.append_and_broadcast(event_id, verify_turn)
    confirm_turn = ConversationTurn(
        turn=(await ctx.next_turn_number(event_id)),
        actor="aligner",
        action="confirm",
        evidence=(
            f"Service: {state['service']}, "
            f"CPU: {state.get('cpu', 0):.1f}%, "
            f"Memory: {state.get('memory', 0):.1f}%, "
            f"Replicas: {state.get('replicas_ready', '?')}/{state.get('replicas_desired', '?')}"
        ),
    )
    await ctx.append_and_broadcast(event_id, confirm_turn)
    return False


async def handle_wait_for_verification(
    ctx: ToolContext, event_id: str, args: dict, response_parts: list[dict] | None,
) -> bool:
    condition = args.get("condition", "")
    bb = ctx.get_blackboard()
    event = await bb.get_event(event_id)
    target_service = event.service if event else ""
    aligner = ctx.get_agent_instance("_aligner")
    if aligner and target_service:
        state = await aligner.check_state(target_service)
        verify_turn = ConversationTurn(
            turn=(await ctx.next_turn_number(event_id)),
            actor="brain",
            action="verify",
            thoughts=f"Waiting for verification: {condition}",
            evidence=f"target_service:{target_service}",
            waitingFor="wait_for_verification",
        )
        await ctx.append_and_broadcast(event_id, verify_turn)
        confirm_turn = ConversationTurn(
            turn=(await ctx.next_turn_number(event_id)),
            actor="aligner",
            action="confirm",
            evidence=(
                f"Service: {state['service']}, "
                f"CPU: {state.get('cpu', 0):.1f}%, "
                f"Memory: {state.get('memory', 0):.1f}%, "
                f"Replicas: {state.get('replicas_ready', '?')}/{state.get('replicas_desired', '?')}"
            ),
            waitingFor="wait_for_verification",
        )
        await ctx.append_and_broadcast(event_id, confirm_turn)
    else:
        turn = ConversationTurn(
            turn=(await ctx.next_turn_number(event_id)),
            actor="brain",
            action="tool_result",
            thoughts="Verification data is not available for this service right now. "
                     "Consider what other tools or participants in the conversation "
                     "might confirm whether the situation has changed since the last check.",
            waitingFor="wait_for_verification",
            response_parts=response_parts,
        )
        await ctx.append_and_broadcast(event_id, turn)
    return True


# ---------------------------------------------------------------------------
# Registry registration
# ---------------------------------------------------------------------------
from .tool_router import HANDLER_REGISTRY

HANDLER_REGISTRY["set_phase"] = handle_set_phase
HANDLER_REGISTRY["re_trigger_aligner"] = handle_re_trigger_aligner
HANDLER_REGISTRY["wait_for_verification"] = handle_wait_for_verification
