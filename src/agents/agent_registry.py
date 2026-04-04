# BlackBoard/src/agents/agent_registry.py
# @ai-rules:
# 1. [Pattern]: All mutations guarded by asyncio.Lock.
# 2. [Pattern]: Evict-on-reconnect by role + agent_id prefix match.
# 3. [Pattern]: _on_task_orphaned callback wired by TaskBridge for error sentinel injection on disconnect.
# 4. [Constraint]: Pure infrastructure. No LLM logic, no routing decisions.
"""Agent Registry -- manages a dynamic pool of connected agent sidecars."""
from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from typing import Callable

from fastapi import WebSocket

logger = logging.getLogger(__name__)


@dataclass
class AgentConnection:
    """A single live sidecar or ephemeral agent WebSocket connection."""

    agent_id: str
    role: str
    capabilities: list[str]
    cli: str
    model: str
    ws: WebSocket
    connected_at: float
    busy: bool = False
    current_event_id: str | None = None
    current_task_id: str | None = None
    ephemeral: bool = False
    bound_event_id: str | None = None
    current_role: str | None = None


class AgentRegistry:
    """Thread-safe registry of live agent sidecar WebSocket connections."""

    def __init__(self) -> None:
        self._agents: dict[str, AgentConnection] = {}
        self._lock = asyncio.Lock()
        self._on_task_orphaned: Callable[[str], None] | None = None
        self._on_ephemeral_registered: Callable[[str], None] | None = None

    def set_task_orphaned_callback(self, cb: Callable[[str], None]) -> None:
        self._on_task_orphaned = cb

    def set_ephemeral_registered_callback(self, cb: Callable[[str], None]) -> None:
        self._on_ephemeral_registered = cb

    async def register(
        self,
        agent_id: str,
        role: str,
        ws: WebSocket,
        capabilities: list[str],
        cli: str,
        model: str,
        ephemeral: bool = False,
        event_id: str | None = None,
    ) -> None:
        async with self._lock:
            if not ephemeral:
                prefix = agent_id.rsplit("-", 1)[0]
                stale = [
                    aid for aid, conn in self._agents.items()
                    if conn.role == role
                    and not conn.ephemeral
                    and aid.rsplit("-", 1)[0] == prefix
                    and aid != agent_id
                ]
                for aid in stale:
                    old = self._agents.pop(aid)
                    try:
                        await old.ws.close()
                    except Exception:
                        pass
                    logger.info("Evicted stale agent %s (replaced by %s)", aid, agent_id)

            self._agents[agent_id] = AgentConnection(
                agent_id=agent_id,
                role=role,
                capabilities=capabilities,
                cli=cli,
                model=model,
                ws=ws,
                connected_at=time.time(),
                ephemeral=ephemeral,
                bound_event_id=event_id,
            )
            logger.info(
                "Registered agent %s (role=%s, cli=%s, model=%s, ephemeral=%s, event=%s)",
                agent_id, role, cli, model, ephemeral, event_id,
            )

        if ephemeral and event_id and self._on_ephemeral_registered:
            self._on_ephemeral_registered(event_id)

    async def unregister(self, agent_id: str) -> None:
        async with self._lock:
            conn = self._agents.pop(agent_id, None)
            if not conn:
                return
            if conn.current_task_id and self._on_task_orphaned:
                self._on_task_orphaned(conn.current_task_id)
            if conn.ephemeral:
                logger.info("Unregistered ephemeral agent %s (event=%s)", agent_id, conn.bound_event_id)
            else:
                logger.info("Unregistered agent %s (role=%s)", agent_id, conn.role)

    async def get_available(self, role: str) -> AgentConnection | None:
        async with self._lock:
            for conn in self._agents.values():
                if conn.role == role and not conn.busy:
                    logger.debug("Found idle agent %s for role=%s", conn.agent_id, role)
                    return conn
            logger.debug("No idle agent for role=%s", role)
            return None

    async def get_by_role(self, role: str) -> AgentConnection | None:
        """Find any agent matching a role, regardless of busy state."""
        async with self._lock:
            for conn in self._agents.values():
                if conn.role == role:
                    return conn
            return None

    async def get_by_id(self, agent_id: str) -> AgentConnection | None:
        """Look up an agent by exact agent_id. For session affinity (follow-up rounds)."""
        async with self._lock:
            return self._agents.get(agent_id)

    async def get_by_event(self, event_id: str) -> AgentConnection | None:
        async with self._lock:
            for conn in self._agents.values():
                if conn.current_event_id == event_id:
                    return conn
            return None

    async def get_ephemeral(self, event_id: str) -> AgentConnection | None:
        """Find the ephemeral agent bound to a specific event."""
        async with self._lock:
            for conn in self._agents.values():
                if conn.ephemeral and conn.bound_event_id == event_id:
                    return conn
            return None

    async def mark_busy(self, agent_id: str, event_id: str, task_id: str, role: str | None = None) -> None:
        async with self._lock:
            conn = self._agents.get(agent_id)
            if not conn:
                return
            conn.busy = True
            conn.current_event_id = event_id
            conn.current_task_id = task_id
            if role:
                conn.current_role = role
            logger.debug("Marked agent %s busy (event=%s, task=%s, role=%s)", agent_id, event_id, task_id, role)

    async def mark_idle(self, agent_id: str) -> None:
        async with self._lock:
            conn = self._agents.get(agent_id)
            if not conn:
                return
            conn.busy = False
            conn.current_event_id = None
            conn.current_task_id = None
            conn.current_role = None
            logger.debug("Marked agent %s idle", agent_id)

    async def list_agents(self) -> list[dict]:
        async with self._lock:
            return [
                {
                    "agent_id": c.agent_id,
                    "role": c.role,
                    "busy": c.busy,
                    "current_event_id": c.current_event_id,
                    "current_task_id": c.current_task_id,
                    "connected_at": c.connected_at,
                    "cli": c.cli,
                    "model": c.model,
                    "ephemeral": c.ephemeral,
                    "bound_event_id": c.bound_event_id,
                    "current_role": c.current_role,
                }
                for c in self._agents.values()
            ]
