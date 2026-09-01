# BlackBoard/src/agents/agent_ws_handler.py
# @ai-rules:
# 1. [Pattern]: Register on connect, unregister on disconnect. Heartbeat ping every 30s;
#    close after 3 consecutive unanswered pings (missed-ping counter, not elapsed wall time).
# 2. [Pattern]: All sidecar messages routed to TaskBridge.put(task_id, msg). Bridge delivers to dispatch coroutine.
# 3. [Constraint]: Must be registered before entering message loop. 10s timeout on register message.
# 4. [Constraint]: This file handles transport only. No LLM logic, no dispatch decisions.
# 5. [Pattern]: Ephemeral agents registering for a closed/missing event are terminated immediately (orphan cleanup).
# 6. [Pattern]: wake_register creates queue SYNC (before next receive), then spawns Brain handler via on_wake callback.
#    Payload may include optional `mode` (default implement in Brain) — single source with sidecar synthetic task.
"""WebSocket handler for agent sidecar connections (reversed WS direction)."""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Callable, TYPE_CHECKING

from fastapi import WebSocket, WebSocketDisconnect

from .agent_registry import AgentRegistry
from .task_bridge import TaskBridge

if TYPE_CHECKING:
    from ..state.blackboard import BlackboardState

logger = logging.getLogger(__name__)

_ROUTED_TYPES = frozenset({
    "progress", "result", "error", "busy", "partial_result", "huddle_message",
    "agent_teammate_message",
})

# 3 consecutive unanswered pings (~90s at the 30s interval). A single delayed
# pong must not trip the watchdog; counting missed ping cycles (not elapsed
# wall time) keeps the close on the 30s grid regardless of RTT.
_PONG_MISS_THRESHOLD = 3


async def _heartbeat(
    ws: WebSocket,
    last_pong: list[float],
    missed_pings: list[int],
    agent_id: str,
    interval: int = 30,
) -> None:
    """Send ping every *interval* seconds. Runs as a background task.

    Closes after _PONG_MISS_THRESHOLD consecutive pings with no intervening
    pong. missed_pings is incremented after each successful ping and reset
    to 0 by the pong handler. last_pong is monotonic time of the last pong
    (or connect) -- used only to log elapsed time, not to decide close.
    """
    while True:
        await asyncio.sleep(interval)
        try:
            await ws.send_json({"type": "ping"})
        except Exception:
            logger.warning(
                "Heartbeat ping failed for agent %s; closing socket", agent_id,
            )
            try:
                await ws.close(code=1001, reason="Heartbeat ping failed")
            except Exception:
                pass
            break
        missed_pings[0] += 1
        if missed_pings[0] >= _PONG_MISS_THRESHOLD:
            elapsed = time.monotonic() - last_pong[0]
            logger.warning(
                "Pong deadline exceeded for agent %s: %.1fs since last pong "
                "(%d missed ping cycles)",
                agent_id, elapsed, missed_pings[0],
            )
            try:
                await ws.close(code=1001, reason="Pong deadline exceeded")
            except Exception:
                pass
            break


async def agent_websocket_handler(
    websocket: WebSocket,
    registry: AgentRegistry,
    bridge: TaskBridge,
    blackboard: "BlackboardState | None" = None,
    on_wake: Callable | None = None,
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
        is_ephemeral = raw.get("ephemeral", False)
        event_id = raw.get("event_id")

        await registry.register(
            agent_id, raw.get("role", "unknown"), websocket,
            raw.get("capabilities", []), raw.get("cli", ""), raw.get("model", ""),
            ephemeral=is_ephemeral,
            event_id=event_id,
        )
        last_pong = [time.monotonic()]
        missed_pings = [0]

        if is_ephemeral and event_id and blackboard and not event_id.startswith("nw-sweep-"):
            event = await blackboard.get_event(event_id)
            if not event or event.status.value == "closed":
                logger.info("Terminating orphan ephemeral agent %s: event %s is %s",
                            agent_id, event_id, event.status.value if event else "missing")
                await websocket.send_json({"type": "terminate", "event_id": event_id, "reason": "Event closed"})
                await websocket.close(code=1000, reason=f"Event {event_id} no longer active")
                return

        heartbeat_task = asyncio.create_task(
            _heartbeat(websocket, last_pong, missed_pings, agent_id),
        )

        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type", "")
            if msg_type in _ROUTED_TYPES:
                bridge.put(data.get("task_id", ""), data)
            elif msg_type == "pong":
                logger.debug("Heartbeat pong from %s", agent_id)
                last_pong[0] = time.monotonic()
                missed_pings[0] = 0
            elif msg_type == "wake_register":
                wake_task_id = data.get("task_id", "")
                bridge.create_queue(wake_task_id)
                await registry.mark_busy(
                    agent_id, data.get("event_id", ""), wake_task_id,
                    role=data.get("role", ""),
                )
                if on_wake:
                    t = asyncio.create_task(on_wake(data, agent_id))
                    t.add_done_callback(
                        lambda fut: logger.exception(
                            "Wake handler failed", exc_info=fut.exception(),
                        ) if fut.exception() else None
                    )
                logger.info("Wake registered: task=%s event=%s agent=%s",
                            wake_task_id, data.get("event_id", ""), agent_id)
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
