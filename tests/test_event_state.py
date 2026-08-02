# tests/test_event_state.py
# @ai-rules:
# 1. [Constraint]: Tests for EventState + CycleSnapshot — the Redis-backed per-event cycle state.
# 2. [Pattern]: pipeline() is MagicMock (sync). pipe.hgetall/hset/expire are sync (chaining).
#    Only pipe.execute is AsyncMock (awaited). EventState(redis=redis, flag_enabled=True).
# 3. [Gotcha]: set_fields(event_id, snapshot, **fields) requires CycleSnapshot positional arg.
#    CycleSnapshot uses generic .get(key) — no recall_lessons property.
# 4. [Pattern]: Each test class is independently runnable. mock_redis fixture in conftest.py.
"""Unit tests for EventState CRUD, CycleSnapshot write-through, TTL renewal,
backend switching, and fail-closed semantics.

These tests define the target interface (TDD). Expected to fail until
implementation lands.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_mock_redis() -> AsyncMock:
    """Mock Redis async client with pipeline support (matches M1 atomic fix).

    pipeline() is sync (returns MagicMock pipe). Pipe methods (hgetall,
    hset, expire) are sync (return pipe for chaining). Only pipe.execute()
    is async (awaited in _RedisBackend).
    """
    redis = AsyncMock()
    redis.hgetall.return_value = {}
    redis.hget.return_value = None
    redis.hset.return_value = True
    redis.hdel.return_value = 1
    redis.delete.return_value = 1
    redis.expire.return_value = True
    redis.sadd.return_value = 1
    redis.sismember.return_value = False
    pipe = MagicMock()
    pipe.hgetall.return_value = pipe
    pipe.hset.return_value = pipe
    pipe.expire.return_value = pipe
    pipe.execute = AsyncMock(return_value=[{}, True])
    redis.pipeline = MagicMock(return_value=pipe)
    return redis


# ---------------------------------------------------------------------------
# Test 1: EventState CRUD
# ---------------------------------------------------------------------------

class TestEventStateCRUD:
    """get returns CycleSnapshot, set_fields persists, clear_fields removes, delete cleans all."""

    @pytest.mark.asyncio
    async def test_get_returns_cycle_snapshot(self):
        """EventState.get(event_id) returns a CycleSnapshot instance."""
        from src.state.event_state import EventState, CycleSnapshot

        redis = _make_mock_redis()
        pipe = redis.pipeline.return_value
        pipe.execute.return_value = [{"agent_name": "sysadmin", "response_emitted": "1"}, True]
        state = EventState(redis=redis, flag_enabled=True)

        snapshot = await state.get("evt-test01")

        assert isinstance(snapshot, CycleSnapshot)
        redis.pipeline.assert_called()

    @pytest.mark.asyncio
    async def test_set_fields_persists_to_redis(self):
        """set_fields writes key-value pairs via pipeline (atomic with expire)."""
        from src.state.event_state import EventState

        redis = _make_mock_redis()
        pipe = redis.pipeline.return_value
        pipe.execute.return_value = [{"agent_name": "developer"}, True]
        state = EventState(redis=redis, flag_enabled=True)
        snapshot = await state.get("evt-test02")

        await state.set_fields("evt-test02", snapshot, agent_name="developer", wait_turn="5")

        pipe.hset.assert_called()
        pipe.expire.assert_called()

    @pytest.mark.asyncio
    async def test_clear_fields_removes_keys(self):
        """clear_fields removes specified keys from the Redis hash."""
        from src.state.event_state import EventState

        redis = _make_mock_redis()
        pipe = redis.pipeline.return_value
        pipe.execute.return_value = [{}, True]
        state = EventState(redis=redis, flag_enabled=True)
        snapshot = await state.get("evt-test03")

        await state.clear_fields("evt-test03", snapshot, "agent_name", "wait_turn")

        redis.hdel.assert_awaited()

    @pytest.mark.asyncio
    async def test_delete_cleans_all(self):
        """delete removes the entire Redis hash for an event."""
        from src.state.event_state import EventState

        redis = _make_mock_redis()
        state = EventState(redis=redis)

        await state.delete("evt-test04")

        redis.delete.assert_awaited()


# ---------------------------------------------------------------------------
# Test 2: CycleSnapshot write-through
# ---------------------------------------------------------------------------

class TestCycleSnapshotWriteThrough:
    """set_fields mutates snapshot._data immediately (visible to same-cycle property reads)."""

    @pytest.mark.asyncio
    async def test_set_fields_mutates_snapshot_data(self):
        """After set_fields, reading the snapshot property reflects the new value."""
        from src.state.event_state import EventState, CycleSnapshot

        redis = _make_mock_redis()
        pipe = redis.pipeline.return_value
        pipe.execute.return_value = [{}, True]
        state = EventState(redis=redis, flag_enabled=True)

        snapshot = await state.get("evt-wt01")
        assert snapshot.agent_name == ""

        await state.set_fields("evt-wt01", snapshot, agent_name="architect")
        assert snapshot.agent_name == "architect"

        # Re-read via pipeline returns the written value
        pipe.execute.return_value = [{"agent_name": "architect"}, True]
        snapshot_fresh = await state.get("evt-wt01")
        assert snapshot_fresh.agent_name == "architect"


# ---------------------------------------------------------------------------
# Test 3: RECALL write-then-read-next-iteration
# ---------------------------------------------------------------------------

class TestRecallWriteThenRead:
    """Write recall_lessons in snapshot, read via property in same object → sees new value."""

    @pytest.mark.asyncio
    async def test_recall_lessons_roundtrip(self):
        """Writing recall_lessons via set_fields and reading back in same CycleSnapshot."""
        from src.state.event_state import EventState

        redis = _make_mock_redis()
        pipe = redis.pipeline.return_value
        state = EventState(redis=redis, flag_enabled=True)

        snapshot = await state.get("evt-recall01")

        import json
        lessons = [{"title": "lesson-1", "score": 0.9}]
        await state.set_fields("evt-recall01", snapshot, recall_lessons=json.dumps(lessons))

        pipe.execute.return_value = [{"recall_lessons": json.dumps(lessons)}, True]
        snapshot_read = await state.get("evt-recall01")
        assert snapshot_read.get("recall_lessons") != ""


# ---------------------------------------------------------------------------
# Test 4: TTL renewal
# ---------------------------------------------------------------------------

class TestTTLRenewal:
    """set_fields calls EXPIRE on every write."""

    @pytest.mark.asyncio
    async def test_set_fields_calls_expire(self):
        """Every set_fields call renews the TTL via pipeline EXPIRE."""
        from src.state.event_state import EventState

        redis = _make_mock_redis()
        pipe = redis.pipeline.return_value
        state = EventState(redis=redis, flag_enabled=True)

        snapshot = await state.get("evt-ttl01")
        await state.set_fields("evt-ttl01", snapshot, agent_name="sysadmin")

        pipe.expire.assert_called()

    @pytest.mark.asyncio
    async def test_touch_ttl_renews_without_writing_fields(self):
        """touch_ttl calls EXPIRE without writing any hash fields."""
        from src.state.event_state import EventState

        redis = _make_mock_redis()
        state = EventState(redis=redis)

        await state.touch_ttl("evt-ttl02")

        redis.expire.assert_awaited()
        redis.hmset.assert_not_awaited()


# ---------------------------------------------------------------------------
# Test 5: Facade backend switching
# ---------------------------------------------------------------------------

class TestFacadeBackendSwitching:
    """flag_enabled=True → Redis, flag_enabled=False → memory dict (same interface)."""

    @pytest.mark.asyncio
    async def test_redis_backend_when_flag_true(self):
        """When flag_enabled=True, operations go to Redis via pipeline."""
        from src.state.event_state import EventState

        redis = _make_mock_redis()
        pipe = redis.pipeline.return_value
        state = EventState(redis=redis, flag_enabled=True)

        snapshot = await state.get("evt-flag01")
        await state.set_fields("evt-flag01", snapshot, agent_name="developer")

        pipe.hset.assert_called()

    @pytest.mark.asyncio
    async def test_memory_backend_when_flag_false(self):
        """When flag_enabled=False, operations use in-memory dict (Redis not called)."""
        from src.state.event_state import EventState

        redis = _make_mock_redis()
        state = EventState(redis=redis, flag_enabled=False)

        snapshot = await state.get("evt-flag02")
        await state.set_fields("evt-flag02", snapshot, agent_name="developer")

        redis.pipeline.assert_not_called()

    @pytest.mark.asyncio
    async def test_memory_backend_get_returns_snapshot(self):
        """Memory backend still returns a CycleSnapshot with the same interface."""
        from src.state.event_state import EventState, CycleSnapshot

        redis = _make_mock_redis()
        state = EventState(redis=redis, flag_enabled=False)

        snapshot = await state.get("evt-flag03")
        await state.set_fields("evt-flag03", snapshot, agent_name="architect")
        snapshot = await state.get("evt-flag03")

        assert isinstance(snapshot, CycleSnapshot)
        assert snapshot.agent_name == "architect"


# ---------------------------------------------------------------------------
# Test 6: Fail-closed
# ---------------------------------------------------------------------------

class TestFailClosed:
    """Redis error raises (not silently returns empty)."""

    @pytest.mark.asyncio
    async def test_redis_error_raises_on_get(self):
        """When pipeline.execute errors, EventState.get raises (fail-closed)."""
        from src.state.event_state import EventState

        redis = _make_mock_redis()
        pipe = redis.pipeline.return_value
        pipe.execute.side_effect = ConnectionError("Redis unavailable")
        state = EventState(redis=redis, flag_enabled=True)

        with pytest.raises((ConnectionError, RuntimeError)):
            await state.get("evt-fail01")

    @pytest.mark.asyncio
    async def test_redis_error_raises_on_set(self):
        """When pipeline.execute errors, EventState.set_fields raises (fail-closed)."""
        from src.state.event_state import EventState, CycleSnapshot

        redis = _make_mock_redis()
        pipe = redis.pipeline.return_value
        state = EventState(redis=redis, flag_enabled=True)

        snapshot = CycleSnapshot({})
        pipe.execute.side_effect = ConnectionError("Redis unavailable")

        with pytest.raises((ConnectionError, RuntimeError)):
            await state.set_fields("evt-fail02", snapshot, agent_name="developer")


# ---------------------------------------------------------------------------
# Test 7: incident_created Redis SET
# ---------------------------------------------------------------------------

class TestIncidentCreatedSet:
    """SADD marks, SISMEMBER checks, survives across EventState instances."""

    @pytest.mark.asyncio
    async def test_sadd_marks_incident(self):
        """mark_incident_created calls SADD on Redis."""
        from src.state.event_state import EventState

        redis = _make_mock_redis()
        state = EventState(redis=redis)

        await state.mark_incident_created("evt-inc01")

        redis.sadd.assert_awaited()

    @pytest.mark.asyncio
    async def test_sismember_checks_incident(self):
        """is_incident_created calls SISMEMBER on Redis."""
        from src.state.event_state import EventState

        redis = _make_mock_redis()
        redis.sismember.return_value = True
        state = EventState(redis=redis)

        result = await state.is_incident_created("evt-inc02")

        assert result is True
        redis.sismember.assert_awaited()

    @pytest.mark.asyncio
    async def test_survives_across_instances(self):
        """Incident created marker persists in Redis across EventState instances."""
        from src.state.event_state import EventState

        redis = _make_mock_redis()
        state1 = EventState(redis=redis)
        await state1.mark_incident_created("evt-inc03")

        state2 = EventState(redis=redis)
        redis.sismember.return_value = True
        result = await state2.is_incident_created("evt-inc03")

        assert result is True
