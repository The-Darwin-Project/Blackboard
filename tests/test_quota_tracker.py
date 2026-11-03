# BlackBoard/tests/test_quota_tracker.py
# @ai-rules:
# 1. [Constraint]: Unit tests for QuotaTracker reservation lifecycle, rollback, and monotonic time domain.
# 2. [Pattern]: Validates T-1, T-9, clamping, and window pruning without sleeping.
"""Unit tests for QuotaTracker reservation lifecycle and monotonic time domain."""
import time
from unittest.mock import patch
import pytest

from src.agents.llm.quota_tracker import QuotaTracker, Reservation


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
    async def test_prune_evicts_stale_active_reservations_after_300s(self, tracker):
        """F-04: Stale active reservations older than 300s (exceeding 180s HTTP timeout) are evicted by _prune."""
        base_time = 1000.0
        with patch("time.monotonic", return_value=base_time):
            res = await tracker.acquire(estimated_tokens=5000, max_wait_seconds=5.0)
            assert res.id in tracker._active_reservations

        # 305s later, prune runs
        with patch("time.monotonic", return_value=base_time + 305.0):
            stats = tracker.get_stats()
            assert res.id not in tracker._active_reservations
            assert stats["active_reservations"] == 0

    @pytest.mark.asyncio
    async def test_record_ignores_already_finalized_reservation(self, tracker):
        """Record with an unknown or rolled-back reservation early-returns without recording delta."""
        res = await tracker.acquire(estimated_tokens=5000, max_wait_seconds=5.0)
        tracker.rollback(res)

        tokens_before = tracker._total_tokens
        # Attempt late record on already rolled-back reservation
        tracker.record(actual_tokens=8000, estimated_tokens=5000, reservation=res)
        assert tracker._total_tokens == tokens_before
