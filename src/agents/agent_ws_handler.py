# BlackBoard/src/agents/agent_ws_handler.py
# @ai-rules:
# 1. [Pattern]: Register on connect, unregister on disconnect. Heartbeat ping every 30s.
# 2. [Pattern]: All sidecar messages routed to TaskBridge.put(task_id, msg). Bridge delivers to dispatch coroutine.
# 3. [Constraint]: Must be registered before entering message loop. 10s timeout on register message.
# 4. [Constraint]: This file handles transport only. No LLM logic, no dispatch decisions.
"""WebSocket handler for agent sidecar connections (reversed WS direction)."""
from __future__ import annotations

import asyncio
import logging

from fastapi import WebSocket, WebSocketDisconnect

from .agent_registry import AgentRegistry
from .task_bridge import TaskBridge

logger = logging.getLogger(__name__)

_ROUTED_TYPES = frozenset({
    "progress", "result", "error", "partial_result", "huddle_message",
})


async def _heartbeat(ws: WebSocket, interval: int = 30) -> None:
    """Send ping every *interval* seconds. Runs as a background task."""
    while True:
        await asyncio.sleep(interval)
        try:
            await ws.send_json({"type": "ping"})
        except Exception:
            break


async def agent_websocket_handler(
    websocket: WebSocket,
    registry: AgentRegistry,
    bridge: TaskBridge,
) -> None:
    """Handle a single agent sidecar WebSocket lifecycle."""
    await websocket.accept()
    agent_id: str | None = None
    heartbeat_task: asyncio.Task | None = None

    try:
        raw = await asyncio.wait_for(websocket.receive_json(), timeout=10.0)
        if raw.get("type") != "register" or not raw.get("agent_id"):
            await websocket.close(code=1008, reason="Expected register message")
            return

        agent_id = raw["agent_id"]
        await registry.register(
            agent_id, raw.get("role", "unknown"), websocket,
            raw.get("capabilities", []), raw.get("cli", ""), raw.get("model", ""),
        )

        heartbeat_task = asyncio.create_task(_heartbeat(websocket))

        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type", "")
            if msg_type in _ROUTED_TYPES:
                bridge.put(data.get("task_id", ""), data)
            elif msg_type == "pong":
                logger.debug("Heartbeat pong from %s", agent_id)
            else:
                logger.warning("Unknown message type '%s' from %s", msg_type, agent_id)

    except asyncio.TimeoutError:
        logger.warning("Agent registration timed out")
        await websocket.close(code=1008, reason="Register timeout")
    except WebSocketDisconnect:
        logger.info("Agent %s disconnected", agent_id or "unknown")
    except Exception:
        logger.exception("Agent WS error (agent=%s)", agent_id or "unknown")
    finally:
        if heartbeat_task:
            heartbeat_task.cancel()
        if agent_id:
            await registry.unregister(agent_id)
