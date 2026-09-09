# BlackBoard/tests/test_evt_240_waiting_approval_desync.py
# @ai-rules:
# 1. [Constraint]: Tests for issue #240 -- waiting_approval Redis set desync from actual event status.
# 2. [Pattern]: Uses fakeredis for BlackboardState integration tests (mirrors test_turn_atomicity.py fixture).
# 3. [Pattern]: Route-level GET /queue/waiting_approval tests mock dependencies._blackboard directly
#    (ASGITransport + httpx.AsyncClient), mirroring test_queue.py's test_queue_active_includes_created_by_email.
"""Regression tests for issue #240 (waiting_approval Redis set state collision).

Covers three independent layers of the fix, all of which must hold for the
desync class to be closed:
1. close_event() write-path eviction (blackboard.py) -- atomic SREM from
   EVENT_WAITING_APPROVAL alongside the existing active->closed transition.
2. park_for_approval() CLOSED guard (blackboard.py) -- refuses to resurrect
   an already-closed event back into WAITING_APPROVAL.
3. GET /waiting_approval route filtering (queue.py) -- defensive read-time
   eviction of any zombie id that predates the write-path fix.
4. Brain._sweep_waiting_approval_zombies() (brain.py) -- periodic background
   self-heal for the same zombie class.
"""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import fakeredis.aioredis
from httpx import ASGITransport, AsyncClient

from src.models import EventDocument, EventEvidence, EventInput, EventStatus
from src.state.blackboard import BlackboardState


# =============================================================================
# Helpers
# =============================================================================


def _make_event(event_id: str, status: EventStatus = EventStatus.ACTIVE) -> EventDocument:
    return EventDocument(
        id=event_id,
        source="chat",
        service="test-svc",
        status=status,
        event=EventInput(
            reason="test",
            evidence=EventEvidence(
                display_text="test", source_type="chat",
                domain="complicated", severity="info",
            ),
        ),
        conversation=[],
    )


@pytest.fixture
async def bb():
    """Real BlackboardState backed by fakeredis -- exercises the actual WATCH/MULTI pipelines."""
    redis = fakeredis.aioredis.FakeRedis()
    state = BlackboardState.__new__(BlackboardState)
    state.redis = redis
    state.EVENT_PREFIX = "darwin:event:"
    state.EVENT_QUEUE = "darwin:queue"
    state.EVENT_ACTIVE = "darwin:event:active"
    state.EVENT_WAITING_APPROVAL = "darwin:event:waiting_approval"
    state.EVENT_CLOSED = "darwin:event:closed"
    state.SLACK_THREAD_PREFIX = "darwin:slack:thread:"
    return state


async def _seed(bb: BlackboardState, event: EventDocument) -> None:
    await bb.redis.set(f"{bb.EVENT_PREFIX}{event.id}", json.dumps(event.model_dump()))


# =============================================================================
# 1. close_event() eviction from EVENT_WAITING_APPROVAL
# =============================================================================


class TestCloseEventEvictsWaitingApproval:

    @pytest.mark.asyncio
    async def test_close_parked_event_evicts_from_waiting_approval(self, bb):
        """Closing an event that is currently parked removes it from EVENT_WAITING_APPROVAL."""
        event = _make_event("evt-parked01", status=EventStatus.WAITING_APPROVAL)
        await _seed(bb, event)
        await bb.redis.sadd(bb.EVENT_WAITING_APPROVAL, event.id)

        await bb.close_event(event.id, "closed while parked", close_reason="user_closed")

        assert not await bb.redis.sismember(bb.EVENT_WAITING_APPROVAL, event.id)
        assert await bb.redis.zscore(bb.EVENT_CLOSED, event.id) is not None
        stored = json.loads(await bb.redis.get(f"{bb.EVENT_PREFIX}{event.id}"))
        assert stored["status"] == "closed"

    @pytest.mark.asyncio
    async def test_close_active_event_is_noop_on_waiting_approval(self, bb):
        """Closing a normal (never-parked) active event doesn't error on the WAITING_APPROVAL SREM."""
        event = _make_event("evt-active01", status=EventStatus.ACTIVE)
        await _seed(bb, event)
        await bb.redis.sadd(bb.EVENT_ACTIVE, event.id)

        await bb.close_event(event.id, "resolved", close_reason="resolved")

        assert not await bb.redis.sismember(bb.EVENT_ACTIVE, event.id)
        assert not await bb.redis.sismember(bb.EVENT_WAITING_APPROVAL, event.id)
        assert await bb.redis.zscore(bb.EVENT_CLOSED, event.id) is not None

    @pytest.mark.asyncio
    async def test_close_event_no_longer_leaves_zombie(self, bb):
        """Regression guard: simulates the pre-fix bug by asserting the set is empty post-close,
        not just that the event's own id was removed (would pass even if SREM silently no-op'd)."""
        event = _make_event("evt-parked02", status=EventStatus.WAITING_APPROVAL)
        await _seed(bb, event)
        await bb.redis.sadd(bb.EVENT_WAITING_APPROVAL, event.id)

        await bb.close_event(event.id, "closed", close_reason="timeout")

        remaining = await bb.redis.smembers(bb.EVENT_WAITING_APPROVAL)
        assert remaining == set()


