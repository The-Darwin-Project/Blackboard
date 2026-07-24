# BlackBoard/src/agents/ephemeral_provisioner.py
# @ai-rules:
# 1. [Pattern]: Pure plumbing -- spawns/terminates ephemeral agents via Tekton EventListener webhook.
# 2. [Pattern]: Hybrid wait_for loop with injected SpawnHealthPort for pod-aware spawn tracking.
# 3. [Constraint]: NO capacity logic here. Per-source WIP gating lives in Brain (event-based, not agent-based).
# 4. [Constraint]: One agent per event. Role switching handled by WS msg.role, not new containers.
# 5. [Pattern]: Circuit breaker: MAX_INFRA_FAILURES consecutive Tekton failures -> fall back to sidecar (returns None).
#    SpawnFailed (terminal pod) follows the same retry-once-then-sentinel path as timeout.
# 6. [Gotcha]: `model` is only added to the POST body when non-empty (`if model: payload["model"] = model`).
#    An empty string in the body would override the TriggerTemplate's Helm-configured default.
"""Ephemeral agent provisioner -- spawns on-call agents via Tekton TaskRun."""
from __future__ import annotations

import asyncio
import logging
import time
from typing import TYPE_CHECKING, Protocol, runtime_checkable

import httpx

from src.observers.k8s_constants import SpawnStatus, SpawnPollResult

if TYPE_CHECKING:
    from .agent_registry import AgentConnection, AgentRegistry


@runtime_checkable
class SpawnHealthPort(Protocol):
    """Port for polling ephemeral agent pod health during spawn."""
    async def poll_spawn_status(self, event_id: str) -> SpawnPollResult: ...
    def clear_event(self, event_id: str) -> None: ...


class SpawnFailed(Exception):
    """Terminal pod failure — distinct from TimeoutError to separate fast-fail from deadline."""
    pass

logger = logging.getLogger(__name__)

INFRA_SENTINEL = "__EPHEMERAL_INFRA_FAIL__"

MAX_INFRA_FAILURES = 2


from dataclasses import dataclass, replace as _dc_replace


@dataclass
class DispatchMetrics:
    """Counters for dispatch outcomes — exposed as immutable snapshot via property.

    Safe: no await points between counter increments (asyncio single-threaded guarantee).
    """
    total: int = 0
    success: int = 0
    infra_fail: int = 0
    circuit_break: int = 0
    sidecar_fallback: int = 0
    spawn_latency_sum: float = 0.0
    spawn_latency_count: int = 0

    @property
    def avg_spawn_latency_sec(self) -> float:
        return (self.spawn_latency_sum / self.spawn_latency_count) if self.spawn_latency_count else 0.0

    @property
    def success_rate_pct(self) -> float:
        return (self.success / self.total * 100) if self.total else 100.0


