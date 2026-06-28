# BlackBoard/src/agents/handlers_state.py
# @ai-rules:
# 1. [Pattern]: Group B+E "wait-state + subscription + close" handlers. Full ToolContext mutation.
# 2. [Constraint]: No Brain import. All state access via ToolContext protocol.
# 3. [Pattern]: Every handler returns bool (True = re-invoke LLM, False = stop).
# 4. [Constraint]: Called within per-event asyncio.Lock — MUST NOT re-acquire.
# 5. [Gotcha]: defer_event uses ctx.get_blackboard().defer_event_status() (not raw Redis).
# 6. [Gotcha]: close_event delegates to ctx.close_and_broadcast() which stays on Brain.
"""Group B+E: 9 wait-state, subscription, and close tool handlers."""
from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import TYPE_CHECKING

from ..models import ConversationTurn, EventStatus, EventType, _resolve_domain, _resolve_phase

if TYPE_CHECKING:
    from .tool_router import ToolContext

logger = logging.getLogger("darwin.brain")


# ---------------------------------------------------------------------------
# close_event
# ---------------------------------------------------------------------------
async def handle_close_event(
    ctx: ToolContext, event_id: str, args: dict, response_parts: list[dict] | None,
) -> bool:
    summary = args.get("summary", "Event closed.")
    await ctx.close_and_broadcast(event_id, summary)
    return False


# ---------------------------------------------------------------------------
# request_user_approval
# ---------------------------------------------------------------------------
async def handle_request_user_approval(
    ctx: ToolContext, event_id: str, args: dict, response_parts: list[dict] | None,
) -> bool:
    plan_summary = args.get("plan_summary", "")
    ctx.mark_waiting_for_user(event_id)
    turn = ConversationTurn(
        turn=(await ctx.next_turn_number(event_id)),
        actor="brain",
        action="request_approval",
        thoughts=plan_summary,
        pendingApproval=True,
        waitingFor="user",
    )
    await ctx.append_and_broadcast(event_id, turn)
    bb = ctx.get_blackboard()
    await bb.park_for_approval(event_id)
    event = await bb.get_event(event_id)
    if event and event.source in ("slack", "chat"):
        ctx.get_idle_timeout().schedule(event_id, warning_sec=ctx.get_conversation_timeout(event))
    return False


# ---------------------------------------------------------------------------
# wait_for_user
# ---------------------------------------------------------------------------
async def handle_wait_for_user(
    ctx: ToolContext, event_id: str, args: dict, response_parts: list[dict] | None,
) -> bool:
    bb = ctx.get_blackboard()
    event = await bb.get_event(event_id)
    if event and event.source not in ("chat", "slack"):
        turn = ConversationTurn(
            turn=(await ctx.next_turn_number(event_id)),
            actor="brain",
            action="tool_result",
            thoughts="wait_for_user is not available for automated events. "
                     "Use request_user_approval to pause for human authorization, "
                     "or defer_event to wait for external processes.",
            waitingFor="wait_for_user",
        )
        await ctx.append_and_broadcast(event_id, turn)
        return False
    summary = args.get("summary", "")
    ctx.mark_waiting_for_user(event_id)
    turn = ConversationTurn(
        turn=(await ctx.next_turn_number(event_id)),
        actor="brain",
        action="wait",
        thoughts=summary,
        waitingFor="user",
    )
    await ctx.append_and_broadcast(event_id, turn)
    event = await bb.get_event(event_id)
    if event and event.source in ("slack", "chat"):
        ctx.get_idle_timeout().schedule(event_id, warning_sec=ctx.get_conversation_timeout(event))
    return False


