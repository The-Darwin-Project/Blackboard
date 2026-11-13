# BlackBoard/tests/test_quota_tracker.py
# @ai-rules:
# 1. [Constraint]: Unit tests for QuotaTracker reservation lifecycle, rollback, and monotonic time domain.
# 2. [Pattern]: Validates T-1, T-9, clamping, and window pruning without sleeping.
# 3. [Pattern]: Priority-gating tests must DISCRIMINATE: size capacity so only one waiter fits and make the low-priority
#    waiter wake first, otherwise they pass on sleep timing alone (see test_high_priority_acquires_first_when_capacity_frees).
"""Unit tests for QuotaTracker reservation lifecycle and monotonic time domain."""
import asyncio
import time
from unittest.mock import patch
import pytest

from src.agents.llm.quota_tracker import (
    PRIORITY_HIGH,
    PRIORITY_NORMAL,
    QuotaExhaustedError,
    QuotaTracker,
    RequestExceedsBurstError,
    Reservation,
)


@pytest.fixture
def tracker():
    # 60,000 tokens/min cap
    return QuotaTracker(tpm_cap=60000)


class TestQuotaTrackerReservationLifecycle:
    @pytest.mark.asyncio
    async def test_acquire_returns_reservation_token(self, tracker):
        """T-9 part 1: acquire returns Reservation with monotonic timestamp and tracks it in _active_reservations."""
        start_mono = time.monotonic()
        res = await tracker.acquire(estimated_tokens=5000, max_wait_seconds=5.0)
        end_mono = time.monotonic()

        assert isinstance(res, Reservation)
        assert res.tokens == 5000
        assert start_mono <= res.timestamp <= end_mono
        assert res.id in tracker._active_reservations
        assert tracker._active_reservations[res.id] == res

        stats = tracker.get_stats()
        assert stats["tokens_used_60s"] == 5000

    @pytest.mark.asyncio
    async def test_rollback_appends_negative_delta_and_cleans_reservation(self, tracker):
        """T-1: rollback applies negative delta with monotonic timestamp and cleans active reservation."""
        res = await tracker.acquire(estimated_tokens=8000, max_wait_seconds=5.0)
        assert res.id in tracker._active_reservations
        assert tracker.get_stats()["tokens_used_60s"] == 8000

        # Rollback (e.g. stream timeout)
        tracker.rollback(res)

        assert res.id not in tracker._active_reservations
        stats = tracker.get_stats()
        assert stats["tokens_used_60s"] == 0

        # Idempotent rollback
        tracker.rollback(res)
        assert tracker.get_stats()["tokens_used_60s"] == 0

    @pytest.mark.asyncio
    async def test_record_cleans_reservation_and_records_actual_usage(self, tracker):
        """T-9: record pops reservation and adjusts window with actual usage."""
        res = await tracker.acquire(estimated_tokens=5000, max_wait_seconds=5.0)
        assert res.id in tracker._active_reservations

        # Model actually consumed 6200 tokens
        tracker.record(actual_tokens=6200, estimated_tokens=5000, reservation=res)

        assert res.id not in tracker._active_reservations
        stats = tracker.get_stats()
        assert stats["tokens_used_60s"] == 6200

    @pytest.mark.asyncio
    async def test_clamping_prevents_negative_tokens_used(self, tracker):
        """Stats clamp tokens_used_60s to at least 0 even if negative deltas transiently exceed positive."""
        await tracker.acquire(estimated_tokens=4000, max_wait_seconds=5.0)
        # Manually invoke rollback with larger reservation to test clamping resilience
        bogus_res = Reservation(id="bogus", tokens=10000, timestamp=time.monotonic())
        tracker._active_reservations["bogus"] = bogus_res
        tracker.rollback(bogus_res)

        stats = tracker.get_stats()
        assert stats["tokens_used_60s"] >= 0

    @pytest.mark.asyncio
    async def test_monotonic_window_pruning_after_60s(self, tracker):
        """T-1/T-9: Pruning correctly purges both reservation and negative delta entries after 60s."""
        base_time = 1000.0
        with patch("time.monotonic", return_value=base_time):
            res = await tracker.acquire(estimated_tokens=3000, max_wait_seconds=5.0)
            tracker.rollback(res)
            # Before 60s: window has 2 entries (acquire + rollback delta)
            assert len(tracker._window) == 2
            assert tracker.get_stats()["tokens_used_60s"] == 0

        # 61 seconds later
        with patch("time.monotonic", return_value=base_time + 61.0):
            stats = tracker.get_stats()
            assert stats["tokens_used_60s"] == 0
            assert len(tracker._window) == 0

    @pytest.mark.asyncio
    async def test_rollback_after_60s_does_not_inject_phantom_anti_tokens(self, tracker):
        """F-02: Rollback after 60s (e.g. 120s timeout) does not inject negative tokens into window."""
        base_time = 1000.0
        with patch("time.monotonic", return_value=base_time):
            res = await tracker.acquire(estimated_tokens=5000, max_wait_seconds=5.0)

        # 120s later, rollback occurs (stream timeout)
        with patch("time.monotonic", return_value=base_time + 120.0):
            tracker.rollback(res)
            # Window should be completely empty (positive already pruned, no negative appended)
            assert len(tracker._window) == 0
            assert tracker.get_stats()["tokens_used_60s"] == 0
            assert res.id not in tracker._active_reservations

    @pytest.mark.asyncio
    async def test_prune_evicts_stale_active_reservations_after_default_1800s_ttl(self, tracker, monkeypatch):
        """F-04: Active reservations survive below the 1800s default TTL (+600s, +1795s) and are evicted at +1805s."""
        monkeypatch.delenv("LLM_HTTP_TIMEOUT_SEC", raising=False)
        base_time = 1000.0
        with patch("time.monotonic", return_value=base_time):
            res = await tracker.acquire(estimated_tokens=5000, max_wait_seconds=5.0)
            assert res.id in tracker._active_reservations

        for offset in (600.0, 1795.0):
            with patch("time.monotonic", return_value=base_time + offset):
                stats = tracker.get_stats()
                assert res.id in tracker._active_reservations
                assert stats["active_reservations"] == 1

        with patch("time.monotonic", return_value=base_time + 1805.0):
            stats_evicted = tracker.get_stats()
            assert res.id not in tracker._active_reservations
            assert stats_evicted["active_reservations"] == 0
            assert stats_evicted["total_tokens"] == 0

    @pytest.mark.asyncio
    async def test_record_ignores_already_finalized_reservation(self, tracker):
        """Record with an unknown or rolled-back reservation early-returns without recording delta."""
        res = await tracker.acquire(estimated_tokens=5000, max_wait_seconds=5.0)
        tracker.rollback(res)

        tokens_before = tracker._total_tokens
        # Attempt late record on already rolled-back reservation
        tracker.record(actual_tokens=8000, estimated_tokens=5000, reservation=res)
        assert tracker._total_tokens == tokens_before


