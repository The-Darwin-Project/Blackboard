# src/scheduling/reconciler.py
# @ai-rules:
# 1. [Constraint]: Pure asyncio -- no Redis, no LLM, no external deps. Testable in isolation.
# 2. [Pattern]: FairQueue = asyncio.Queue + in_flight set + pending set. enqueue is O(1) dedup check.
# 3. [Gotcha]: Worker count is fixed at start. Dynamic scaling is NOT supported (use env var restart).
# 4. [Pattern]: reconcile_fn receives event_id only. All state lives in the Brain, not the scheduler.
# 5. [Constraint]: Scheduler NEVER catches exceptions from reconcile_fn -- they propagate to worker error handler.
# 6. [Pattern]: mark_done must be called after reconcile_fn completes (success or failure) to release the key.
"""
ReconcileScheduler: Kubernetes controller-runtime style fair event scheduler.

FairQueue provides per-key deduplication with FIFO ordering.
ReconcileScheduler manages N worker coroutines that drain the queue.
"""
import asyncio
import logging
import time
from typing import Awaitable, Callable, Protocol

logger = logging.getLogger(__name__)


class Trigger(Protocol):
    """Protocol for event sources that enqueue work."""

    async def start(self, scheduler: "ReconcileScheduler") -> None: ...
    async def stop(self) -> None: ...


class FairQueue:
    """Per-key deduplicating FIFO queue.

    Guarantees:
    - An event_id appears at most once in pending + inflight combined.
    - FIFO ordering for distinct keys.
    - enqueue() is a no-op if the key is already pending or inflight.
    - mark_done() releases the key for future re-enqueue.
    """

    def __init__(self) -> None:
        self._queue: asyncio.Queue[str] = asyncio.Queue()
        self._pending: set[str] = set()
        self._inflight: set[str] = set()
        self._total_enqueued: int = 0
        self._dedup_count: int = 0

    def enqueue(self, event_id: str) -> bool:
        """Enqueue if not already pending or inflight. Returns True if enqueued."""
        if event_id in self._pending or event_id in self._inflight:
            self._dedup_count += 1
            return False
        self._pending.add(event_id)
        self._queue.put_nowait(event_id)
        self._total_enqueued += 1
        return True

    async def dequeue(self) -> str:
        """Block until item available. Move from pending to inflight."""
        event_id = await self._queue.get()
        self._pending.discard(event_id)
        self._inflight.add(event_id)
        return event_id

    def mark_done(self, event_id: str) -> None:
        """Remove from inflight. Allows future re-enqueue."""
        self._inflight.discard(event_id)

    @property
    def pending_count(self) -> int:
        return len(self._pending)

    @property
    def inflight_count(self) -> int:
        return len(self._inflight)

    @property
    def stats(self) -> dict:
        return {
            "pending": self.pending_count,
            "inflight": self.inflight_count,
            "total_enqueued": self._total_enqueued,
            "dedup_count": self._dedup_count,
        }