# ---------------------------------------------------------------------------
# wait_for_agent
# ---------------------------------------------------------------------------
async def handle_wait_for_agent(
    ctx: ToolContext, event_id: str, args: dict, response_parts: list[dict] | None,
) -> bool:
    if not ctx.get_active_agent_for_event(event_id):
        logger.info("wait_for_agent rejected: no active agent for %s", event_id)
        turn = ConversationTurn(
            turn=(await ctx.next_turn_number(event_id)),
            actor="brain",
            action="tool_result",
            thoughts=(
                "No agent is currently running for this event. "
                "The agent already delivered results above. To continue: "
                "(1) dispatch another agent with select_agent, or "
                "(2) defer the event with defer_event to wait for an "
                "external process."
            ),
            waitingFor="wait_for_agent",
            response_parts=response_parts,
        )
        await ctx.append_and_broadcast(event_id, turn)
        return False
    summary = args.get("summary", "")
    agent_name = ctx.get_active_agent_for_event(event_id) or "unknown"
    wait_turn = await ctx.next_turn_number(event_id)
    ctx.mark_waiting_for_agent(event_id, agent_name, wait_turn)
    turn = ConversationTurn(
        turn=wait_turn,
        actor="brain",
        action="wait",
        thoughts=summary,
        waitingFor=f"agent:{agent_name}",
    )
    await ctx.append_and_broadcast(event_id, turn)
    return False


# ---------------------------------------------------------------------------
# wait_for_jarvis
# ---------------------------------------------------------------------------
async def handle_wait_for_jarvis(
    ctx: ToolContext, event_id: str, args: dict, response_parts: list[dict] | None,
) -> bool:
    if ctx.has_jarvis_waiters() and ctx.get_jarvis_wait_count(event_id) > 0:
        # Already waiting — exit loop
        return False
    context = args.get("context", "")
    bb = ctx.get_blackboard()
    event = await bb.get_event(event_id)
    if not event:
        return False
    last_respond_ts = 0.0
    for t in reversed(event.conversation):
        if t.actor == "brain" and t.action == "respond_jarvis":
            last_respond_ts = t.timestamp or 0.0
            break
    if last_respond_ts:
        existing_reply = next(
            (t for t in event.conversation
             if t.actor == "jarvis" and t.action == "message"
             and (t.timestamp or 0.0) > last_respond_ts),
            None,
        )
        if existing_reply:
            result_text = "JARVIS already replied. Check his message above."
            turn = ConversationTurn(
                turn=(await ctx.next_turn_number(event_id)),
                actor="brain", action="tool_result",
                waitingFor="wait_for_jarvis",
                thoughts=result_text,
                response_parts=response_parts,
            )
            await ctx.append_and_broadcast(event_id, turn)
            return True
    turn = ConversationTurn(
        turn=(await ctx.next_turn_number(event_id)),
        actor="brain",
        action="wait",
        thoughts=f"Waiting for JARVIS response: {context}",
        waitingFor="jarvis",
    )
    await ctx.append_and_broadcast(event_id, turn)
    ctx.mark_jarvis_wait(event_id, last_respond_ts or time.time())
    ctx.increment_jarvis_wait_count(event_id)
    ctx.update_last_processed(event_id)
    return False


# ---------------------------------------------------------------------------
# hold_watch
# ---------------------------------------------------------------------------
async def handle_hold_watch(
    ctx: ToolContext, event_id: str, args: dict, response_parts: list[dict] | None,
) -> bool:
    bb = ctx.get_blackboard()
    event = await bb.get_event(event_id)
    if not event:
        return False
    if event.source != "jarvis" or _resolve_phase(event.brain_phase) != "close":
        reject_turn = ConversationTurn(
            turn=(await ctx.next_turn_number(event_id)),
            actor="brain",
            action="tool_result",
            thoughts="hold_watch is only available for jarvis-sourced events in the close phase.",
            response_parts=response_parts,
        )
        await ctx.append_and_broadcast(event_id, reject_turn)
        return True
    ctx.clear_jarvis_wait(event_id)
    active_status_map = await bb.get_active_events_with_status()
    parked_deferred = frozenset(
        eid for eid, status in active_status_map.items()
        if eid != event_id and status == "deferred"
    )
    ctx.set_hold_watch(event_id, parked_deferred)
    ctx.set_hold_watch_park_time(event_id)
    context = args.get("context", "")
    turn = ConversationTurn(
        turn=(await ctx.next_turn_number(event_id)),
        actor="brain",
        action="hold_watch",
        thoughts=f"Parking: {context}" if context else "Parking in hold_watch",
        waitingFor="hold_watch",
    )
    await ctx.append_and_broadcast(event_id, turn)
    logger.info(
        "hold_watch parked %s (deferred_snapshot=%d)",
        event_id, len(parked_deferred),
    )
    return False


