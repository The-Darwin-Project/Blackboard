# BlackBoard/src/agents/handlers_dispatch.py
# @ai-rules:
# 1. [Pattern]: Dispatch + incident handlers. Highest Brain coupling.
# 2. [Constraint]: No Brain import. All state access via ToolContext protocol.
# 3. [Pattern]: select_agent uses ctx.run_agent_task() callback (stays on Brain).
# 4. [Gotcha]: select_agent → defer_event recursive call via ctx.dispatch_handler().
# 5. [Pattern]: _run_agent_task stays on Brain; injected as callback on ToolContext.
"""Dispatch group: reply_to_agent, select_agent, message_agent, report_incident."""
from __future__ import annotations

import asyncio
import logging
import os
import time
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from ..models import ConversationTurn, EventType
from ..utils.event_markdown import event_to_markdown

if TYPE_CHECKING:
    from .tool_router import ToolContext

logger = logging.getLogger("darwin.brain")


# ---------------------------------------------------------------------------
# reply_to_agent
# ---------------------------------------------------------------------------
async def handle_reply_to_agent(
    ctx: ToolContext, event_id: str, args: dict, response_parts: list[dict] | None,
) -> bool:
    agent_id = args.get("agent_id", "")
    message = args.get("message", "")
    from ..dependencies import get_registry_and_bridge
    registry, _ = get_registry_and_bridge()
    agent_conn = None
    if registry:
        agent_conn = await registry.get_by_id(agent_id)
        if not agent_conn:
            agent_conn = await registry.get_by_event(event_id)
        if not agent_conn:
            agent_conn = await registry.get_available(agent_id)
    if agent_conn and agent_conn.ws:
        try:
            await agent_conn.ws.send_json({
                "type": "huddle_reply",
                "task_id": agent_conn.current_task_id or "",
                "content": message,
            })
            logger.info(f"Brain reply_to_agent -> {agent_id} ({len(message)} chars)")
        except Exception as e:
            logger.warning(f"Failed to send reply_to_agent to {agent_id}: {e}")
            await ctx.emit_pulse(event_id, [("tool:reply_to_agent", "tool", 0.0)])
            followup = ConversationTurn(
                turn=(await ctx.next_turn_number(event_id)),
                actor="brain",
                action="tool_result",
                thoughts="The message was not delivered. "
                         "The agent may still be working -- check for recent updates "
                         "from them before deciding next steps.",
                waitingFor="reply_to_agent",
                response_parts=response_parts,
            )
            await ctx.append_and_broadcast(event_id, followup)
    else:
        logger.warning(f"reply_to_agent: agent {agent_id} not found or disconnected")
        await ctx.emit_pulse(event_id, [("tool:reply_to_agent", "tool", 0.3)])
        followup = ConversationTurn(
            turn=(await ctx.next_turn_number(event_id)),
            actor="brain",
            action="tool_result",
            thoughts="The message was not delivered. "
                     "The agent may still be working -- check for recent updates "
                     "from them before deciding next steps.",
            waitingFor="reply_to_agent",
            response_parts=response_parts,
        )
        await ctx.append_and_broadcast(event_id, followup)
    turn = ConversationTurn(
        turn=(await ctx.next_turn_number(event_id)),
        actor="brain",
        action="reply",
        thoughts=f"Reply to {agent_id}: {message}",
        waitingFor="reply_to_agent",
    )
    await ctx.append_and_broadcast(event_id, turn)
    return False


