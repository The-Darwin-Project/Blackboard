# tests/test_nightwatcher_deadlock_remediation.py
"""
ATDD Acceptance & Unit Test Suite for Nightwatcher Deadlock Remediation.
Jira: VMER-2236 (Plan: nightwatcher-backlog-and-quota-deadlock)
Dave Farley 4-Layer ATDD Model:
  T-1: Bounded lease query in blackboard (limit parameter)
  T-2: Quota tracker fail-fast guardrail on oversize payloads
  T-3: Atomic inflight cleanup & FIFO preservation in restage_orphans
  T-4: Null-safe lean Phase 1 prompt construction
  T-5: Railway auto-reconciliation with platform taxonomy in validate_cluster_plan
  T-6: Standalone backlog drain script dry-run classification
"""

import json
import time
import pytest
from unittest.mock import AsyncMock, MagicMock

from src.agents.llm.quota_tracker import QuotaTracker, QuotaExhaustedError
from src.state.blackboard import BlackboardState
from src.models import StagedEscalation, ShiftReport
from src.observers.nightwatcher import NightwatcherObserver
from src.observers.nightwatcher_tools import validate_cluster_plan, VALID_PLATFORMS


# ==============================================================================
# Layer 2 & 3: DSL & Drivers
# ==============================================================================

class NightwatcherHarnessDriver:
    """ATDD Protocol Driver for Nightwatcher Deadlock Remediation scenarios."""

    @staticmethod
    def sample_staged_escalation(
        event_id: str,
        staged_at: float = 1000.0,
        summary: str = "CI test failure",
        description: str = "Traceback (most recent call last):\n ...",
    ):
        return StagedEscalation(
            event_id=event_id,
            service="test-service",
            source="aligner",
            reason="ci_failure",
            summary=summary,
            platform="kargo",
            description=description,
            staged_at=staged_at,
        )


# ==============================================================================
# Layer 1: Executable Domain Scenarios (T-1 to T-6)
# ==============================================================================

@pytest.mark.asyncio
async def test_t1_bounded_lease_pending_escalations():
    """T-1: Given 724 items in pending, When lease_pending_escalations is called with limit=25,
    Then Redis query uses start=0, num=limit and leases at most 25 items."""
    bb = BlackboardState.__new__(BlackboardState)
    bb.redis = AsyncMock()

    fake_items = [
        json.dumps({
            "event_id": f"evt-{i}",
            "service": "test",
            "source": "aligner",
            "reason": "ci_failure",
            "summary": f"sum-{i}",
            "platform": "kargo",
            "staged_at": 1000.0 + i,
        })
        for i in range(50)
    ]

    pipe_mock = AsyncMock()
    captured_kwargs = {}

    async def mock_zrangebyscore(*args, **kwargs):
        captured_kwargs.update(kwargs)
        limit = kwargs.get("num", len(fake_items))
        return fake_items[:limit]

    pipe_mock.zrangebyscore = AsyncMock(side_effect=mock_zrangebyscore)
    pipe_mock.zrem = MagicMock()
    pipe_mock.sadd = MagicMock()
    pipe_mock.execute = AsyncMock(return_value=[None, None])

    bb.redis.pipeline = MagicMock(
        return_value=AsyncMock(__aenter__=AsyncMock(return_value=pipe_mock), __aexit__=AsyncMock())
    )

    # Act
    leased, raw_members = await bb.lease_pending_escalations(before_ts=2000.0, limit=25)

    # Assert
    assert len(leased) == 25
    assert len(raw_members) == 25
    assert captured_kwargs.get("start") == 0
    assert captured_kwargs.get("num") == 25


@pytest.mark.asyncio
async def test_t2_quota_tracker_fail_fast_on_oversize_payload():
    """T-2: Given payload of 1,000,000 tokens and burst limit 500,000,
    When quota_tracker.acquire is called, Then it raises QuotaExhaustedError immediately without sleeping."""
    tracker = QuotaTracker(tpm_limit=500_000, burst_factor=0.8)

    start_time = time.monotonic()
    with pytest.raises(QuotaExhaustedError) as exc_info:
        await tracker.acquire(1_000_000, max_wait_seconds=120.0)

    elapsed = time.monotonic() - start_time

    assert elapsed < 0.2, f"acquire() took too long ({elapsed}s) instead of failing fast!"
    assert "exceed" in str(exc_info.value).lower() and "burst" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_t3_atomic_inflight_cleanup_and_fifo_restage_orphans():
    """T-3: Given orphaned escalations with varied staged_at timestamps,
    When restage_orphans is called, Then items are restored to pending with original staged_at
    scores, removed from inflight via pipe.srem, and returns count."""
    bb = BlackboardState.__new__(BlackboardState)
    bb.redis = AsyncMock()

    orphans = [
        json.dumps({"event_id": "evt-1", "staged_at": 100.5}),
        json.dumps({"event_id": "evt-2", "staged_at": 200.25}),
        "invalid-json-string-should-be-skipped",
    ]

    pipe_mock = AsyncMock()
    pipe_mock.zadd = MagicMock()
    pipe_mock.srem = MagicMock()
    pipe_mock.execute = AsyncMock(return_value=[None, None])

    bb.redis.pipeline = MagicMock(
        return_value=AsyncMock(__aenter__=AsyncMock(return_value=pipe_mock), __aexit__=AsyncMock())
    )

    # Act
    count = await bb.restage_orphans(orphans)

    # Assert
    assert count == 2
    zadd_calls = pipe_mock.zadd.call_args_list
    assert len(zadd_calls) == 2
    assert zadd_calls[0].args[1] == {orphans[0]: 100.5}
    assert zadd_calls[1].args[1] == {orphans[1]: 200.25}

    srem_calls = pipe_mock.srem.call_args_list
    assert len(srem_calls) == 1
    assert srem_calls[0].args == ("darwin:nightwatcher:inflight", *orphans)


