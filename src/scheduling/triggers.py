# src/scheduling/triggers.py
# @ai-rules:
# 1. [Constraint]: Triggers enqueue event_ids -- they NEVER call process_event directly.
# 2. [Pattern]: QueueTrigger owns the BRPOP loop. ResyncTrigger owns the periodic active-set scan.
# 3. [Gotcha]: ResyncTrigger interval must be > 1s to avoid tight-spinning (default 5s).
# 4. [Pattern]: StalenessGuard is source-scoped policy. Named instances: jarvis (120s), chat (5400s). Extensible via name param.
"""
Trigger implementations for ReconcileScheduler.

QueueTrigger: drains the Redis event queue via a dequeue callback.
ResyncTrigger: periodic active-set scan that discovers missed events.
StalenessGuard: source-scoped TTL enforcement (e.g., JARVIS 120s auto-close).
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import TYPE_CHECKING, Awaitable, Callable

if TYPE_CHECKING:
    from .reconciler import ReconcileScheduler

logger = logging.getLogger(__name__)


class QueueTrigger:
    """Drains the Redis event queue via a dequeue callback.

    On each iteration: calls dequeue_fn (blocking up to BRPOP timeout),
    enqueues the returned event_id into the scheduler's FairQueue.
    Exponential backoff on errors (2s -> 60s cap).
    """

    def __init__(self, dequeue_fn: Callable[[], Awaitable[str | None]]) -> None:
        self._dequeue_fn = dequeue_fn
        self._running = False

    async def start(self, scheduler: ReconcileScheduler) -> None:
        self._running = True
        backoff = 2
        logger.info("QueueTrigger started")
        while self._running:
            try:
                event_id = await self._dequeue_fn()
                if event_id:
                    scheduler.enqueue(event_id)
                    logger.info("QueueTrigger: enqueued %s", event_id)
                backoff = 2
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.warning("QueueTrigger error, retry in %ds: %s", backoff, e)
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 60)

    async def stop(self) -> None:
        self._running = False


class ResyncTrigger:
    """Periodic active-set scan that discovers events needing reconciliation.

    Every `interval` seconds: calls scan_fn -> enqueues each returned event_id.
    scan_fn is Brain._scan_active_for_reconcile (handles side effects internally).
    """

    def __init__(
        self,
        scan_fn: Callable[[], Awaitable[list[str]]],
        interval: float = 5.0,
    ) -> None:
        if interval < 1.0:
            raise ValueError("ResyncTrigger interval must be >= 1.0s")
        self._scan_fn = scan_fn
        self._interval = interval
        self._running = False

    async def start(self, scheduler: ReconcileScheduler) -> None:
        self._running = True
        logger.info("ResyncTrigger started (interval=%.1fs)", self._interval)
        while self._running:
            try:
                await asyncio.sleep(self._interval)
                if not self._running:
                    break
                event_ids = await self._scan_fn()
                enqueued = 0
                for eid in event_ids:
                    if scheduler.enqueue(eid):
                        enqueued += 1
                if enqueued:
                    logger.debug("ResyncTrigger: enqueued %d/%d events", enqueued, len(event_ids))
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.warning("ResyncTrigger scan error: %s", e)
                await asyncio.sleep(self._interval)

    async def stop(self) -> None:
        self._running = False


class StalenessGuard:
    """Source-scoped TTL enforcement for stale events.

    Periodically scans tracked events (pending + inflight) via scheduler's public API.
    If check_fn returns True (stale), calls on_stale to handle cleanup.
    Policy enforcement (source filtering, TTL thresholds) lives in check_fn, not here.
    """

    def __init__(
        self,
        check_fn: Callable[[str], Awaitable[bool]],
        on_stale: Callable[[str], Awaitable[None]],
        interval: float = 10.0,
        name: str = "default",
    ) -> None:
        self._check_fn = check_fn
        self._on_stale = on_stale
        self._interval = interval
        self._name = name
        self._running = False
        self._last_sweep_at: float = 0.0
        self._last_sweep_duration: float = 0.0
        self._sweep_count: int = 0
        self._stale_close_count: int = 0
        self._error_count: int = 0

    async def start(self, scheduler: ReconcileScheduler) -> None:
        self._running = True
        logger.info("StalenessGuard[%s] started (interval=%.1fs)", self._name, self._interval)
        while self._running:
            try:
                await asyncio.sleep(self._interval)
                if not self._running:
                    break
                sweep_start = time.time()
                stale_count = 0
                tracked = list(scheduler.tracked_event_ids())
                for eid in tracked:
                    try:
                        if await self._check_fn(eid):
                            await self._on_stale(eid)
                            stale_count += 1
                    except Exception as e:
                        self._error_count += 1
                        logger.warning("StalenessGuard[%s] check failed for %s: %s", self._name, eid, e)
                self._last_sweep_at = sweep_start
                self._last_sweep_duration = time.time() - sweep_start
                self._sweep_count += 1
                self._stale_close_count += stale_count
                if stale_count:
                    logger.info("StalenessGuard[%s]: handled %d stale events", self._name, stale_count)
            except asyncio.CancelledError:
                break
            except Exception as e:
                self._error_count += 1
                logger.warning("StalenessGuard[%s] error: %s", self._name, e)
                await asyncio.sleep(self._interval)

    async def stop(self) -> None:
        self._running = False

    def metrics(self) -> dict:
        return {
            "name": self._name,
            "last_sweep_at": self._last_sweep_at,
            "last_sweep_duration": round(self._last_sweep_duration, 3),
            "sweep_count": self._sweep_count,
            "stale_close_count": self._stale_close_count,
            "error_count": self._error_count,
        }