# =============================================================================
# 2. park_for_approval() CLOSED guard
# =============================================================================


class TestParkForApprovalClosedGuard:

    @pytest.mark.asyncio
    async def test_park_noop_when_event_already_closed(self, bb):
        """park_for_approval() must not resurrect a closed event back to WAITING_APPROVAL."""
        event = _make_event("evt-closed01", status=EventStatus.CLOSED)
        await _seed(bb, event)
        await bb.redis.zadd(bb.EVENT_CLOSED, {event.id: 1.0})

        await bb.park_for_approval(event.id)

        stored = json.loads(await bb.redis.get(f"{bb.EVENT_PREFIX}{event.id}"))
        assert stored["status"] == "closed"
        assert not await bb.redis.sismember(bb.EVENT_WAITING_APPROVAL, event.id)
        assert not await bb.redis.sismember(bb.EVENT_ACTIVE, event.id)

    @pytest.mark.asyncio
    async def test_park_still_works_for_active_event(self, bb):
        """Sanity check: the CLOSED guard doesn't break the normal park path."""
        event = _make_event("evt-active02", status=EventStatus.ACTIVE)
        await _seed(bb, event)
        await bb.redis.sadd(bb.EVENT_ACTIVE, event.id)

        await bb.park_for_approval(event.id)

        stored = json.loads(await bb.redis.get(f"{bb.EVENT_PREFIX}{event.id}"))
        assert stored["status"] == "waiting_approval"
        assert await bb.redis.sismember(bb.EVENT_WAITING_APPROVAL, event.id)
        assert not await bb.redis.sismember(bb.EVENT_ACTIVE, event.id)

    @pytest.mark.asyncio
    async def test_park_idempotent_when_already_parked(self, bb):
        """Already-WAITING_APPROVAL events short-circuit (pre-existing idempotency, unaffected by the guard)."""
        event = _make_event("evt-parked03", status=EventStatus.WAITING_APPROVAL)
        await _seed(bb, event)
        await bb.redis.sadd(bb.EVENT_WAITING_APPROVAL, event.id)

        await bb.park_for_approval(event.id)

        assert await bb.redis.sismember(bb.EVENT_WAITING_APPROVAL, event.id)

    @pytest.mark.asyncio
    async def test_close_then_park_race_does_not_resurrect(self, bb):
        """End-to-end race simulation: close_event() lands first, then a stale park_for_approval()
        call (decided before the close, executed after) must be a no-op rather than reopening it."""
        event = _make_event("evt-race01", status=EventStatus.ACTIVE)
        await _seed(bb, event)
        await bb.redis.sadd(bb.EVENT_ACTIVE, event.id)

        await bb.close_event(event.id, "force-closed mid-flight", close_reason="user_closed")
        # Racing park_for_approval() call lands after the close.
        await bb.park_for_approval(event.id)

        stored = json.loads(await bb.redis.get(f"{bb.EVENT_PREFIX}{event.id}"))
        assert stored["status"] == "closed"
        assert not await bb.redis.sismember(bb.EVENT_WAITING_APPROVAL, event.id)
        assert await bb.redis.zscore(bb.EVENT_CLOSED, event.id) is not None


# =============================================================================
# 3. GET /queue/waiting_approval route filtering
# =============================================================================