# ---------------------------------------------------------------------------
# select_agent / ask_agent_for_state (shared branch)
# ---------------------------------------------------------------------------
async def handle_select_agent(
    ctx: ToolContext, event_id: str, args: dict, response_parts: list[dict] | None,
) -> bool:
    agent_name = args.get("agent_name", "")
    task = args.get("task_instruction", "") or args.get("question", "")
    mode = args.get("mode", "")

    if ctx.is_task_running(event_id):
        logger.info(f"Task already active for {event_id}, skipping dispatch")
        dup_turn = ConversationTurn(
            turn=(await ctx.next_turn_number(event_id)),
            actor="brain",
            action="tool_result",
            thoughts="An agent is already actively working on this event. "
                     "Wait for their update before dispatching again.",
            response_parts=response_parts,
        )
        await ctx.append_and_broadcast(event_id, dup_turn)
        return False

    if ctx.is_dispatch_locked():
        bb = ctx.get_blackboard()
        flow = await bb.get_flow_metrics()
        logger.warning(
            f"Dispatch WIP cap reached for {event_id}, deferring "
            f"(queue_depth={flow['queue_depth']}, active={len(flow.get('active_events', []))})"
        )
        await ctx.dispatch_handler(
            "defer_event", event_id,
            {"delay_seconds": 30, "reason": "Dispatch WIP cap reached"},
            None,
        )
        return False

    depth = ctx.increment_routing_depth(event_id)
    if depth > 30:
        logger.warning(f"Event {event_id} hit routing depth limit (30)")
        await ctx.close_and_broadcast(event_id, "Agent routing loop detected. Force closed.", "force_closed")
        return False

    await ctx.stamp_event(event_id, last_dispatched_at=time.time())

    action = "route"
    turn = ConversationTurn(
        turn=(await ctx.next_turn_number(event_id)),
        actor="brain",
        action=action,
        waitingFor="select_agent",
        thoughts=f"Routing to {agent_name}: {task}",
        selectedAgents=[agent_name],
        taskForAgent={"agent": agent_name, "instruction": task, "mode": mode},
        response_parts=response_parts,
    )
    await ctx.append_and_broadcast(event_id, turn)
    await ctx.emit_pulse(event_id, [(f"agent:{agent_name}", "agent")])
    await ctx.record_event(
        EventType.BRAIN_AGENT_ROUTED,
        {"event_id": event_id, "agent": agent_name},
        narrative=f"Routed {event_id} to {agent_name}: {task[:80]}",
    )

    bb = ctx.get_blackboard()
    event = await bb.get_event(event_id)
    if event:
        svc_meta = await bb.get_service(event.service)
        await ctx.broadcast({
            "type": "attachment",
            "event_id": event_id,
            "actor": "brain",
            "filename": f"event-{event_id}.md",
            "content": event_to_markdown(event, svc_meta),
        })

    agent = ctx.get_agent_instance(agent_name)
    ws_mode = ctx.get_ws_mode()
    if agent or (ws_mode == "reverse" and agent_name not in ("_aligner", "_archivist_memory")):
        event_md_path = f"./events/event-{event_id}.md"
        await ctx.run_agent_task(
            event_id, agent_name, agent, task, event_md_path,
            routing_turn_num=turn.turn, mode=mode,
        )
    else:
        logger.error(f"Agent '{agent_name}' not found in agents dict")
        not_found_turn = ConversationTurn(
            turn=(await ctx.next_turn_number(event_id)),
            actor="brain",
            action="tool_result",
            thoughts="That agent is not available in this environment. "
                     "Review which agents are available and which has "
                     "the right expertise for this task.",
            response_parts=response_parts,
        )
        await ctx.append_and_broadcast(event_id, not_found_turn)
        await ctx.emit_pulse(event_id, [("tool:select_agent", "tool", 0.3)])
    return False