# ---------------------------------------------------------------------------
# classify_event
# ---------------------------------------------------------------------------
async def handle_classify_event(
    ctx: ToolContext, event_id: str, args: dict, response_parts: list[dict] | None,
) -> bool:
    domain = _resolve_domain(args.get("domain", "complicated"))
    reasoning = args.get("reasoning", "")
    severity = args.get("severity")
    intent = args.get("intent")
    bb = ctx.get_blackboard()
    if domain == "casual":
        event_doc = await bb.get_event(event_id)
        if not event_doc:
            logger.warning(f"classify_event: cannot verify source for {event_id}, rejecting casual")
            turn = ConversationTurn(
                turn=(await ctx.next_turn_number(event_id)),
                actor="brain", action="tool_result",
                waitingFor="classify_event",
                evidence=(
                    "[GATE] casual domain rejected. State: event not found. "
                    "Constraint: cannot verify source. Reclassify with an operational domain."
                ),
                response_parts=[],
            )
            await ctx.append_and_broadcast(event_id, turn)
            return True
        if event_doc.source not in ("chat", "slack"):
            turn = ConversationTurn(
                turn=(await ctx.next_turn_number(event_id)),
                actor="brain", action="tool_result",
                waitingFor="classify_event",
                evidence=(
                    "[GATE] casual domain rejected. State: source is "
                    f"{event_doc.source}. Constraint: casual is only valid for "
                    "chat/slack events. Reclassify with an operational domain."
                ),
                response_parts=[],
            )
            await ctx.append_and_broadcast(event_id, turn)
            return True
    await bb.update_event_domain(event_id, domain)
    thoughts = f"Cynefin: {domain.upper()}."
    if severity:
        await bb.update_event_severity(event_id, severity)
        thoughts += f" Severity: {severity}."
        await ctx.broadcast({"type": "severity_updated", "event_id": event_id, "severity": severity})
    thoughts += f" {reasoning}"
    turn = ConversationTurn(
        turn=(await ctx.next_turn_number(event_id)),
        actor="brain", action="triage",
        thoughts=thoughts,
        timestamp=time.time(),
    )
    await ctx.append_and_broadcast(event_id, turn)
    await ctx.broadcast({"type": "domain_updated", "event_id": event_id, "domain": domain})
    domain_directives = {
        "casual": "Domain locked: CASUAL. Respond to the user conversationally now. Do not reclassify unless the user's next message shifts to a task.",
        "clear": "Domain set: CLEAR. Known solution exists. Execute the best practice or transition phase to proceed.",
        "complicated": "Domain set: COMPLICATED. Classification registered. Transition phase or dispatch an agent to proceed.",
        "complex": "Domain set: COMPLEX. Design a safe-to-fail probe before acting.",
        "chaotic": "Domain set: CHAOTIC. Act immediately to stabilize, then sense.",
    }
    directive = domain_directives.get(domain, f"Domain set: {domain.upper()}. Classification registered. Proceed to next action.")
    if intent and intent.strip():
        directive += f" Your stated intent: {intent.strip()}"
    nudge = ConversationTurn(
        turn=(await ctx.next_turn_number(event_id)),
        actor="brain", action="tool_result",
        evidence=directive,
        timestamp=time.time(),
    )
    await ctx.append_and_broadcast(event_id, nudge)
    if ctx.is_waiting_for_user(event_id):
        event_doc = await bb.get_event(event_id)
        if event_doc and ctx.is_waiting_for_user(event_id):
            ctx.get_idle_timeout().schedule(
                event_id, warning_sec=ctx.get_conversation_timeout(event_doc)
            )
    return True


