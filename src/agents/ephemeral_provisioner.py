# BlackBoard/src/agents/ephemeral_provisioner.py
# @ai-rules:
# 1. [Pattern]: Provisions ephemeral agents via Tekton EventListener webhook. Pure plumbing.
# 2. [Pattern]: Per-source maxActive from env var convention: {SOURCE}_MAX_ACTIVE.
# 3. [Pattern]: asyncio.Event for registration wait -- set by registry callback, no polling.
# 4. [Constraint]: Headhunter events NEVER fall back to local sidecars. They defer and wait.
# 5. [Constraint]: One agent per event. Role switching handled by WS msg.role, not new containers.
"""Ephemeral agent provisioner -- spawns on-call agents via Tekton TaskRun."""
from __future__ import annotations

import asyncio
import logging
import os
from typing import TYPE_CHECKING

import httpx

if TYPE_CHECKING:
    from .agent_registry import AgentConnection, AgentRegistry

logger = logging.getLogger(__name__)

CAPACITY_SENTINEL = "__EPHEMERAL_CAPACITY__"
INFRA_SENTINEL = "__EPHEMERAL_INFRA_FAIL__"


MAX_INFRA_FAILURES = 2


class EphemeralProvisioner:
    """Provisions ephemeral agents via Tekton EventListener webhook.

    The Brain calls ``ensure_agent(event_id, source)`` before dispatching
    to an agent for trigger-source events (headhunter, etc.).  If an
    ephemeral agent is already running for the event, it is returned
    immediately.  Otherwise a Tekton TaskRun is spawned and the method
    blocks until the agent connects and registers via WebSocket.

    Capacity is controlled per-source via ``{SOURCE}_MAX_ACTIVE`` env vars
    (e.g., ``HEADHUNTER_MAX_ACTIVE=3``).  The limit is read from the
    trigger agent's own Helm values section -- no duplication.
    """

    def __init__(self, registry: AgentRegistry, event_listener_url: str) -> None:
        self._registry = registry
        self._url = event_listener_url
        self._pending: dict[str, asyncio.Event] = {}
        self._active_sources: dict[str, str] = {}
        self._infra_failures: dict[str, int] = {}

    def get_source_limit(self, source: str) -> int:
        env_key = f"{source.upper().replace('-', '_')}_MAX_ACTIVE"
        return int(os.environ.get(env_key, "1"))

    async def ensure_agent(self, event_id: str, source: str) -> "AgentConnection | str":
        """Ensure an ephemeral agent exists for this event. Spawn if needed.

        Returns ``AgentConnection`` on success, or a sentinel string:
        - ``CAPACITY_SENTINEL``: source maxActive reached, caller should defer
        - ``INFRA_SENTINEL``: Tekton unreachable, caller should defer
        """
        existing = await self._registry.get_ephemeral(event_id)
        if existing:
            return existing

        self._active_sources = {
            eid: src for eid, src in self._active_sources.items()
            if await self._registry.get_ephemeral(eid) is not None
        }

        limit = self.get_source_limit(source)
        source_count = sum(1 for s in self._active_sources.values() if s == source)
        if source_count >= limit:
            logger.info(
                "Ephemeral limit for '%s' reached (%d/%d). Event %s stays queued.",
                source, source_count, limit, event_id,
            )
            return CAPACITY_SENTINEL

        failures = self._infra_failures.get(event_id, 0)
        if failures >= MAX_INFRA_FAILURES:
            logger.warning(
                "Ephemeral circuit breaker for %s: %d consecutive failures. Falling back to sidecar.",
                event_id, failures,
            )
            self._infra_failures.pop(event_id, None)
            return None

        try:
            await self._trigger_taskrun(event_id)
            agent = await self._wait_for_registration(event_id, timeout=90)
            self._active_sources[event_id] = source
            self._infra_failures.pop(event_id, None)
            return agent
        except (httpx.ConnectError, httpx.TimeoutException, asyncio.TimeoutError) as exc:
            self._infra_failures[event_id] = failures + 1
            logger.warning(
                "Ephemeral dispatch failed for %s (%d/%d): %s. Event stays queued.",
                event_id, failures + 1, MAX_INFRA_FAILURES, exc or "handshake timeout",
            )
            return INFRA_SENTINEL

    def on_ephemeral_registered(self, event_id: str) -> None:
        """Called by registry.register() when an ephemeral agent registers."""
        evt = self._pending.get(event_id)
        if evt:
            evt.set()

    async def terminate_agent(self, event_id: str) -> None:
        """Send terminate signal to ephemeral agent on event close."""
        agent = await self._registry.get_ephemeral(event_id)
        if agent and agent.ephemeral:
            try:
                await agent.ws.send_json({"type": "terminate", "event_id": event_id})
                logger.info("Sent terminate to ephemeral agent for %s", event_id)
            except Exception:
                logger.debug("Failed to send terminate for %s (already disconnected?)", event_id)
        self._active_sources.pop(event_id, None)
        self._infra_failures.pop(event_id, None)

    async def _trigger_taskrun(self, event_id: str) -> None:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(self._url, json={"event_id": event_id})
            resp.raise_for_status()
            logger.info("Triggered TaskRun for %s (status=%d)", event_id, resp.status_code)

    async def _wait_for_registration(
        self, event_id: str, timeout: float = 90,
    ) -> "AgentConnection":
        evt = asyncio.Event()
        self._pending[event_id] = evt
        try:
            await asyncio.wait_for(evt.wait(), timeout=timeout)
            agent = await self._registry.get_ephemeral(event_id)
            if not agent:
                raise asyncio.TimeoutError("Agent registered but not found in registry")
            return agent
        finally:
            self._pending.pop(event_id, None)