class TestQuotaTrackerPriorityReservation:
    """Dave Farley ATDD 4-Layer Spec for Priority-Aware Token Reservation (Step 5)."""

    @pytest.mark.asyncio
    async def test_high_priority_immediate_acquire_no_leak(self, tracker):
        """Immediate acquire with priority=0 when capacity exists, check high_priority_waiters == 0."""
        res = await tracker.acquire(estimated_tokens=5000, max_wait_seconds=5.0, priority=0)
        assert isinstance(res, Reservation)
        assert res.tokens == 5000
        stats = tracker.get_stats()
        assert stats["high_priority_waiters"] == 0

    @pytest.mark.asyncio
    async def test_low_priority_gated_while_high_priority_waiting(self, tracker):
        """Low-priority request (priority=1) is blocked when high-priority request is waiting for capacity."""
        # Fill tracker near limit: cap is 60,000, fill with 50,000
        await tracker.acquire(estimated_tokens=50000, max_wait_seconds=5.0)

        high_prio_started = asyncio.Event()
        low_prio_admitted = asyncio.Event()

        async def high_prio_caller():
            high_prio_started.set()
            # Needs 20,000 tokens (50k + 20k > 60k limit -> will wait)
            return await tracker.acquire(estimated_tokens=20000, max_wait_seconds=0.5, priority=0)

        async def low_prio_caller():
            await high_prio_started.wait()
            # Give high_prio_caller a moment to enter acquire loop and increment waiter counter
            await asyncio.sleep(0.01)
            # Fits headroom if un-gated (50k + 5k <= 60k), but should be gated by high-prio waiter
            res = await tracker.acquire(estimated_tokens=5000, max_wait_seconds=0.2, priority=1)
            low_prio_admitted.set()
            return res

        high_task = asyncio.create_task(high_prio_caller())
        low_task = asyncio.create_task(low_prio_caller())

        # Low priority should fail or be gated (times out waiting) because high priority is waiting
        with pytest.raises(QuotaExhaustedError):
            await low_task

        assert not low_prio_admitted.is_set()

        # Clean up high priority task
        with pytest.raises(QuotaExhaustedError):
            await high_task

    @pytest.mark.asyncio
    async def test_high_priority_acquires_first_when_capacity_frees(self, tracker):
        """Freed capacity fits only ONE of two 10k waiters; the high-priority one must win even though it
        queued later and wakes later than the low-priority one.

        Discriminating setup (fails if priority gating is removed):
          - bucket is full: 10k (released later) + 50k (kept) = 60k
          - after releasing the 10k, headroom is exactly 10k -> only one waiter fits
          - the low-priority waiter enters first with a short deadline, so its poll wakes (t~0.2s) BEFORE the
            high-priority waiter's poll (t~1.0s). Without gating the low waiter grabs the 10k first and the
            high waiter times out. With gating the low waiter is held back (and times out) and high is admitted.
        """
        release_res = await tracker.acquire(estimated_tokens=10000, max_wait_seconds=5.0)
        await tracker.acquire(estimated_tokens=50000, max_wait_seconds=5.0)
        assert tracker.get_stats()["tokens_used_60s"] == 60000

        async def low_prio_caller():
            return await tracker.acquire(estimated_tokens=10000, max_wait_seconds=0.2, priority=PRIORITY_NORMAL)

        async def high_prio_caller():
            return await tracker.acquire(estimated_tokens=10000, max_wait_seconds=1.0, priority=PRIORITY_HIGH)

        low_task = asyncio.create_task(low_prio_caller())
        await asyncio.sleep(0.01)  # low enters acquire first (no high waiter yet -> merely capacity-blocked)
        high_task = asyncio.create_task(high_prio_caller())
        await asyncio.sleep(0.01)  # high registered as waiter
        assert tracker.get_stats()["high_priority_waiters"] == 1

        # Free exactly one 10k slot.
        tracker.rollback(release_res)

        results = await asyncio.gather(low_task, high_task, return_exceptions=True)
        low_result, high_result = results

        assert isinstance(high_result, Reservation), f"high-priority waiter must be admitted, got {high_result!r}"
        assert isinstance(low_result, QuotaExhaustedError), f"low-priority waiter must stay gated/blocked, got {low_result!r}"
        stats = tracker.get_stats()
        assert stats["tokens_used_60s"] == 60000
        assert stats["high_priority_waiters"] == 0

    @pytest.mark.asyncio
    async def test_high_priority_waiter_underflow_is_logged_and_clamped(self, tracker, caplog):
        """L-4: a decrement below zero is logged as an error and clamped at 0 (counter-imbalance signal)."""
        import logging

        await tracker.acquire(estimated_tokens=60000, max_wait_seconds=5.0)

        async def high_prio_caller():
            return await tracker.acquire(estimated_tokens=10000, max_wait_seconds=0.3, priority=PRIORITY_HIGH)

        task = asyncio.create_task(high_prio_caller())
        await asyncio.sleep(0.02)
        assert tracker._high_priority_waiters == 1

        # Simulate an external imbalance while the waiter is still registered.
        tracker._high_priority_waiters = 0
        with caplog.at_level(logging.ERROR, logger="src.agents.llm.quota_tracker"):
            with pytest.raises(QuotaExhaustedError):
                await task

        assert tracker._high_priority_waiters == 0
        assert any("underflow" in r.getMessage() for r in caplog.records)

    @pytest.mark.asyncio
    async def test_balanced_high_priority_acquire_does_not_log_underflow(self, tracker, caplog):
        """Normal balanced increment/decrement never emits the underflow error."""
        import logging

        with caplog.at_level(logging.ERROR, logger="src.agents.llm.quota_tracker"):
            await tracker.acquire(estimated_tokens=5000, max_wait_seconds=1.0, priority=PRIORITY_HIGH)
        assert not any("underflow" in r.getMessage() for r in caplog.records)

    @pytest.mark.asyncio
    async def test_high_priority_waiter_counter_cleaned_up_on_timeout(self, tracker):
        """Waiter counter decrements back to 0 on QuotaExhaustedError."""
        # Fill capacity
        await tracker.acquire(estimated_tokens=60000, max_wait_seconds=5.0)

        with pytest.raises(QuotaExhaustedError):
            await tracker.acquire(estimated_tokens=10000, max_wait_seconds=0.1, priority=0)

        stats = tracker.get_stats()
        assert stats["high_priority_waiters"] == 0

    @pytest.mark.asyncio
    async def test_high_priority_waiter_counter_cleaned_up_on_cancellation(self, tracker):
        """Waiter counter decrements back to 0 on asyncio.CancelledError."""
        await tracker.acquire(estimated_tokens=60000, max_wait_seconds=5.0)

        started = asyncio.Event()

        async def waiting_call():
            started.set()
            await tracker.acquire(estimated_tokens=10000, max_wait_seconds=5.0, priority=0)

        task = asyncio.create_task(waiting_call())
        await started.wait()
        await asyncio.sleep(0.02)

        # Cancel the task while waiting
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

        stats = tracker.get_stats()
        assert stats["high_priority_waiters"] == 0

    @pytest.mark.asyncio
    async def test_oversize_high_priority_request_raises_burst_without_leaking_counter(self, tracker):
        """estimated_tokens > burst_limit raises RequestExceedsBurstError and _high_priority_waiters remains 0."""
        stats_before = tracker.get_stats()
        assert stats_before.get("high_priority_waiters", 0) == 0

        with pytest.raises(RequestExceedsBurstError):
            await tracker.acquire(estimated_tokens=70000, max_wait_seconds=5.0, priority=PRIORITY_HIGH)

        stats_after = tracker.get_stats()
        assert stats_after["high_priority_waiters"] == 0

    @pytest.mark.asyncio
    async def test_get_stats_includes_high_priority_waiters(self, tracker):
        """get_stats() dictionary has key 'high_priority_waiters'."""
        stats = tracker.get_stats()
        assert "high_priority_waiters" in stats

    @pytest.mark.asyncio
    async def test_multiple_concurrent_high_priority_waiters_tracked(self, tracker):
        """Concurrent high-priority waiters increment high_priority_waiters count and decrement cleanly."""
        await tracker.acquire(estimated_tokens=60000, max_wait_seconds=5.0)

        async def _waiter():
            return await tracker.acquire(estimated_tokens=10000, max_wait_seconds=0.1, priority=PRIORITY_HIGH)

        t1 = asyncio.create_task(_waiter())
        t2 = asyncio.create_task(_waiter())
        await asyncio.sleep(0.01)

        stats = tracker.get_stats()
        assert stats["high_priority_waiters"] == 2

        await asyncio.gather(t1, t2, return_exceptions=True)
        stats_final = tracker.get_stats()
        assert stats_final["high_priority_waiters"] == 0

    @pytest.mark.asyncio
    @pytest.mark.parametrize("invalid_tokens", [0, -1, -500, 1.5, "100", None, True])
    async def test_acquire_rejects_non_positive_or_non_integer_tokens(self, tracker, invalid_tokens):
        """validates ValueError when estimated_tokens <= 0 or non-int."""
        with pytest.raises(ValueError, match="estimated_tokens must be a positive integer"):
            await tracker.acquire(estimated_tokens=invalid_tokens, max_wait_seconds=1.0)

    @pytest.mark.asyncio
    @pytest.mark.parametrize("non_high_priority", [2, -1])
    async def test_arbitrary_non_high_priority_is_gated_when_high_priority_waiting(self, tracker, non_high_priority):
        """validates that priority=2 or negative priority is gated while high-priority is waiting."""
        await tracker.acquire(estimated_tokens=50000, max_wait_seconds=5.0)

        high_prio_started = asyncio.Event()
        non_high_admitted = asyncio.Event()

        async def high_prio_caller():
            high_prio_started.set()
            return await tracker.acquire(estimated_tokens=20000, max_wait_seconds=1.0, priority=0)

        async def non_high_caller():
            await high_prio_started.wait()
            for _ in range(50):
                if tracker._high_priority_waiters > 0:
                    break
                await asyncio.sleep(0.005)
            res = await tracker.acquire(estimated_tokens=5000, max_wait_seconds=0.2, priority=non_high_priority)
            non_high_admitted.set()
            return res

        high_task = asyncio.create_task(high_prio_caller())
        non_high_task = asyncio.create_task(non_high_caller())

        with pytest.raises(QuotaExhaustedError):
            await non_high_task

        assert not non_high_admitted.is_set()

        with pytest.raises(QuotaExhaustedError):
            await high_task