# ---------------------------------------------------------------------------
# defer_event
# ---------------------------------------------------------------------------
async def handle_defer_event(
    ctx: ToolContext, event_id: str, args: dict, response_parts: list[dict] | None,
) -> bool:
    if ctx.is_waiting_for_user(event_id):
        logger.warning(f"Ignoring defer_event for {event_id}: waiting for user response")
        turn = ConversationTurn(
            turn=(await ctx.next_turn_number(event_id)),
            actor="brain",
            action="tool_result",
            thoughts="This event is currently waiting for user input and "
                     "cannot be deferred until the user responds.",
            waitingFor="defer_event",
            response_parts=response_parts,
        )
        await ctx.append_and_broadcast(event_id, turn)
        return False
    ctx.clear_waiting_for_agent(event_id)
    current_cycle = ctx.get_cycle_id(event_id)
    ctx.cancel_stale_subscriptions(event_id, current_cycle)
    reason = args.get("reason", "Deferred by Brain")
    delay = max(30, min(int(args.get("delay_seconds", 60)), 3600))
    defer_started_at = time.time()
    defer_until = defer_started_at + delay
    turn = ConversationTurn(
        turn=(await ctx.next_turn_number(event_id)),
        actor="brain",
        action="defer",
        thoughts=f"Deferring event for {delay}s: {reason}",
        waitingFor="defer_event",
    )
    await ctx.append_and_broadcast(event_id, turn)
    bb = ctx.get_blackboard()
    success = await bb.defer_event_status(event_id, defer_until, delay)
    if success:
        await ctx.broadcast({
            "type": "event_status_changed",
            "event_id": event_id,
            "status": EventStatus.DEFERRED.value,
            "defer_until": defer_until,
            "defer_started_at": defer_started_at,
        })
    await ctx.record_event(
        EventType.BRAIN_EVENT_DEFERRED,
        {"event_id": event_id, "delay_seconds": delay},
        narrative=f"Event {event_id} deferred for {delay}s: {reason[:80]}",
    )
    logger.info(f"Event {event_id} deferred for {delay}s: {reason}")
    meta_id = ctx.get_active_meta_event_id()
    if meta_id and meta_id != event_id and not ctx.is_in_hold_watch(meta_id):
        event = await bb.get_event(event_id)
        service = event.service if event else "unknown"
        notify_turn = ConversationTurn(
            turn=(await ctx.next_turn_number(meta_id)),
            actor="system",
            action="notification",
            thoughts=f"[SYSTEM] evt-{event_id[:8]} ({service}) entered deferred state.",
        )
        await ctx.append_and_broadcast(meta_id, notify_turn)
        logger.debug("Injected defer notification into active meta-event %s for %s", meta_id, event_id)
    return False


# ---------------------------------------------------------------------------
# respond_to_jarvis
# ---------------------------------------------------------------------------
async def handle_respond_to_jarvis(
    ctx: ToolContext, event_id: str, args: dict, response_parts: list[dict] | None,
) -> bool:
    response_text = args.get("response", "").strip()
    if len(response_text) < 20:
        turn = ConversationTurn(
            turn=(await ctx.next_turn_number(event_id)),
            actor="brain",
            action="tool_result",
            thoughts="Response was too brief. JARVIS needs to understand your reasoning. "
                     "Include what you observed, whether you agree or disagree, "
                     "and what your next action will be.",
            waitingFor="respond_to_jarvis",
            response_parts=response_parts,
        )
        await ctx.append_and_broadcast(event_id, turn)
        await ctx.emit_pulse(event_id, [("tool:respond_to_jarvis", "tool", 0.3)])
        return True
    turn = ConversationTurn(
        turn=(await ctx.next_turn_number(event_id)),
        actor="brain",
        action="respond_jarvis",
        thoughts=response_text,
        waitingFor="respond_to_jarvis",
        response_parts=response_parts,
    )
    await ctx.append_and_broadcast(event_id, turn)
    await ctx.deliver_to_jarvis(event_id, response_text)
    logger.info(f"Responded to JARVIS for {event_id}")
    return True


# ---------------------------------------------------------------------------
# Registry registration
# ---------------------------------------------------------------------------
from .tool_router import HANDLER_REGISTRY

HANDLER_REGISTRY["close_event"] = handle_close_event
HANDLER_REGISTRY["request_user_approval"] = handle_request_user_approval
HANDLER_REGISTRY["wait_for_user"] = handle_wait_for_user
HANDLER_REGISTRY["wait_for_agent"] = handle_wait_for_agent
HANDLER_REGISTRY["wait_for_jarvis"] = handle_wait_for_jarvis
HANDLER_REGISTRY["hold_watch"] = handle_hold_watch
HANDLER_REGISTRY["classify_event"] = handle_classify_event
HANDLER_REGISTRY["defer_event"] = handle_defer_event
HANDLER_REGISTRY["respond_to_jarvis"] = handle_respond_to_jarvis