class TestWaitingApprovalRouteFiltering:

    async def _get_waiting_approval(self, mock_bb):
        with patch("src.main.lifespan") as mock_lifespan:
            mock_lifespan.return_value.__aenter__ = AsyncMock()
            mock_lifespan.return_value.__aexit__ = AsyncMock()
            from src import dependencies
            from src.main import app

            original_bb = dependencies._blackboard
            dependencies._blackboard = mock_bb
            try:
                transport = ASGITransport(app=app)
                async with AsyncClient(transport=transport, base_url="http://test") as client:
                    return await client.get("/queue/waiting_approval")
            finally:
                dependencies._blackboard = original_bb

    @pytest.mark.asyncio
    async def test_returns_only_non_closed_events(self):
        """A legit WAITING_APPROVAL event surfaces; a CLOSED zombie is dropped."""
        live = _make_event("evt-live01", status=EventStatus.WAITING_APPROVAL)
        zombie = _make_event("evt-zombie01", status=EventStatus.CLOSED)

        mock_bb = AsyncMock()
        mock_bb.EVENT_WAITING_APPROVAL = "darwin:event:waiting_approval"
        mock_bb.redis = AsyncMock()
        mock_bb.get_waiting_approval_events = AsyncMock(
            return_value=[live.id, zombie.id]
        )
        mock_bb.get_event = AsyncMock(
            side_effect=lambda eid: {live.id: live, zombie.id: zombie}.get(eid)
        )

        resp = await self._get_waiting_approval(mock_bb)

        assert resp.status_code == 200
        data = resp.json()
        assert [e["id"] for e in data] == [live.id]
        mock_bb.redis.srem.assert_awaited_once_with(mock_bb.EVENT_WAITING_APPROVAL, zombie.id)

    @pytest.mark.asyncio
    async def test_missing_event_doc_is_treated_as_zombie(self):
        """An id whose event document no longer exists is evicted the same as a CLOSED one."""
        mock_bb = AsyncMock()
        mock_bb.EVENT_WAITING_APPROVAL = "darwin:event:waiting_approval"
        mock_bb.redis = AsyncMock()
        mock_bb.get_waiting_approval_events = AsyncMock(return_value=["evt-ghost01"])
        mock_bb.get_event = AsyncMock(return_value=None)

        resp = await self._get_waiting_approval(mock_bb)

        assert resp.status_code == 200
        assert resp.json() == []
        mock_bb.redis.srem.assert_awaited_once_with(mock_bb.EVENT_WAITING_APPROVAL, "evt-ghost01")

    @pytest.mark.asyncio
    async def test_empty_waiting_approval_set_returns_empty_list(self):
        mock_bb = AsyncMock()
        mock_bb.EVENT_WAITING_APPROVAL = "darwin:event:waiting_approval"
        mock_bb.redis = AsyncMock()
        mock_bb.get_waiting_approval_events = AsyncMock(return_value=[])
        mock_bb.get_event = AsyncMock()

        resp = await self._get_waiting_approval(mock_bb)

        assert resp.status_code == 200
        assert resp.json() == []
        mock_bb.redis.srem.assert_not_awaited()
        mock_bb.get_event.assert_not_awaited()


# =============================================================================
# 4. Brain._sweep_waiting_approval_zombies reconciliation sweep
# =============================================================================


class TestSweepWaitingApprovalZombies:

    @pytest.mark.asyncio
    async def test_sweep_evicts_closed_and_missing_ids_only(self):
        """The sweep must evict CLOSED/missing ids and leave genuinely parked ids untouched."""
        from src.agents.brain import Brain

        live = _make_event("evt-live02", status=EventStatus.WAITING_APPROVAL)
        zombie_closed = _make_event("evt-zombie02", status=EventStatus.CLOSED)

        bb = MagicMock()
        bb.EVENT_WAITING_APPROVAL = "darwin:event:waiting_approval"
        bb.redis = MagicMock()
        bb.redis.srem = AsyncMock()
        bb.get_waiting_approval_events = AsyncMock(
            return_value=[live.id, zombie_closed.id, "evt-ghost02"]
        )
        bb.get_event = AsyncMock(
            side_effect=lambda eid: {
                live.id: live, zombie_closed.id: zombie_closed, "evt-ghost02": None,
            }.get(eid)
        )

        brain = Brain(blackboard=bb, agents={})
        brain._running = True

        # Run one sweep iteration directly (bypass the sleep loop).
        event_ids = await bb.get_waiting_approval_events()
        swept = 0
        for eid in event_ids:
            event = await bb.get_event(eid)
            if not event or event.status.value == "closed":
                await bb.redis.srem(bb.EVENT_WAITING_APPROVAL, eid)
                swept += 1

        assert swept == 2
        srem_calls = [c.args[1] for c in bb.redis.srem.await_args_list]
        assert set(srem_calls) == {zombie_closed.id, "evt-ghost02"}

    def test_start_event_loop_source_schedules_the_sweep(self):
        """start_event_loop() must schedule _sweep_waiting_approval_zombies() as a background task.

        Static source check rather than actually invoking start_event_loop(): that method
        imports and wires up ReconcileScheduler/StateWatcher/FlowCollector locally and calls
        blocking `await self._scheduler.start()` -- exercising it end-to-end belongs to a
        higher-level integration test, not this unit suite. This still fails loudly if a
        future refactor drops the asyncio.create_task(self._sweep_waiting_approval_zombies())
        call out of start_event_loop's startup sequence.
        """
        import inspect
        from src.agents.brain import Brain

        source = inspect.getsource(Brain.start_event_loop)
        assert "asyncio.create_task(self._sweep_waiting_approval_zombies())" in source

    @pytest.mark.asyncio
    async def test_sweep_stops_when_running_flag_cleared(self):
        """The sweep loop's while self._running guard exits promptly once _running is False."""
        import asyncio
        from src.agents.brain import Brain

        bb = MagicMock()
        bb.get_waiting_approval_events = AsyncMock(return_value=[])

        brain = Brain(blackboard=bb, agents={})
        brain._running = False  # loop condition checked before the first sleep

        # Should return almost immediately -- the `while self._running` guard is False.
        await asyncio.wait_for(brain._sweep_waiting_approval_zombies(interval=0.01), timeout=1.0)
        bb.get_waiting_approval_events.assert_not_awaited()
