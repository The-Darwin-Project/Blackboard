# BlackBoard/src/agents/dispatch.py
# @ai-rules:
# 1. [Constraint]: Security check (FORBIDDEN_PATTERNS) is the FIRST thing -- before any WS send. Single enforcement point.
# 2. [Pattern]: Queue loop reads progress/partial_result/huddle_message/result/error/_error_sentinel from TaskBridge.
# 3. [Pattern]: agent_id parameter enables session affinity (follow-up rounds route to same agent).
# 4. [Pattern]: Retryable errors return ("__RETRYABLE__", None) sentinel. Caller (Brain) defers the event.
# 5. [Constraint]: finally block: mark_idle only if sidecar accepted the task (accepted flag).
#    If rejected, restore previous agent state. delete_queue always runs.
# 6. [Pattern]: consume_wake_task mirrors the receive loop but skips queue creation + task send. Queue pre-created by WS handler.
"""Unified dispatch -- sends tasks to agent sidecars via persistent WebSocket."""
from __future__ import annotations

import asyncio
import json
import logging
import re
import uuid
from typing import Callable

from .agent_registry import AgentRegistry
from .task_bridge import TaskBridge, ERROR_SENTINEL_TYPE
from .security import FORBIDDEN_PATTERNS, SecurityError

logger = logging.getLogger(__name__)

RETRYABLE_SENTINEL = "__RETRYABLE__"

_TOOL_MARKER_RE = re.compile(r'\[tool\]\s*\S+', re.IGNORECASE)


def _sanitize_stdout(raw: str) -> str:
    """Strip CLI tool markers from raw stdout used as fallback agent result.

    When an agent exits without calling team_send_results, the raw stdout
    contains interleaved [tool] markers that confuse the Brain's LLM.
    """
    cleaned = _TOOL_MARKER_RE.sub('', raw)
    cleaned = re.sub(r'\n{3,}', '\n\n', cleaned).strip()
    if not cleaned or len(cleaned) < 20:
        return "(Agent completed but did not send a structured report. Raw output was tool execution logs.)"
    return cleaned

AGENT_VOLUME_PATHS = {
    "architect": "/data/gitops-architect",
    "sysadmin": "/data/gitops-sysadmin",
    "developer": "/data/gitops-developer",
    "qe": "/data/gitops-qe",
}


def _build_prompt(task: str, event_md_path: str) -> str:
    parts = []
    if event_md_path:
        parts.append(f"Read the event document at {event_md_path} for full context.")
        parts.append(
            "Use bb_catch_up to read the blackboard for plan steps and progress. "
            "Use bb_update_plan_step to mark steps as in_progress or completed."
        )
    parts.append(f"Execute the following task:\n\n{task}")
    return " ".join(parts) if event_md_path else task


def _check_security(prompt: str) -> None:
    for pattern in FORBIDDEN_PATTERNS:
        if re.search(pattern, prompt, re.IGNORECASE):
            raise SecurityError(f"Blocked forbidden pattern: {pattern}")


async def dispatch_to_agent(
    registry: AgentRegistry,
    bridge: TaskBridge,
    role: str,
    event_id: str,
    task: str,
    on_progress: Callable | None = None,
    on_huddle: Callable | None = None,
    agent_id: str | None = None,
    session_id: str | None = None,
    event_md_path: str = "",
    cwd: str = "",
) -> tuple[str, str | None]:
    """Send task to an available agent via persistent WS, return (result, session_id)."""
    prompt = _build_prompt(task, event_md_path)
    _check_security(prompt)

    # --- Resolve agent (session affinity or role-based) ---
    if agent_id:
        agent_conn = await registry.get_by_id(agent_id)
        if agent_conn and agent_conn.busy:
            logger.warning(
                "dispatch_to_agent: agent %s is busy (task=%s) but dispatching via agent_id override",
                agent_id, agent_conn.current_task_id,
            )
    else:
        agent_conn = await registry.get_available(role)

    if not agent_conn:
        return f"Error: No available agent for role {role}", None

    task_id = str(uuid.uuid4())
    queue = bridge.create_queue(task_id)

    prev_busy = agent_conn.busy
    prev_event_id = agent_conn.current_event_id
    prev_task_id = agent_conn.current_task_id
    prev_role = agent_conn.current_role
    accepted = False

    try:
        await agent_conn.ws.send_json({
            "type": "task",
            "task_id": task_id,
            "event_id": event_id,
            "role": role,
            "prompt": prompt,
            "cwd": cwd or AGENT_VOLUME_PATHS.get(role, "/data/gitops"),
            "autoApprove": True,
            "session_id": session_id,
        })
        await registry.mark_busy(agent_conn.agent_id, event_id, task_id, role=role)

        latest_callback_result: str | None = None
        returned_session_id = session_id

        while True:
            msg = await queue.get()
            msg_type = msg.get("type", "")

            if msg_type == "progress":
                accepted = True
                if on_progress:
                    await on_progress({
                        "actor": role,
                        "event_id": event_id,
                        "message": msg.get("message", ""),
                        "source": msg.get("source", ""),
                    })

            elif msg_type == "partial_result":
                accepted = True
                latest_callback_result = msg.get("content", "")
                if on_progress:
                    await on_progress({
                        "actor": role,
                        "event_id": event_id,
                        "message": f"[deliverable updated: {len(latest_callback_result)} chars]",
                        "source": "callback",
                    })

            elif msg_type == "huddle_message":
                accepted = True
                if on_huddle:
                    await on_huddle({
                        "agent_id": agent_conn.agent_id,
                        "task_id": task_id,
                        "event_id": event_id,
                        "content": msg.get("content", ""),
                    })

            elif msg_type == "result":
                accepted = True
                output = msg.get("output", "")
                source = msg.get("source", "stdout")
                if isinstance(output, dict):
                    output = json.dumps(output, indent=2)
                if latest_callback_result and source == "stdout":
                    output = latest_callback_result
                elif source == "stdout" and not latest_callback_result:
                    output = _sanitize_stdout(str(output))
                returned_session_id = msg.get("session_id") or returned_session_id
                return str(output), returned_session_id

            elif msg_type == "error":
                error_msg = msg.get("error", msg.get("message", "Unknown error"))
                if msg.get("retryable"):
                    logger.warning("Retryable error from %s [%s]: %s", role, event_id, error_msg)
                    return RETRYABLE_SENTINEL, None
                return f"Error: {error_msg}", returned_session_id

            elif msg_type == ERROR_SENTINEL_TYPE:
                return f"Error: {msg.get('message', 'Agent disconnected')}", returned_session_id

    finally:
        if accepted:
            await registry.mark_idle(agent_conn.agent_id)
        elif prev_busy:
            await registry.mark_busy(
                agent_conn.agent_id, prev_event_id, prev_task_id, role=prev_role
            )
            logger.debug(
                "Dispatch rejected, restored previous state for %s (task=%s)",
                agent_conn.agent_id, prev_task_id,
            )
        else:
            await registry.mark_idle(agent_conn.agent_id)
        bridge.delete_queue(task_id)


