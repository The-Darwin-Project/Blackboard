# BlackBoard/src/agents/ephemeral_provisioner.py
# @ai-rules:
# 1. [Pattern]: Pure plumbing -- spawns/terminates ephemeral agents via Tekton EventListener webhook.
# 2. [Pattern]: asyncio.Event for registration wait -- set by registry callback, no polling.
# 3. [Constraint]: NO capacity logic here. Per-source WIP gating lives in Brain (event-based, not agent-based).
# 4. [Constraint]: One agent per event. Role switching handled by WS msg.role, not new containers.
# 5. [Pattern]: Circuit breaker: MAX_INFRA_FAILURES consecutive Tekton failures -> fall back to sidecar (returns None).
"""Ephemeral agent provisioner -- spawns on-call agents via Tekton TaskRun."""
from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

import httpx

if TYPE_CHECKING:
    from .agent_registry import AgentConnection, AgentRegistry

logger = logging.getLogger(__name__)

INFRA_SENTINEL = "__EPHEMERAL_INFRA_FAIL__"

MAX_INFRA_FAILURES = 2


class EphemeralProvisioner:
    """Provisions ephemeral agents via Tekton EventListener webhook.

    Pure plumbing: spawn an agent for an event, terminate on close.
    Capacity control (per-source WIP limits) lives in the Brain --
    it gates at the event level (NEW -> ACTIVE transition), not
    at the agent level.  By the time ``ensure_agent`` is called the
    Brain has already admitted the event.
    """

    def __init__(self, registry: AgentRegistry, event_listener_url: str) -> None:
        self._registry = registry
        self._url = event_listener_url
        self._pending: dict[str, asyncio.Event] = {}
        self._infra_failures: dict[str, int] = {}

    async def ensure_agent(self, event_id: str) -> "AgentConnection | str | None":
        """Ensure an ephemeral agent exists for this event. Spawn if needed.

        Returns ``AgentConnection`` on success, or:
        - ``INFRA_SENTINEL``: Tekton unreachable, caller should defer
        - ``None``: circuit breaker tripped, caller should fall back to sidecar
        """
        existing = await self._registry.get_ephemeral(event_id)
        if existing:
            return existing

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
            agent = await self._wait_for_registration(event_id, timeout=180)
            self._infra_failures.pop(event_id, None)
            return agent
        except (httpx.ConnectError, httpx.TimeoutException, asyncio.TimeoutError) as exc:
            logger.warning(
                "Ephemeral dispatch failed for %s (%d/%d): %s. Cleaning up and retrying.",
                event_id, failures + 1, MAX_INFRA_FAILURES, exc or "handshake timeout",
            )
            await self._cancel_taskrun(event_id)
            await asyncio.sleep(5)

            try:
                await self._trigger_taskrun(event_id)
                agent = await self._wait_for_registration(event_id, timeout=180)
                self._infra_failures.pop(event_id, None)
                logger.info("Ephemeral retry succeeded for %s after cleanup", event_id)
                return agent
            except (httpx.ConnectError, httpx.TimeoutException, asyncio.TimeoutError) as retry_exc:
                self._infra_failures[event_id] = failures + 1
                logger.warning(
                    "Ephemeral retry also failed for %s (%d/%d): %s.",
                    event_id, failures + 1, MAX_INFRA_FAILURES, retry_exc or "handshake timeout",
                )
                await self._cancel_taskrun(event_id)
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
        self._infra_failures.pop(event_id, None)

    async def _trigger_taskrun(self, event_id: str) -> None:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(self._url, json={"event_id": event_id, "action": "spawn"})
            resp.raise_for_status()
            logger.info("Triggered TaskRun for %s (status=%d)", event_id, resp.status_code)

    async def _cancel_taskrun(self, event_id: str) -> None:
        """Trigger prune TaskRun to delete stuck TaskRuns for this event."""
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(self._url, json={"event_id": event_id, "action": "cancel"})
                resp.raise_for_status()
                logger.info("Triggered prune TaskRun for %s (status=%d)", event_id, resp.status_code)
        except Exception as exc:
            logger.warning("Failed to trigger prune for %s: %s", event_id, exc)

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