class EphemeralProvisioner:
    """Provisions ephemeral agents via Tekton EventListener webhook.

    Pure plumbing: spawn an agent for an event, terminate on close.
    Capacity control (per-source WIP limits) lives in the Brain --
    it gates at the event level (NEW -> ACTIVE transition), not
    at the agent level.  By the time ``ensure_agent`` is called the
    Brain has already admitted the event.
    """

    def __init__(
        self,
        registry: AgentRegistry,
        event_listener_url: str,
        health_port: SpawnHealthPort | None = None,
        deadline_sec: float = 300,
        poll_interval_sec: float = 10,
        stall_timeout_sec: float = 60,
    ) -> None:
        self._registry = registry
        self._url = event_listener_url
        self._health_port = health_port
        self._deadline_sec = deadline_sec
        self._poll_interval_sec = poll_interval_sec
        self._stall_timeout_sec = stall_timeout_sec
        self._pending: dict[str, asyncio.Event] = {}
        self._infra_failures: dict[str, int] = {}
        self._dispatch_metrics = DispatchMetrics()

    def record_dispatch_success(self, latency_sec: float) -> None:
        self._dispatch_metrics.total += 1
        self._dispatch_metrics.success += 1
        self._dispatch_metrics.spawn_latency_sum += latency_sec
        self._dispatch_metrics.spawn_latency_count += 1

    def record_dispatch_infra_fail(self) -> None:
        self._dispatch_metrics.total += 1
        self._dispatch_metrics.infra_fail += 1

    def record_dispatch_circuit_break(self) -> None:
        self._dispatch_metrics.total += 1
        self._dispatch_metrics.circuit_break += 1

    def record_dispatch_sidecar_fallback(self) -> None:
        self._dispatch_metrics.total += 1
        self._dispatch_metrics.sidecar_fallback += 1

    @property
    def dispatch_metrics(self) -> DispatchMetrics:
        return _dc_replace(self._dispatch_metrics)

    async def ensure_agent(
        self, event_id: str, installation_id: str = "", model: str = "",
    ) -> "AgentConnection | str | None":
        """Ensure an ephemeral agent exists for this event. Spawn if needed.

        `installation_id` (GitHub App installation) is forwarded to the TaskRun as
        GITHUB_INSTALLATION_ID -- the provisioner stays pure and never resolves it itself.

        `model` (per-role model override) is forwarded to the TaskRun as AGENT_MODEL --
        only included in the POST body when non-empty, so an empty value never overrides
        the TriggerTemplate's Helm-configured default.

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
            await self._trigger_taskrun(event_id, installation_id, model)
            agent = await self._wait_for_registration(
                event_id, self._deadline_sec,
                self._poll_interval_sec, self._stall_timeout_sec,
            )
            self._infra_failures.pop(event_id, None)
            return agent
        except (httpx.HTTPError, asyncio.TimeoutError, SpawnFailed) as exc:
            logger.warning(
                "Ephemeral dispatch failed for %s (%d/%d): %s. Cleaning up and retrying.",
                event_id, failures + 1, MAX_INFRA_FAILURES, exc or "handshake timeout",
            )
            await self._cancel_taskrun(event_id)
            if self._health_port:
                self._health_port.clear_event(event_id)
            await asyncio.sleep(5)

            try:
                await self._trigger_taskrun(event_id, installation_id, model)
                retry_deadline = max(60.0, self._deadline_sec / 2)
                agent = await self._wait_for_registration(
                    event_id, retry_deadline,
                    self._poll_interval_sec, self._stall_timeout_sec,
                )
                self._infra_failures.pop(event_id, None)
                logger.info("Ephemeral retry succeeded for %s after cleanup", event_id)
                return agent
            except (httpx.HTTPError, asyncio.TimeoutError, SpawnFailed) as retry_exc:
                self._infra_failures[event_id] = failures + 1
                logger.warning(
                    "Ephemeral retry also failed for %s (%d/%d): %s.",
                    event_id, failures + 1, MAX_INFRA_FAILURES, retry_exc or "handshake timeout",
                )
                await self._cancel_taskrun(event_id)
                if self._health_port:
                    self._health_port.clear_event(event_id)
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
        if self._health_port:
            self._health_port.clear_event(event_id)

    async def _trigger_taskrun(
        self, event_id: str, installation_id: str = "", model: str = "",
    ) -> None:
        payload = {
            "event_id": event_id, "action": "spawn", "installation_id": installation_id,
        }
        if model:
            payload["model"] = model
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(self._url, json=payload)
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
        self,
        event_id: str,
        deadline_sec: float = 300,
        poll_interval_sec: float = 10,
        stall_timeout_sec: float = 60,
    ) -> "AgentConnection":
        """Wait for ephemeral agent WS registration with pod health polling.

        Hybrid loop: asyncio.Event for instant registration detection +
        SpawnHealthPort polls for early termination on pod failures.
        Degrades to blind wait when health_port is None.
        """
        evt = asyncio.Event()
        self._pending[event_id] = evt
        start = time.monotonic()
        last_progress: float | None = None

        try:
            while True:
                # Registration check FIRST — before deadline, so a late registration
                # during a slow health poll is never missed (codereview R2 F1).
                if evt.is_set():
                    agent = await self._registry.get_ephemeral(event_id)
                    if not agent:
                        raise asyncio.TimeoutError("Registered but not in registry")
                    return agent

                elapsed = time.monotonic() - start
                remaining = deadline_sec - elapsed
                if remaining <= 0:
                    raise asyncio.TimeoutError(
                        f"Spawn deadline exceeded ({deadline_sec:.0f}s)"
                    )

                wait_time = min(poll_interval_sec, remaining)
                try:
                    await asyncio.wait_for(evt.wait(), timeout=wait_time)
                    agent = await self._registry.get_ephemeral(event_id)
                    if not agent:
                        raise asyncio.TimeoutError("Registered but not in registry")
                    return agent
                except asyncio.TimeoutError:
                    pass

                if self._health_port:
                    result = await self._health_port.poll_spawn_status(event_id)
                    logger.info(
                        "Spawn health [%s]: status=%s reason=%s elapsed=%.0fs",
                        event_id, result.status.value, result.reason, elapsed,
                    )
                    if result.status == SpawnStatus.FAILED:
                        raise SpawnFailed(
                            f"Pod terminal: {result.reason} ({result.pod_name})"
                        )
                    if result.status in (SpawnStatus.PENDING, SpawnStatus.RUNNING):
                        last_progress = time.monotonic()

                if last_progress is not None:
                    stall = time.monotonic() - last_progress
                    if stall > stall_timeout_sec:
                        raise asyncio.TimeoutError(
                            f"No spawn progress for {stall:.0f}s"
                        )
        finally:
            self._pending.pop(event_id, None)
