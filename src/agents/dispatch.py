# BlackBoard/src/agents/dispatch.py
# @ai-rules:
# 1. [Constraint]: Security check (FORBIDDEN_PATTERNS) is the FIRST thing -- before any WS send. Single enforcement point.
# 2. [Pattern]: Queue loop reads progress/partial_result/huddle_message/result/error/_error_sentinel from TaskBridge.
# 3. [Pattern]: agent_id parameter enables session affinity (follow-up rounds route to same agent).
# 4. [Pattern]: Retryable errors return ("__RETRYABLE__", None) sentinel. Caller (Brain) defers the event.
# 5. [Constraint]: mark_idle + delete_queue in finally block -- always cleans up regardless of exit path.
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

AGENT_VOLUME_PATHS = {
    "architect": "/data/gitops-architect",
    "sysadmin": "/data/gitops-sysadmin",
    "developer": "/data/gitops-developer",
    "qe": "/data/gitops-qe",
}


def _build_prompt(task: str, event_md_path: str) -> str:
    if event_md_path:
        return (
            f"Read the event document at {event_md_path} for full context, "
            f"then execute the following task:\n\n{task}"
        )
    return task


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
    else:
        agent_conn = await registry.get_available(role)

    if not agent_conn:
        return f"Error: No available agent for role {role}", None

    task_id = str(uuid.uuid4())
    queue = bridge.create_queue(task_id)

    try:
        await agent_conn.ws.send_json({
            "type": "task",
            "task_id": task_id,
            "event_id": event_id,
            "prompt": prompt,
            "cwd": cwd or AGENT_VOLUME_PATHS.get(role, "/data/gitops"),
            "autoApprove": True,
            "session_id": session_id,
        })
        await registry.mark_busy(agent_conn.agent_id, event_id, task_id)

        latest_callback_result: str | None = None
        returned_session_id = session_id

        while True:
            msg = await queue.get()
            msg_type = msg.get("type", "")

            if msg_type == "progress":
                if on_progress:
                    await on_progress({
                        "actor": role,
                        "event_id": event_id,
                        "message": msg.get("message", ""),
                        "source": msg.get("source", ""),
                    })

            elif msg_type == "partial_result":
                latest_callback_result = msg.get("content", "")
                if on_progress:
                    await on_progress({
                        "actor": role,
                        "event_id": event_id,
                        "message": f"[deliverable updated: {len(latest_callback_result)} chars]",
                        "source": "callback",
                    })

            elif msg_type == "huddle_message":
                if on_huddle:
                    await on_huddle({
                        "agent_id": agent_conn.agent_id,
                        "task_id": task_id,
                        "event_id": event_id,
                        "content": msg.get("content", ""),
                    })

            elif msg_type == "result":
                output = msg.get("output", "")
                source = msg.get("source", "stdout")
                if isinstance(output, dict):
                    output = json.dumps(output, indent=2)
                if latest_callback_result and source == "stdout":
                    output = latest_callback_result
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
        await registry.mark_idle(agent_conn.agent_id)
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