# ---------------------------------------------------------------------------
# message_agent
# ---------------------------------------------------------------------------
async def handle_message_agent(
    ctx: ToolContext, event_id: str, args: dict, response_parts: list[dict] | None,
) -> bool:
    agent_name = args.get("agent_id", "")
    message = args.get("message", "")

    if agent_name in ctx.ephemeral_only_roles:
        running_agent = ctx.get_active_agent_for_event(event_id)
        if running_agent != agent_name:
            logger.info(
                "message_agent: %s is ephemeral-only and not active on %s -- redirecting to select_agent",
                agent_name, event_id,
            )
            followup = ConversationTurn(
                turn=(await ctx.next_turn_number(event_id)),
                actor="brain",
                action="tool_result",
                thoughts=(
                    f"{agent_name} is an ephemeral-only agent (no persistent sidecar). "
                    f"Use select_agent to dispatch it -- this provisions an on-call pod. "
                    f"message_agent only works for agents that are already running."
                ),
                waitingFor="message_agent",
                response_parts=response_parts,
            )
            await ctx.append_and_broadcast(event_id, followup)
            return True

    turn = ConversationTurn(
        turn=(await ctx.next_turn_number(event_id)),
        actor="brain",
        action="message",
        thoughts=f"Message to {agent_name}: {message}",
        selectedAgents=[agent_name],
        waitingFor="message_agent",
    )
    await ctx.append_and_broadcast(event_id, turn)

    from ..dependencies import get_registry_and_bridge
    registry, _ = get_registry_and_bridge()

    running_agent = ctx.get_active_agent_for_event(event_id)
    event_has_active_task = ctx.is_task_running(event_id)

    if event_has_active_task and running_agent == agent_name:
        if registry:
            agent_conn = await registry.get_by_event(event_id)
            if not agent_conn:
                agent_conn = await registry.get_available(agent_name)
            if agent_conn and agent_conn.ws:
                try:
                    await agent_conn.ws.send_json({
                        "type": "proactive_message",
                        "from": "brain",
                        "content": message,
                        "event_id": event_id,
                    })
                    logger.info(f"Brain message_agent -> {agent_name} (busy, inbox, event={event_id}) ({len(message)} chars)")
                except Exception as e:
                    logger.warning(f"Failed to send message to {agent_name}: {e}")
                    await ctx.emit_pulse(event_id, [("tool:message_agent", "tool", 0.0)])
                    followup = ConversationTurn(
                        turn=(await ctx.next_turn_number(event_id)),
                        actor="brain",
                        action="tool_result",
                        thoughts="The message was not delivered. "
                                 "The agent may still be working -- check for recent updates "
                                 "from them before deciding next steps.",
                        waitingFor="message_agent",
                        response_parts=response_parts,
                    )
                    await ctx.append_and_broadcast(event_id, followup)
        return False

    agent_conn = await registry.get_available(agent_name) if registry else None

    if agent_conn:
        agent = ctx.get_agent_instance(agent_name)
        ws_mode = ctx.get_ws_mode()
        if agent or (ws_mode == "reverse" and agent_name not in ("_aligner", "_archivist_memory")):
            event_md_path = f"./events/event-{event_id}.md"
            await ctx.run_agent_task(
                event_id, agent_name, agent, message, event_md_path,
                routing_turn_num=turn.turn, mode="message",
                parallel=event_has_active_task,
            )
            label = "parallel" if event_has_active_task else "idle, dispatch"
            logger.info(f"Brain message_agent -> {agent_name} ({label}) ({len(message)} chars)")
        else:
            logger.warning(f"message_agent: no agent class for role {agent_name}")
            await ctx.emit_pulse(event_id, [("tool:message_agent", "tool", 0.3)])
    else:
        if registry:
            busy_conn = await registry.get_by_role(agent_name)
            if busy_conn and busy_conn.ws:
                try:
                    await busy_conn.ws.send_json({
                        "type": "proactive_message",
                        "from": "brain",
                        "content": message,
                        "event_id": event_id,
                    })
                    logger.info(f"Brain message_agent -> {agent_name} (busy fallback, inbox, event={event_id}) ({len(message)} chars)")
                except Exception as e:
                    logger.warning(f"Failed to send message to {agent_name}: {e}")
                    await ctx.emit_pulse(event_id, [("tool:message_agent", "tool", 0.0)])
                    followup = ConversationTurn(
                        turn=(await ctx.next_turn_number(event_id)),
                        actor="brain",
                        action="tool_result",
                        thoughts="The message was not delivered. "
                                 "The agent may still be working -- check for recent updates "
                                 "from them before deciding next steps.",
                        waitingFor="message_agent",
                        response_parts=response_parts,
                    )
                    await ctx.append_and_broadcast(event_id, followup)
            else:
                logger.warning(f"message_agent: no WS connection for {agent_name}, message dropped")
                await ctx.emit_pulse(event_id, [("tool:message_agent", "tool", 0.3)])
                followup = ConversationTurn(
                    turn=(await ctx.next_turn_number(event_id)),
                    actor="brain",
                    action="tool_result",
                    thoughts="The message was not delivered. "
                             "The agent may still be working -- check for recent updates "
                             "from them before deciding next steps.",
                    waitingFor="message_agent",
                    response_parts=response_parts,
                )
                await ctx.append_and_broadcast(event_id, followup)
    return False