async def consume_wake_task(
    bridge: TaskBridge,
    registry: AgentRegistry,
    agent_id: str,
    task_id: str,
    event_id: str,
    role: str,
    on_progress: Callable | None = None,
    on_huddle: Callable | None = None,
) -> tuple[str, str | None]:
    """Consume a self-initiated wake task's messages from a pre-created TaskBridge queue.

    Unlike dispatch_to_agent, this does NOT create the queue (WS handler did it
    synchronously) and does NOT send a task message (sidecar already started).
    """
    queue = bridge.get_queue(task_id)
    if not queue:
        return "Error: Wake task queue not found", None

    try:
        latest_callback_result: str | None = None
        returned_session_id: str | None = None

        while True:
            msg = await queue.get()
            msg_type = msg.get("type", "")

            if msg_type == "progress":
                if on_progress:
                    await on_progress({
                        "actor": role, "event_id": event_id,
                        "message": msg.get("message", ""),
                        "source": msg.get("source", ""),
                    })

            elif msg_type == "partial_result":
                latest_callback_result = msg.get("content", "")
                if on_progress:
                    await on_progress({
                        "actor": role, "event_id": event_id,
                        "message": f"[deliverable updated: {len(latest_callback_result)} chars]",
                        "source": "callback",
                    })

            elif msg_type == "huddle_message":
                if on_huddle:
                    await on_huddle({
                        "agent_id": agent_id, "task_id": task_id,
                        "event_id": event_id,
                        "content": msg.get("content", ""),
                    })

            elif msg_type == "agent_teammate_message":
                if on_progress:
                    await on_progress({
                        "actor": msg.get("from", role), "event_id": event_id,
                        "message": msg.get("content", ""),
                        "source": "teammate",
                    })

            elif msg_type == "result":
                output = msg.get("output", "")
                source = msg.get("source", "stdout")
                if isinstance(output, dict):
                    output = json.dumps(output, indent=2)
                if latest_callback_result and source == "stdout":
                    output = latest_callback_result
                elif source == "stdout" and not latest_callback_result:
                    output = _sanitize_stdout(str(output))
                returned_session_id = msg.get("session_id") or returned_session_id
                return str(output), returned_session_id

            elif msg_type == "error":
                error_msg = msg.get("error", msg.get("message", "Unknown error"))
                if msg.get("retryable"):
                    logger.warning("Retryable wake error from %s [%s]: %s", role, event_id, error_msg)
                    return RETRYABLE_SENTINEL, None
                return f"Error: {error_msg}", returned_session_id

            elif msg_type == ERROR_SENTINEL_TYPE:
                return f"Error: {msg.get('message', 'Agent disconnected')}", returned_session_id

    finally:
        await registry.mark_idle(agent_id)
        bridge.delete_queue(task_id)


async def send_cancel(registry: AgentRegistry, bridge: TaskBridge, event_id: str) -> None:
    """Send cancel to the agent working on *event_id*. Fallback: inject error sentinel."""
    agent = await registry.get_by_event(event_id)
    if not agent or not agent.current_task_id:
        return
    task_id = agent.current_task_id
    try:
        await agent.ws.send_json({"type": "cancel", "task_id": task_id})
        # Wait up to 5s for sidecar to respond (queue deleted = dispatch unblocked)
        for _ in range(50):
            if not bridge.get_queue(task_id):
                return  # sidecar responded, queue already consumed
            await asyncio.sleep(0.1)
        # Sidecar didn't respond in 5s -- force unblock
        bridge.put_error(task_id, "Cancel timeout -- forced")
    except Exception:
        bridge.put_error(task_id, "Cancel send failed")
