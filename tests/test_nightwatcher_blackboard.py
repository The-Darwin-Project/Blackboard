# tests/test_nightwatcher_blackboard.py
# @ai-rules:
# 1. [Pattern]: Mock Redis client via AsyncMock. Tests blackboard staging methods in isolation.
# 2. [Constraint]: Verify Redis command sequences (ZADD, ZRANGEBYSCORE, SADD, SREM, DEL).
# 3. [Pattern]: Each test constructs a BlackboardState with mock_redis from conftest.
"""Unit tests for Nightwatcher blackboard durable staging methods."""
from __future__ import annotations

import json
import time

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.models import ShiftReport, StagedEscalation
from src.state.blackboard import BlackboardState


# =========================================================================
# Fixtures
# =========================================================================

def _make_escalation(event_id="evt-1", service="svc-a", staged_at=1000.0, **kw):
    defaults = dict(source="aligner", reason="cpu", summary="High CPU")
    defaults.update(kw)
    return StagedEscalation(
        event_id=event_id, service=service, staged_at=staged_at, **defaults,
    )


def _make_blackboard(mock_redis) -> BlackboardState:
    bb = BlackboardState.__new__(BlackboardState)
    bb.redis = mock_redis
    return bb


# =========================================================================
# stage_escalation
# =========================================================================

class TestStageEscalation:
    @pytest.mark.asyncio
    async def test_zadd_called_with_score(self, mock_redis):
        bb = _make_blackboard(mock_redis)
        esc = _make_escalation(staged_at=1500.0)
        await bb.stage_escalation(esc)
        mock_redis.zadd.assert_awaited_once()
        call_args = mock_redis.zadd.call_args
        key = call_args[0][0]
        mapping = call_args[0][1]
        assert key == bb.NIGHTWATCHER_PENDING
        scores = list(mapping.values())
        assert scores[0] == 1500.0


# =========================================================================
# lease_pending_escalations
# =========================================================================

class TestLeasePendingEscalations:
    @pytest.mark.asyncio
    async def test_empty_pending_returns_empty(self, mock_redis):
        bb = _make_blackboard(mock_redis)
        mock_pipe = AsyncMock()
        mock_pipe.__aenter__ = AsyncMock(return_value=mock_pipe)
        mock_pipe.__aexit__ = AsyncMock(return_value=False)
        mock_pipe.watch = AsyncMock()
        mock_pipe.reset = AsyncMock()
        mock_pipe.zrangebyscore = AsyncMock(return_value=[])
        mock_redis.pipeline = MagicMock(return_value=mock_pipe)

        result, json_members = await bb.lease_pending_escalations(time.time())
        assert result == []
        assert json_members == []

    @pytest.mark.asyncio
    async def test_leases_and_parses_escalations(self, mock_redis):
        bb = _make_blackboard(mock_redis)
        esc = _make_escalation("evt-1", "svc-a", staged_at=100.0)
        json_str = esc.model_dump_json()

        mock_pipe = AsyncMock()
        mock_pipe.__aenter__ = AsyncMock(return_value=mock_pipe)
        mock_pipe.__aexit__ = AsyncMock(return_value=False)
        mock_pipe.watch = AsyncMock()
        mock_pipe.zrangebyscore = AsyncMock(return_value=[json_str])
        mock_pipe.multi = MagicMock()
        mock_pipe.zrem = MagicMock()
        mock_pipe.sadd = MagicMock()
        mock_pipe.expire = MagicMock()
        mock_pipe.execute = AsyncMock(return_value=[1, 1, 1, True])
        mock_redis.pipeline = MagicMock(return_value=mock_pipe)

        escalations, members = await bb.lease_pending_escalations(time.time())
        assert len(escalations) == 1
        assert escalations[0].event_id == "evt-1"
        assert len(members) == 1
        assert members[0] == json_str


# =========================================================================
# commit_inflight
# =========================================================================

class TestCommitInflight:
    @pytest.mark.asyncio
    async def test_srem_called(self, mock_redis):
        bb = _make_blackboard(mock_redis)
        await bb.commit_inflight(["json1", "json2"])
        mock_redis.srem.assert_awaited_once_with(
            bb.NIGHTWATCHER_INFLIGHT, "json1", "json2",
        )

    @pytest.mark.asyncio
    async def test_empty_list_skips(self, mock_redis):
        bb = _make_blackboard(mock_redis)
        await bb.commit_inflight([])
        mock_redis.srem.assert_not_awaited()


# =========================================================================
# requeue_inflight
# =========================================================================