# ---------------------------------------------------------------------------
# report_incident
# ---------------------------------------------------------------------------
async def handle_report_incident(
    ctx: ToolContext, event_id: str, args: dict, response_parts: list[dict] | None,
) -> bool:
    bb = ctx.get_blackboard()
    event_doc = await bb.get_event(event_id)
    if not event_doc:
        result_text = f"Event {event_id} not found. Cannot create incident."
        await ctx.emit_pulse(event_id, [("tool:report_incident", "tool", 0.3)])
        turn = ConversationTurn(
            turn=(await ctx.next_turn_number(event_id)),
            actor="brain", action="notify", thoughts=result_text,
            waitingFor="report_incident", response_parts=response_parts,
        )
        await ctx.append_and_broadcast(event_id, turn)
        return False
    if ctx.has_incident_been_created(event_id):
        result_text = f"Incident already created for event {event_id}. Skipping duplicate."
        turn = ConversationTurn(
            turn=(await ctx.next_turn_number(event_id)),
            actor="brain", action="notify", thoughts=result_text,
            waitingFor="report_incident", response_parts=response_parts,
        )
        await ctx.append_and_broadcast(event_id, turn)
        return True
    prior_incident = any(
        t.actor == "brain" and t.action == "notify"
        and ("Incident created" in (t.thoughts or "") or "Escalation staged [nightwatcher]" in (t.thoughts or ""))
        for t in (event_doc.conversation or [])
    )
    if prior_incident:
        ctx.mark_incident_created(event_id)
        result_text = f"Incident already created for event {event_id} (recovered from conversation history). Skipping duplicate."
        turn = ConversationTurn(
            turn=(await ctx.next_turn_number(event_id)),
            actor="brain", action="notify", thoughts=result_text,
            waitingFor="report_incident", response_parts=response_parts,
        )
        await ctx.append_and_broadcast(event_id, turn)
        return True
    automated_sources = ("headhunter", "timekeeper", "aligner")
    if event_doc.source not in automated_sources:
        result_text = (
            f"report_incident is only available for automated events "
            f"(source={event_doc.source} is not eligible)."
        )
    elif os.environ.get("NIGHTWATCHER_ENABLED", "false").lower() == "true":
        from ..models import StagedEscalation
        conv_turns = [
            t for t in (event_doc.conversation or [])
            if t.actor != "user" and t.action != "phase"
        ]
        summary_parts = [
            f"[{t.actor}.{t.action}] {(t.thoughts or '')[:150]}"
            for t in conv_turns[-3:]
        ]
        conversation_summary = " | ".join(summary_parts)[:500]
        slack_thread_url = ""
        if event_doc.slack_thread_ts and event_doc.slack_channel_id:
            ts_nodot = event_doc.slack_thread_ts.replace(".", "")
            workspace = os.environ.get("SLACK_WORKSPACE_DOMAIN", "app.slack.com/client")
            slack_thread_url = f"https://{workspace}/archives/{event_doc.slack_channel_id}/p{ts_nodot}"
        evidence = event_doc.event.evidence
        staged = StagedEscalation(
            event_id=event_id,
            service=event_doc.service,
            source=event_doc.source,
            reason=event_doc.event.reason,
            summary=args.get("summary", "")[:200],
            platform=args.get("platform", ""),
            priority=args.get("priority", "Normal"),
            description=args.get("description", ""),
            evidence_snapshot=evidence.model_dump() if hasattr(evidence, "model_dump") else {},
            conversation_summary=conversation_summary,
            slack_thread_url=slack_thread_url,
        )
        try:
            await bb.stage_escalation(staged)
            ctx.mark_incident_created(event_id)
            if event_doc.service:
                try:
                    await bb.set_escalation_flag(
                        event_doc.service, event_id,
                        args.get("summary", "escalated")[:100],
                    )
                except Exception as ef:
                    logger.warning(f"set_escalation_flag failed for {event_doc.service}: {ef}")
            result_text = (
                f"Escalation staged [nightwatcher] for consolidation "
                f"(event {event_id}, service {event_doc.service})"
            )
        except Exception as e:
            result_text = f"Failed to stage escalation: {e}"
            logger.warning(f"stage_escalation failed for {event_id}: {e}")
    else:
        adapter = ctx.get_smartsheet_incident_adapter()
        if not adapter:
            result_text = "Smartsheet incident tracking not configured (SMARTSHEET_INCIDENT_* env vars missing)."
        else:
            fields = {
                "Reporter e-mail": os.environ.get("SMARTSHEET_INCIDENT_REPORTER", ""),
                "Reporter Display Name": os.environ.get("SMARTSHEET_INCIDENT_REPORTER_NAME", "Darwin Brain"),
                "Date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                "Status": "New",
                "Issue Type": os.environ.get("SMARTSHEET_INCIDENT_ISSUE_TYPE", "Task"),
                "Labels": os.environ.get("SMARTSHEET_INCIDENT_LABELS", ""),
                "Components": os.environ.get("SMARTSHEET_INCIDENT_COMPONENTS", ""),
                "Platform": args.get("platform", ""),
                "Summary": args.get("summary", "")[:200],
                "Reason": args.get("description", ""),
                "Priority": args.get("priority", "Normal"),
                "Affected Versions": args.get("affected_versions", ""),
            }
            gl_ctx = None
            if event_doc.event and event_doc.event.evidence:
                gl_ctx = getattr(event_doc.event.evidence, "gitlab_context", None)
            if gl_ctx and isinstance(gl_ctx, dict):
                fields["Fix PR"] = gl_ctx.get("target_url", "") or gl_ctx.get("mr_url", "")
            if event_doc.slack_thread_ts and event_doc.slack_channel_id:
                ts_nodot = event_doc.slack_thread_ts.replace(".", "")
                workspace = os.environ.get("SLACK_WORKSPACE_DOMAIN", "app.slack.com/client")
                fields["Slack Thread"] = f"https://{workspace}/archives/{event_doc.slack_channel_id}/p{ts_nodot}"
            try:
                result = await adapter.create_incident(fields)
                ctx.mark_incident_created(event_id)
                if event_doc.service:
                    try:
                        await bb.set_escalation_flag(
                            event_doc.service, event_id,
                            args.get("summary", "escalated")[:100],
                        )
                    except Exception as ef:
                        logger.warning(f"set_escalation_flag failed for {event_doc.service}: {ef}")
                logger.info(f"Incident created for {event_id}")
                result_text = (
                    f"Incident created in Smartsheet (row {result['row_id']}). "
                    f"Sheet: {result['sheet_url']}"
                )
            except Exception as e:
                result_text = f"Failed to create incident: {e}"
                logger.warning(f"report_incident failed for {event_id}: {e}")
    turn = ConversationTurn(
        turn=(await ctx.next_turn_number(event_id)),
        actor="brain",
        action="notify",
        thoughts=result_text,
        waitingFor="report_incident",
        response_parts=response_parts,
    )
    await ctx.append_and_broadcast(event_id, turn)
    return True


# ---------------------------------------------------------------------------
# Registry registration
# ---------------------------------------------------------------------------
from .tool_router import HANDLER_REGISTRY

HANDLER_REGISTRY["reply_to_agent"] = handle_reply_to_agent
HANDLER_REGISTRY["select_agent"] = handle_select_agent
HANDLER_REGISTRY["ask_agent_for_state"] = handle_select_agent  # shared branch
HANDLER_REGISTRY["message_agent"] = handle_message_agent
HANDLER_REGISTRY["report_incident"] = handle_report_incident