class ReconcileScheduler:
    """Controller-runtime style reconciler with N concurrent workers.

    Usage:
        scheduler = ReconcileScheduler(reconcile_fn=brain.process_event, workers=9)
        scheduler.register_trigger(my_trigger)
        await scheduler.start()  # blocks until stop() is called
    """

    def __init__(
        self,
        reconcile_fn: Callable[[str], Awaitable[None]],
        workers: int = 4,
        on_error: Callable[[str, Exception], Awaitable[None]] | None = None,
        stats_interval: float = 60.0,
    ) -> None:
        self._reconcile_fn = reconcile_fn
        self._worker_count = workers
        self._on_error = on_error
        self._stats_interval = stats_interval
        self._queue = FairQueue()
        self._triggers: list[Trigger] = []
        self._worker_tasks: list[asyncio.Task] = []
        self._trigger_tasks: list[asyncio.Task] = []
        self._stats_task: asyncio.Task | None = None
        self._running = False
        self._reconcile_count: int = 0
        self._error_count: int = 0
        self._total_reconcile_ms: float = 0.0

    def register_trigger(self, trigger: Trigger) -> None:
        """Register a trigger to be started with the scheduler."""
        self._triggers.append(trigger)

    def enqueue(self, event_id: str) -> bool:
        """Enqueue an event for reconciliation. No-op if already pending/inflight."""
        return self._queue.enqueue(event_id)

    def tracked_event_ids(self) -> set[str]:
        """All event_ids currently pending or inflight. Public API for StalenessGuard."""
        return self._queue._pending | self._queue._inflight

    async def start(self) -> None:
        """Start workers and triggers. Blocks until stop() is called."""
        self._running = True
        logger.info(
            "ReconcileScheduler starting: workers=%d, triggers=%d",
            self._worker_count, len(self._triggers),
        )

        for i in range(self._worker_count):
            task = asyncio.create_task(self._worker_loop(i), name=f"reconcile-worker-{i}")
            self._worker_tasks.append(task)

        for trigger in self._triggers:
            task = asyncio.create_task(self._run_trigger(trigger), name=f"trigger-{type(trigger).__name__}")
            self._trigger_tasks.append(task)

        if self._stats_interval > 0:
            self._stats_task = asyncio.create_task(self._stats_loop(), name="reconcile-stats")

        try:
            await asyncio.gather(*self._worker_tasks, return_exceptions=True)
        finally:
            self._running = False

    async def stop(self) -> None:
        """Graceful shutdown: stop triggers, drain queue, cancel workers."""
        self._running = False
        logger.info("ReconcileScheduler stopping...")

        for trigger in self._triggers:
            try:
                await trigger.stop()
            except Exception as e:
                logger.warning("Trigger stop failed: %s", e)

        for task in self._trigger_tasks:
            task.cancel()

        if self._stats_task:
            self._stats_task.cancel()

        for task in self._worker_tasks:
            task.cancel()

        await asyncio.gather(*self._worker_tasks, *self._trigger_tasks, return_exceptions=True)
        logger.info("ReconcileScheduler stopped. Final stats: %s", self.metrics)

    async def _worker_loop(self, worker_id: int) -> None:
        """Single worker: dequeue -> reconcile -> mark_done -> repeat."""
        logger.debug("Worker %d started", worker_id)
        while self._running:
            try:
                event_id = await asyncio.wait_for(self._queue.dequeue(), timeout=5.0)
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break

            start_ms = time.time() * 1000
            try:
                await self._reconcile_fn(event_id)
                self._reconcile_count += 1
            except asyncio.CancelledError:
                break
            except Exception as e:
                self._error_count += 1
                logger.error("Reconcile error for %s (worker %d): %s", event_id, worker_id, e)
                if self._on_error:
                    try:
                        await self._on_error(event_id, e)
                    except Exception:
                        pass
            finally:
                elapsed = time.time() * 1000 - start_ms
                self._total_reconcile_ms += elapsed
                self._queue.mark_done(event_id)

    async def _run_trigger(self, trigger: Trigger) -> None:
        """Run a trigger, restarting on non-fatal errors."""
        while self._running:
            try:
                await trigger.start(self)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.warning("Trigger %s failed, restarting in 5s: %s", type(trigger).__name__, e)
                await asyncio.sleep(5)

    async def _stats_loop(self) -> None:
        """Periodically log queue stats."""
        while self._running:
            await asyncio.sleep(self._stats_interval)
            if self._running:
                avg_ms = (self._total_reconcile_ms / self._reconcile_count) if self._reconcile_count else 0
                logger.info(
                    "ReconcileScheduler stats: %s | reconciled=%d errors=%d avg_ms=%.1f",
                    self._queue.stats, self._reconcile_count, self._error_count, avg_ms,
                )

    @property
    def metrics(self) -> dict:
        avg_ms = (self._total_reconcile_ms / self._reconcile_count) if self._reconcile_count else 0
        return {
            **self._queue.stats,
            "workers": self._worker_count,
            "reconcile_count": self._reconcile_count,
            "error_count": self._error_count,
            "avg_reconcile_ms": round(avg_ms, 1),
            "running": self._running,
        }