class TestQuotaTrackerDynamicStaleReservationEviction:
    """Dave Farley 4-Layer ATDD Spec (T-7):
    Dynamic stale-reservation TTL aligned above LLM_HTTP_TIMEOUT_SEC (max(1800s, HTTP + 120s))
    and unified warn-once registry across QuotaTracker._prune() and GeminiAdapter.
    """

    # -------------------------------------------------------------------------
    # Layer 3: Protocol Drivers & Monotonic Clock Helpers
    # -------------------------------------------------------------------------
    @staticmethod
    async def _acquire_at(qt: QuotaTracker, t0: float, tokens: int = 5000) -> Reservation:
        with patch("time.monotonic", return_value=t0):
            return await qt.acquire(estimated_tokens=tokens, max_wait_seconds=5.0)

    @staticmethod
    def _stats_at(qt: QuotaTracker, t: float) -> dict:
        with patch("time.monotonic", return_value=t):
            return qt.get_stats()

    # -------------------------------------------------------------------------
    # Layer 2: Domain-Specific Language (DSL) Assertions
    # -------------------------------------------------------------------------
    @classmethod
    async def assert_leaked_eviction_threshold(
        cls,
        monkeypatch,
        *,
        http_env: str | None,
        survive_offset: float,
        evict_offset: float,
    ) -> None:
        if http_env is None:
            monkeypatch.delenv("LLM_HTTP_TIMEOUT_SEC", raising=False)
        else:
            monkeypatch.setenv("LLM_HTTP_TIMEOUT_SEC", http_env)

        qt = QuotaTracker(tpm_cap=60000)
        base = 1000.0
        res = await cls._acquire_at(qt, base, tokens=5000)

        stats_alive = cls._stats_at(qt, base + survive_offset)
        assert res.id in qt._active_reservations, (
            f"Expected reservation to survive at +{survive_offset}s for LLM_HTTP_TIMEOUT_SEC={http_env!r}"
        )
        assert stats_alive["active_reservations"] == 1

        stats_evicted = cls._stats_at(qt, base + evict_offset)
        assert res.id not in qt._active_reservations, (
            f"Expected reservation to be evicted at +{evict_offset}s for LLM_HTTP_TIMEOUT_SEC={http_env!r}"
        )
        assert stats_evicted["active_reservations"] == 0
        assert stats_evicted["total_tokens"] == 0

    # -------------------------------------------------------------------------
    # Layer 1: Executable Scenarios (T-7)
    # -------------------------------------------------------------------------
    @pytest.mark.asyncio
    async def test_t7_active_carbon_reservation_survives_1200s_and_records_actual_tpm(
        self, monkeypatch
    ):
        """T-7a: Reservation acquired at t=1000.0 survives get_stats()/_prune() at +600s and +1200s,
        and record(actual_tokens=45000, estimated_tokens=5000, reservation=res) at +1205s records
        total_tokens == 45000 and tokens_used_60s == 40000.
        """
        monkeypatch.delenv("LLM_HTTP_TIMEOUT_SEC", raising=False)
        qt = QuotaTracker(tpm_cap=60000)
        base = 1000.0
        res = await self._acquire_at(qt, base, tokens=5000)

        for offset in (600.0, 1200.0):
            stats_mid = self._stats_at(qt, base + offset)
            assert res.id in qt._active_reservations
            assert stats_mid["active_reservations"] == 1

        with patch("time.monotonic", return_value=base + 1205.0):
            qt.record(actual_tokens=45000, estimated_tokens=5000, reservation=res)
            stats_done = qt.get_stats()

        assert res.id not in qt._active_reservations
        assert stats_done["active_reservations"] == 0
        assert stats_done["total_tokens"] == 45000
        assert stats_done["tokens_used_60s"] == 40000

    @pytest.mark.asyncio
    async def test_t7_leaked_reservation_evicted_at_dynamic_http_thresholds_and_warns_once(
        self, monkeypatch, caplog
    ):
        """T-7b: Leaked reservation eviction honors max(1800s, LLM_HTTP_TIMEOUT_SEC + 120s)
        across default (1800s), '900' floor (1800s), '2000' (2120s), and malformed 'junk' (1800s warn-once).
        """
        import logging
        from src.agents.llm import gemini_client

        monkeypatch.setattr(gemini_client, "_TIMEOUT_ENV_WARNED", set())

        # 1. Default (unset -> 1500s + 120s < 1800s floor -> 1800s)
        await self.assert_leaked_eviction_threshold(
            monkeypatch, http_env=None, survive_offset=1795.0, evict_offset=1805.0
        )

        # 2. Explicit "900" -> 900s + 120s = 1020s -> clamped up to 1800s floor
        await self.assert_leaked_eviction_threshold(
            monkeypatch, http_env="900", survive_offset=1795.0, evict_offset=1805.0
        )

        # 3. Explicit "2000" -> 2000s + 120s = 2120s (> 1800s floor)
        await self.assert_leaked_eviction_threshold(
            monkeypatch, http_env="2000", survive_offset=2115.0, evict_offset=2125.0
        )

        # 4. Malformed "junk" -> falls back to 1500s default -> 1800s floor; warns once across _prune + GeminiAdapter
        caplog.clear()
        with caplog.at_level(logging.WARNING, logger="src.agents.llm.gemini_client"):
            await self.assert_leaked_eviction_threshold(
                monkeypatch, http_env="junk", survive_offset=1795.0, evict_offset=1805.0
            )
            with patch("google.genai.Client"):
                gemini_client.GeminiAdapter("proj", "global", "gemini-4-carbon")

        invalid_warnings = [
            r for r in caplog.records if "Invalid LLM_HTTP_TIMEOUT_SEC" in r.getMessage()
        ]
        assert len(invalid_warnings) == 1, (
            f"Expected exactly 1 invalid LLM_HTTP_TIMEOUT_SEC warning across _prune() and GeminiAdapter, "
            f"got {len(invalid_warnings)}"
        )

    def test_t7_pre_import_prune_and_lazy_gemini_client_warn_once_in_fresh_subprocess(self):
        """T-7c: In a clean interpreter where gemini_client is NOT yet imported, calling
        QuotaTracker._prune() with LLM_HTTP_TIMEOUT_SEC='junk' and then lazily importing and
        initializing GeminiAdapter emits the invalid-env warning exactly once (no split-brain set).
        """
        import os
        import subprocess
        import sys
        from pathlib import Path

        repo_root = Path(__file__).resolve().parent.parent
        env = dict(os.environ)
        env["LLM_HTTP_TIMEOUT_SEC"] = "junk"
        for k in (
            "LLM_STREAM_CHUNK_TIMEOUT_SEC",
            "LLM_STREAM_TTFB_TIMEOUT_SEC",
            "LLM_STREAM_INTER_CHUNK_TIMEOUT_SEC",
            "LLM_STREAM_TOTAL_TIMEOUT_SEC",
        ):
            env.pop(k, None)

        probe_code = (
            "import logging, sys\n"
            "from unittest.mock import patch\n"
            "records = []\n"
            "class _ListHandler(logging.Handler):\n"
            "    def emit(self, record):\n"
            "        records.append(record.getMessage())\n"
            "lg = logging.getLogger('src.agents.llm.gemini_client')\n"
            "lg.setLevel(logging.WARNING)\n"
            "lg.addHandler(_ListHandler())\n"
            "from src.agents.llm.quota_tracker import QuotaTracker\n"
            "assert 'src.agents.llm.gemini_client' not in sys.modules\n"
            "qt = QuotaTracker(tpm_cap=60000)\n"
            "qt._prune()\n"
            "qt._prune()\n"
            "pre_count = sum('Invalid LLM_HTTP_TIMEOUT_SEC' in m for m in records)\n"
            "from src.agents.llm.gemini_client import GeminiAdapter\n"
            "with patch('google.genai.Client'):\n"
            "    GeminiAdapter('proj', 'global', 'gemini-4-carbon')\n"
            "qt._prune()\n"
            "total_count = sum('Invalid LLM_HTTP_TIMEOUT_SEC' in m for m in records)\n"
            "assert pre_count == 1, f'Expected pre_count==1 after pre-import _prune(), got {pre_count}: {records}'\n"
            "assert total_count == 1, f'Expected total_count==1 after lazy GeminiAdapter import, got {total_count}: {records}'\n"
        )

        proc = subprocess.run(
            [sys.executable, "-c", probe_code],
            cwd=repo_root,
            env=env,
            capture_output=True,
            text=True,
            timeout=60,
        )
        assert proc.returncode == 0, f"Fresh-interpreter warn-once probe failed:\n{proc.stderr}\n{proc.stdout}"