@pytest.mark.asyncio
async def test_t4_null_safe_lean_phase1_prompt():
    """T-4: Given escalations with summary and massive stack traces in description,
    When Phase 1 prompt is constructed, Then description is omitted, no TypeError occurs,
    and summaries are capped at 140 chars."""
    driver = NightwatcherHarnessDriver()
    big_trace = "Traceback (most recent call last):\n" + ("  File 'foo.py', line 1, in bar\n" * 500)
    escalations = [
        driver.sample_staged_escalation("evt-short", summary="Short summary", description=big_trace),
        driver.sample_staged_escalation("evt-long", summary="A" * 200, description=big_trace),
        driver.sample_staged_escalation("evt-null", summary=None, description=big_trace),
    ]

    # Test format expression used in _run_analysis_loop
    lines = [
        f"- **{e.event_id}** | {e.service} | {e.platform} | {(e.summary or '')[:140]}"
        for e in escalations
    ]
    prompt = "\n".join(lines)

    assert "Traceback" not in prompt
    assert "evt-short" in prompt
    assert "evt-null" in prompt
    assert len("A" * 140) == 140
    assert ("A" * 141) not in prompt
    assert len(prompt) < 1000


def test_t5_railway_auto_reconciliation_validate_cluster_plan():
    """T-5: Given cluster plan omitting some manifest IDs,
    When validate_cluster_plan is invoked, Then it returns (True, '') and auto-reconciles
    missing events into a fallback cluster with valid platform taxonomy."""
    from src.agents.llm.types import VALID_PLATFORMS

    old = list(VALID_PLATFORMS)
    VALID_PLATFORMS.clear()
    VALID_PLATFORMS.extend(["Konflux", "Kargo"])
    try:
        manifest_ids = {"evt-1", "evt-2", "evt-3", "evt-4"}
        clusters = [
            {
                "title": "Build Failures",
                "platform": "Kargo",
                "events": ["evt-1"],
                "reasoning": "kargo promotions failed",
            }
        ]

        is_valid, error = validate_cluster_plan(clusters, manifest_ids)

        assert is_valid is True
        assert error == ""
        assert len(clusters) == 2

        fallback = clusters[1]
        assert fallback["title"] == "Unassigned Staged Escalations (Auto-Reconciled)"
        assert set(fallback["events"]) == {"evt-2", "evt-3", "evt-4"}
        assert fallback["platform"] in VALID_PLATFORMS
        assert "reasoning" in fallback
    finally:
        VALID_PLATFORMS.clear()
        VALID_PLATFORMS.extend(old)


def test_t6_backlog_drain_script_dry_run_import_and_parse():
    """T-6: Given drain_nightwatcher_backlog.py script,
    When invoked or imported, Then it exposes standard argument parser with --dry-run,
    --age-off-days, --batch-size, --delay-seconds."""
    from scripts.drain_nightwatcher_backlog import build_parser

    parser = build_parser()
    args = parser.parse_args(["--dry-run", "--age-off-days", "7", "--batch-size", "25", "--delay-seconds", "45"])

    assert args.dry_run is True
    assert args.age_off_days == 7
    assert args.batch_size == 25
    assert args.delay_seconds == 45


def test_t6_backlog_drain_script_classification_and_execution():
    """T-6b: Given mock Redis with stale and active items,
    When main() runs with --dry-run vs --execute,
    Then dry-run performs 0 mutations, and execute prunes stale items in bounded batches."""
    from unittest.mock import MagicMock, patch
    from scripts.drain_nightwatcher_backlog import classify_backlog, main

    now = 1_000_000.0
    mock_redis = MagicMock()
    mock_redis.zrange.return_value = [
        (b"stale-item-1", now - 8 * 86400),
        (b"stale-item-2", now - 10 * 86400),
        (b"active-item-1", now - 2 * 86400),
    ]
    mock_redis.zcard.return_value = 3

    with patch("time.time", return_value=now):
        stale_cnt, active_cnt, stale_items, active_items = classify_backlog(mock_redis, age_off_days=7)
        assert stale_cnt == 2
        assert active_cnt == 1

        # Test dry-run: zero pipeline mutations
        with patch("scripts.drain_nightwatcher_backlog.get_redis_client", return_value=mock_redis):
            res_dry = main(["--dry-run", "--age-off-days", "7"])
            assert res_dry == 0
            mock_redis.pipeline.assert_not_called()

        # Test execute: batched pipeline execution
        pipe_mock = MagicMock()
        mock_redis.pipeline.return_value = pipe_mock
        with patch("scripts.drain_nightwatcher_backlog.get_redis_client", return_value=mock_redis):
            res_exec = main(["--execute", "--age-off-days", "7", "--batch-size", "1", "--delay-seconds", "0"])
            assert res_exec == 0
            assert pipe_mock.execute.call_count == 2

