# tests/test_reconciler.py
"""Unit tests for the ReconcileScheduler and FairQueue."""
import asyncio
import pytest
from src.scheduling.reconciler import FairQueue, ReconcileScheduler


# =============================================================================
# FairQueue Tests
# =============================================================================


class TestFairQueueFIFO:
    @pytest.mark.asyncio
    async def test_enqueue_dequeue_fifo(self):
        """Items dequeue in FIFO order."""
        q = FairQueue()
        q.enqueue("a")
        q.enqueue("b")
        q.enqueue("c")
        assert await q.dequeue() == "a"
        assert await q.dequeue() == "b"
        assert await q.dequeue() == "c"

    @pytest.mark.asyncio
    async def test_enqueue_returns_true_on_new(self):
        q = FairQueue()
        assert q.enqueue("a") is True

    @pytest.mark.asyncio
    async def test_enqueue_returns_false_on_dedup(self):
        q = FairQueue()
        q.enqueue("a")
        assert q.enqueue("a") is False


class TestFairQueueDedup:
    @pytest.mark.asyncio
    async def test_dedup_pending(self):
        """Second enqueue of same key while pending is a no-op."""
        q = FairQueue()
        q.enqueue("a")
        q.enqueue("a")
        assert q.pending_count == 1
        assert q.stats["dedup_count"] == 1
        assert await q.dequeue() == "a"
        # Queue should now be empty
        assert q.pending_count == 0

    @pytest.mark.asyncio
    async def test_dedup_inflight(self):
        """Enqueue while inflight is a no-op."""
        q = FairQueue()
        q.enqueue("a")
        await q.dequeue()  # now inflight
        assert q.inflight_count == 1
        assert q.enqueue("a") is False
        assert q.stats["dedup_count"] == 1

    @pytest.mark.asyncio
    async def test_enqueue_after_done(self):
        """After mark_done, the key can be re-enqueued."""
        q = FairQueue()
        q.enqueue("a")
        await q.dequeue()
        q.mark_done("a")
        assert q.inflight_count == 0
        assert q.enqueue("a") is True
        assert await q.dequeue() == "a"


class TestFairQueueStats:
    @pytest.mark.asyncio
    async def test_stats_tracking(self):
        q = FairQueue()
        q.enqueue("a")
        q.enqueue("b")
        q.enqueue("a")  # dedup
        assert q.stats == {
            "pending": 2,
            "inflight": 0,
            "total_enqueued": 2,
            "dedup_count": 1,
        }
        await q.dequeue()  # a moves to inflight
        assert q.stats["pending"] == 1
        assert q.stats["inflight"] == 1


# =============================================================================
# ReconcileScheduler Tests
# =============================================================================


class TestReconcileSchedulerWorkers:
    @pytest.mark.asyncio
    async def test_concurrent_workers(self):
        """N workers process N events concurrently."""
        processing = set()
        max_concurrent = 0
        events_done = []
        barrier = asyncio.Event()

        async def reconcile(event_id: str):
            nonlocal max_concurrent
            processing.add(event_id)
            max_concurrent = max(max_concurrent, len(processing))
            await barrier.wait()  # All workers block until released
            processing.discard(event_id)
            events_done.append(event_id)

        scheduler = ReconcileScheduler(reconcile_fn=reconcile, workers=3, stats_interval=0)

        task = asyncio.create_task(scheduler.start())
        await asyncio.sleep(0.05)

        scheduler.enqueue("e1")
        scheduler.enqueue("e2")
        scheduler.enqueue("e3")
        await asyncio.sleep(0.1)

        assert max_concurrent == 3
        barrier.set()
        await asyncio.sleep(0.1)
        assert set(events_done) == {"e1", "e2", "e3"}

        await scheduler.stop()
        await asyncio.sleep(0.05)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    @pytest.mark.asyncio
    async def test_backpressure(self):
        """With 2 workers and 5 events, only 2 process at a time."""
        processing = set()
        max_concurrent = 0
        gate = asyncio.Event()

        async def reconcile(event_id: str):
            nonlocal max_concurrent
            processing.add(event_id)
            max_concurrent = max(max_concurrent, len(processing))
            await gate.wait()
            processing.discard(event_id)

        scheduler = ReconcileScheduler(reconcile_fn=reconcile, workers=2, stats_interval=0)

        task = asyncio.create_task(scheduler.start())
        await asyncio.sleep(0.05)

        for i in range(5):
            scheduler.enqueue(f"e{i}")
        await asyncio.sleep(0.1)

        assert max_concurrent == 2
        assert scheduler._queue.pending_count == 3  # 5 enqueued - 2 inflight

        gate.set()
        await asyncio.sleep(0.2)
        await scheduler.stop()
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    @pytest.mark.asyncio
    async def test_worker_error_isolation(self):
        """One worker error doesn't crash others."""
        results = []
        error_events = []

        async def reconcile(event_id: str):
            if event_id == "bad":
                raise ValueError("simulated failure")
            results.append(event_id)

        async def on_error(event_id: str, exc: Exception):
            error_events.append(event_id)

        scheduler = ReconcileScheduler(
            reconcile_fn=reconcile, workers=2, on_error=on_error, stats_interval=0,
        )

        task = asyncio.create_task(scheduler.start())
        await asyncio.sleep(0.05)

        scheduler.enqueue("good1")
        scheduler.enqueue("bad")
        scheduler.enqueue("good2")
        await asyncio.sleep(0.2)

        assert "good1" in results
        assert "good2" in results
        assert "bad" in error_events
        assert scheduler._error_count == 1

        await scheduler.stop()
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


class TestReconcileSchedulerDedup:
    @pytest.mark.asyncio
    async def test_enqueue_while_inflight_is_noop(self):
        """Enqueue during processing is deduplicated."""
        call_count = 0
        gate = asyncio.Event()

        async def reconcile(event_id: str):
            nonlocal call_count
            call_count += 1
            await gate.wait()

        scheduler = ReconcileScheduler(reconcile_fn=reconcile, workers=1, stats_interval=0)

        task = asyncio.create_task(scheduler.start())
        await asyncio.sleep(0.05)

        scheduler.enqueue("e1")
        await asyncio.sleep(0.05)  # Worker picks up e1
        # e1 is now inflight -- re-enqueue should be no-op
        assert scheduler.enqueue("e1") is False

        gate.set()
        await asyncio.sleep(0.1)
        assert call_count == 1

        await scheduler.stop()
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    @pytest.mark.asyncio
    async def test_reenqueue_after_completion(self):
        """After reconcile completes, same key can be re-enqueued."""
        call_count = 0

        async def reconcile(event_id: str):
            nonlocal call_count
            call_count += 1

        scheduler = ReconcileScheduler(reconcile_fn=reconcile, workers=1, stats_interval=0)

        task = asyncio.create_task(scheduler.start())
        await asyncio.sleep(0.05)

        scheduler.enqueue("e1")
        await asyncio.sleep(0.1)
        assert call_count == 1

        # After completion, re-enqueue should work
        assert scheduler.enqueue("e1") is True
        await asyncio.sleep(0.1)
        assert call_count == 2

        await scheduler.stop()
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
