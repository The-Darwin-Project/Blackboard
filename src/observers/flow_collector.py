# BlackBoard/src/observers/flow_collector.py
# @ai-rules:
# 1. [Constraint]: Lives in src/observers/ because it writes to Redis (forbidden in src/scheduling/).
# 2. [Pattern]: External observer — reads scheduler.metrics (pull-only public API) + blackboard state.
# 3. [Gotcha]: Must survive Redis errors — try/except per cycle, log + continue.
# 4. [Pattern]: Maintains _prev_* counters for delta computation across snapshots.
# 5. [Constraint]: No Brain logic. No LLM. Pure data collection + persistence.
"""FlowCollector: periodic snapshot of system flow health, persisted to Redis."""
from __future__ import annotations

import asyncio
import logging
import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..agents.agent_registry import AgentRegistry
    from ..scheduling.reconciler import ReconcileScheduler
    from ..state.blackboard import BlackboardState

from ..models import FlowSnapshot

logger = logging.getLogger(__name__)


class FlowCollector:
    """Collects flow health snapshots every interval and persists to Redis."""

    def __init__(
        self,
        scheduler: "ReconcileScheduler",
        blackboard: "BlackboardState",
        registry: "AgentRegistry | None" = None,
        interval: float = 60.0,
    ):
        self._scheduler = scheduler
        self._blackboard = blackboard
        self._registry = registry
        self._interval = interval
        self._task: asyncio.Task | None = None
        self._running = False
        self._prev_reconcile_count = 0
        self._prev_error_count = 0

    async def start(self) -> None:
        if self._task is not None:
            return
        self._running = True
        self._task = asyncio.create_task(self._collect_loop(), name="flow-collector")
        logger.info("FlowCollector started (interval=%ds)", int(self._interval))

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        logger.info("FlowCollector stopped")

    async def _collect_loop(self) -> None:
        while self._running:
            try:
                snapshot = await self._build_snapshot()
                await self._blackboard.persist_flow_snapshot(snapshot)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.warning("FlowCollector: snapshot failed, skipping: %s", e)
            await asyncio.sleep(self._interval)

    async def _build_snapshot(self) -> FlowSnapshot:
        metrics = self._scheduler.metrics
        now = time.time()

        # Delta computation (guard against counter reset producing negative deltas)
        current_reconcile = metrics.get("reconcile_count", 0)
        current_errors = metrics.get("error_count", 0)
        if current_reconcile < self._prev_reconcile_count:
            self._prev_reconcile_count = 0
        if current_errors < self._prev_error_count:
            self._prev_error_count = 0
        reconcile_delta = current_reconcile - self._prev_reconcile_count
        error_delta = current_errors - self._prev_error_count
        self._prev_reconcile_count = current_reconcile
        self._prev_error_count = current_errors

        # Queue depth + active event count from blackboard (O(1) Redis ops)
        flow = await self._blackboard.get_flow_metrics()

        # Event status + age computation (two-step: cheap status map, then full docs for age)
        status_map = await self._blackboard.get_active_events_with_status()
        deferred_count = sum(1 for s in status_map.values() if s == "deferred")

        ages: list[float] = []
        if status_map:
            events = await asyncio.gather(*[
                self._blackboard.get_event(eid) for eid in status_map
            ])
            ages = [now - e.queued_at for e in events if e and e.queued_at is not None]

        avg_age = sum(ages) / len(ages) if ages else 0.0

        # Agent stats from registry
        busy = 0
        idle = 0
        try:
            if self._registry:
                agents = await self._registry.list_agents()
                for a in agents:
                    if a.get("busy"):
                        busy += 1
                    else:
                        idle += 1
        except Exception as e:
            logger.debug("FlowCollector: agent stats unavailable: %s", e)

        # Subscription count from state watcher (if available via blackboard)
        active_subs = 0
        try:
            active_subs = metrics.get("active_subscriptions", 0)
        except Exception:
            pass

        return FlowSnapshot(
            timestamp=now,
            queue_depth=flow["queue_depth"],
            active_events=len(status_map),
            deferred_events=deferred_count,
            busy_agents=busy,
            idle_agents=idle,
            active_subscriptions=active_subs,
            avg_event_age_sec=round(avg_age, 1),
            avg_reconcile_ms=metrics.get("avg_reconcile_ms", 0.0),
            reconcile_count_delta=reconcile_delta,
            error_count_delta=error_delta,
        )