class TestRequeueInflight:
    @pytest.mark.asyncio
    async def test_no_inflight_returns_zero(self, mock_redis):
        bb = _make_blackboard(mock_redis)
        mock_redis.smembers = AsyncMock(return_value=set())
        count = await bb.requeue_inflight()
        assert count == 0

    @pytest.mark.asyncio
    async def test_requeues_with_original_timestamp(self, mock_redis):
        bb = _make_blackboard(mock_redis)
        esc_json = json.dumps({"event_id": "evt-1", "staged_at": 500.0})
        mock_redis.smembers = AsyncMock(return_value={esc_json})
        mock_redis.zadd = AsyncMock()
        mock_redis.delete = AsyncMock()

        count = await bb.requeue_inflight()
        assert count == 1
        mock_redis.zadd.assert_awaited_once()
        call_args = mock_redis.zadd.call_args
        mapping = call_args[0][1]
        assert mapping[esc_json] == 500.0
        mock_redis.delete.assert_awaited_once_with(bb.NIGHTWATCHER_INFLIGHT)

    @pytest.mark.asyncio
    async def test_corrupt_member_skipped(self, mock_redis):
        bb = _make_blackboard(mock_redis)
        mock_redis.smembers = AsyncMock(return_value={"not-valid-json"})
        mock_redis.zadd = AsyncMock()
        mock_redis.delete = AsyncMock()

        count = await bb.requeue_inflight()
        assert count == 0
        mock_redis.delete.assert_awaited_once()


# =========================================================================
# count_pending_escalations
# =========================================================================

class TestCountPendingEscalations:
    @pytest.mark.asyncio
    async def test_delegates_to_zcard(self, mock_redis):
        bb = _make_blackboard(mock_redis)
        mock_redis.zcard = AsyncMock(return_value=7)
        count = await bb.count_pending_escalations()
        assert count == 7
        mock_redis.zcard.assert_awaited_once_with(bb.NIGHTWATCHER_PENDING)


# =========================================================================
# persist_shift_report / get_shift_report
# =========================================================================

class TestShiftReportPersistence:
    @pytest.mark.asyncio
    async def test_persist_sets_key_and_index(self, mock_redis):
        bb = _make_blackboard(mock_redis)
        report = ShiftReport(
            shift_date="2026-04-29", window="morning",
            window_start="2026-04-29T06:00Z", window_end="2026-04-29T12:00Z",
            status="completed", started_at=1000.0,
        )
        await bb.persist_shift_report(report)
        mock_redis.set.assert_awaited_once()
        set_key = mock_redis.set.call_args[0][0]
        assert "2026-04-29:morning" in set_key
        mock_redis.zadd.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_get_returns_parsed_report(self, mock_redis):
        bb = _make_blackboard(mock_redis)
        report = ShiftReport(
            shift_date="2026-04-29", window="evening",
            window_start="s", window_end="e", status="empty",
        )
        mock_redis.get = AsyncMock(return_value=report.model_dump_json())
        result = await bb.get_shift_report("2026-04-29", "evening")
        assert result.shift_date == "2026-04-29"
        assert result.window == "evening"
        assert result.status == "empty"

    @pytest.mark.asyncio
    async def test_get_missing_returns_none(self, mock_redis):
        bb = _make_blackboard(mock_redis)
        mock_redis.get = AsyncMock(return_value=None)
        result = await bb.get_shift_report("2026-01-01", "morning")
        assert result is None


# =========================================================================
# list_shift_reports
# =========================================================================

class TestListShiftReports:
    @pytest.mark.asyncio
    async def test_empty_range_returns_empty(self, mock_redis):
        bb = _make_blackboard(mock_redis)
        mock_redis.zrangebyscore = AsyncMock(return_value=[])
        result = await bb.list_shift_reports(0, time.time())
        assert result == []

    @pytest.mark.asyncio
    async def test_returns_metadata_fields(self, mock_redis):
        bb = _make_blackboard(mock_redis)
        report_data = {
            "shift_date": "2026-04-29", "window": "morning",
            "status": "completed", "manifest": [{"event_id": "e1"}],
            "incidents": [{"affected_events": ["e1"]}],
            "metrics": {"noise_reduction_pct": 80.0},
        }
        mock_redis.zrangebyscore = AsyncMock(return_value=["2026-04-29:morning"])
        mock_redis.mget = AsyncMock(return_value=[json.dumps(report_data)])

        result = await bb.list_shift_reports(0, time.time())
        assert len(result) == 1
        assert result[0]["shift_date"] == "2026-04-29"
        assert result[0]["escalation_count"] == 1
        assert result[0]["incident_count"] == 1
        assert result[0]["noise_reduction_pct"] == 80.0
