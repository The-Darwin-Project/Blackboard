# BlackBoard/tests/test_evt_240_waiting_approval_desync.py
# @ai-rules:
# 1. [Constraint]: Tests for issue #240 -- waiting_approval Redis set desync from actual event status.
# 2. [Pattern]: Uses fakeredis for BlackboardState integration tests (mirrors test_turn_atomicity.py fixture).
# 3. [Pattern]: Route-level GET /queue/waiting_approval and GET /queue/active tests mock
#    dependencies._blackboard directly (ASGITransport + httpx.AsyncClient), mirroring
#    test_queue.py's test_queue_active_includes_created_by_email.
# 4. [Pattern]: TestSweepWaitingApprovalZombies patches asyncio.sleep (side_effect flips
#    brain._running False) to force exactly one real iteration of the sweep loop
#    deterministically -- NOT a re-implementation of the eviction logic (code_reviewer
#    HIGH finding: the original version tested a copy-pasted inline loop instead).
"""Regression tests for issue #240 (waiting_approval Redis set state collision).

Covers the independent layers of the fix, all of which must hold for the
desync class to be closed:
1. close_event() write-path eviction (blackboard.py) -- SREM from both
   EVENT_ACTIVE and EVENT_WAITING_APPROVAL in a single WATCH/MULTI/EXEC
   alongside the CLOSED status write and EVENT_CLOSED zadd.
2. park_for_approval() CLOSED guard (blackboard.py) -- refuses to resurrect
   an already-closed event back into WAITING_APPROVAL.
3. GET /waiting_approval and GET /active route filtering (queue.py) --
   defensive read-time eviction of any zombie id (CLOSED or missing doc) in
   either set, symmetric halves of the same partial-close failure mode.
4. Brain._sweep_waiting_approval_zombies() (brain.py) -- periodic background
   self-heal for the same zombie class, across both EVENT_WAITING_APPROVAL
   and EVENT_ACTIVE.
5. WS broadcasts on park (handlers_state.py) and resume (brain.py), not just
   close, so the UI queue sidebar refreshes on every transition.
"""
from __future__ import annotations

import asyncio
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


def _make_event(event_id: str, status: EventStatus = EventStatus.ACTIVE, source: str = "chat") -> EventDocument:
    return EventDocument(
        id=event_id,
        source=source,
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
# 3b. GET /queue/active route filtering (symmetric EVENT_ACTIVE zombie path)
# =============================================================================


class TestActiveRouteFiltering:
    """A CLOSED-but-still-in-EVENT_ACTIVE id is the mirror-image zombie of a
    CLOSED-but-still-in-EVENT_WAITING_APPROVAL id -- both are possible outputs of a
    partially-applied close_event() and need the same defensive read-time eviction."""

    async def _get_active(self, mock_bb):
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
                    return await client.get("/queue/active")
            finally:
                dependencies._blackboard = original_bb

    @pytest.mark.asyncio
    async def test_active_route_drops_closed_zombie(self):
        """A legit ACTIVE event surfaces; a CLOSED zombie in EVENT_ACTIVE is dropped + SREM'd."""
        live = _make_event("evt-active-live01", status=EventStatus.ACTIVE)
        zombie = _make_event("evt-active-zombie01", status=EventStatus.CLOSED)

        mock_bb = AsyncMock()
        mock_bb.EVENT_ACTIVE = "darwin:event:active"
        mock_bb.redis = AsyncMock()
        mock_bb.get_active_events = AsyncMock(return_value=[live.id, zombie.id])
        mock_bb.get_event = AsyncMock(
            side_effect=lambda eid: {live.id: live, zombie.id: zombie}.get(eid)
        )

        resp = await self._get_active(mock_bb)

        assert resp.status_code == 200
        data = resp.json()
        assert [e["id"] for e in data] == [live.id]
        mock_bb.redis.srem.assert_awaited_once_with(mock_bb.EVENT_ACTIVE, zombie.id)

    @pytest.mark.asyncio
    async def test_active_route_drops_missing_event_doc(self):
        """An id whose event document no longer exists is evicted the same as a CLOSED one."""
        mock_bb = AsyncMock()
        mock_bb.EVENT_ACTIVE = "darwin:event:active"
        mock_bb.redis = AsyncMock()
        mock_bb.get_active_events = AsyncMock(return_value=["evt-active-ghost01"])
        mock_bb.get_event = AsyncMock(return_value=None)

        resp = await self._get_active(mock_bb)

        assert resp.status_code == 200
        assert resp.json() == []
        mock_bb.redis.srem.assert_awaited_once_with(mock_bb.EVENT_ACTIVE, "evt-active-ghost01")


# =============================================================================
# 4. Brain._sweep_waiting_approval_zombies reconciliation sweep
# =============================================================================


class TestSweepWaitingApprovalZombies:

    @pytest.mark.asyncio
    async def test_sweep_evicts_closed_and_missing_ids_only(self):
        """Exercises the REAL Brain._sweep_waiting_approval_zombies() body (not a
        re-implementation of its eviction logic) for exactly one iteration, across both
        EVENT_WAITING_APPROVAL and EVENT_ACTIVE. asyncio.sleep is patched to let the
        first call return normally (loop proceeds through its `if not self._running:
        break` post-sleep check and runs the real sweep body) and flips brain._running
        False on the second call, so the loop exits before a second iteration.
        """
        from src.agents.brain import Brain

        live_wa = _make_event("evt-live02", status=EventStatus.WAITING_APPROVAL)
        zombie_wa = _make_event("evt-zombie02", status=EventStatus.CLOSED)
        live_active = _make_event("evt-live03", status=EventStatus.ACTIVE)
        zombie_active = _make_event("evt-zombie03", status=EventStatus.CLOSED)

        docs = {
            live_wa.id: live_wa,
            zombie_wa.id: zombie_wa,
            "evt-ghost02": None,
            live_active.id: live_active,
            zombie_active.id: zombie_active,
        }

        bb = MagicMock()
        bb.EVENT_WAITING_APPROVAL = "darwin:event:waiting_approval"
        bb.EVENT_ACTIVE = "darwin:event:active"
        bb.redis = MagicMock()
        bb.redis.srem = AsyncMock()
        bb.get_waiting_approval_events = AsyncMock(
            return_value=[live_wa.id, zombie_wa.id, "evt-ghost02"]
        )
        bb.get_active_events = AsyncMock(return_value=[live_active.id, zombie_active.id])
        bb.get_event = AsyncMock(side_effect=lambda eid: docs.get(eid))

        brain = Brain(blackboard=bb, agents={})
        brain._running = True

        sleep_calls = {"n": 0}

        async def _stop_after_one_iteration(_seconds):
            sleep_calls["n"] += 1
            if sleep_calls["n"] >= 2:
                brain._running = False

        with patch("src.agents.brain.asyncio.sleep", side_effect=_stop_after_one_iteration):
            await asyncio.wait_for(
                brain._sweep_waiting_approval_zombies(interval=0.01), timeout=1.0
            )

        bb.get_waiting_approval_events.assert_awaited_once()
        bb.get_active_events.assert_awaited_once()
        srem_calls = {c.args[1] for c in bb.redis.srem.await_args_list}
        assert srem_calls == {zombie_wa.id, "evt-ghost02", zombie_active.id}
        # Live ids in either set must never be touched.
        assert live_wa.id not in srem_calls
        assert live_active.id not in srem_calls

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
        from src.agents.brain import Brain

        bb = MagicMock()
        bb.get_waiting_approval_events = AsyncMock(return_value=[])

        brain = Brain(blackboard=bb, agents={})
        brain._running = False  # loop condition checked before the first sleep

        # Should return almost immediately -- the `while self._running` guard is False.
        await asyncio.wait_for(brain._sweep_waiting_approval_zombies(interval=0.01), timeout=1.0)
        bb.get_waiting_approval_events.assert_not_awaited()


# =============================================================================
# 5. WS broadcasts on park / resume transitions (not just close)
# =============================================================================


class _FakeParkToolContext:
    """Minimal ToolContext stand-in for handle_request_user_approval -- implements only
    the methods that handler actually calls, backed by a real (fakeredis) BlackboardState."""

    def __init__(self, bb: BlackboardState):
        self._bb = bb
        self.broadcast = AsyncMock()
        self.append_and_broadcast = AsyncMock(return_value=1)
        self.idle_timeout = MagicMock(schedule=MagicMock())

    def mark_waiting_for_user(self, event_id: str) -> None:
        pass

    async def next_turn_number(self, event_id: str) -> int:
        return 2

    def get_blackboard(self) -> BlackboardState:
        return self._bb

    def get_idle_timeout(self):
        return self.idle_timeout

    def get_conversation_timeout(self, event) -> int:
        """Distinct from get_approval_timeout so tests can prove which one a
        call-site actually uses."""
        return 300

    def get_approval_timeout(self, event) -> int:
        return 5400


class TestParkAndResumeBroadcasts:

    @pytest.mark.asyncio
    async def test_park_broadcasts_event_status_changed_waiting_approval(self, bb):
        """handle_request_user_approval must broadcast the park transition, not just
        append_and_broadcast the request_approval turn -- the UI queue sidebar only
        listens for event_status_changed/event_closed, not arbitrary turn actions."""
        from src.agents.handlers_state import handle_request_user_approval

        event = _make_event("evt-park-broadcast01", status=EventStatus.ACTIVE)
        await _seed(bb, event)
        await bb.redis.sadd(bb.EVENT_ACTIVE, event.id)
        ctx = _FakeParkToolContext(bb)

        await handle_request_user_approval(ctx, event.id, {"plan_summary": "test"}, None)

        ctx.broadcast.assert_awaited_once_with({
            "type": "event_status_changed",
            "event_id": event.id,
            "status": "waiting_approval",
        })

    @pytest.mark.asyncio
    async def test_park_skips_broadcast_when_close_race_wins(self, bb):
        """If the event was closed concurrently just before parking, park_for_approval()
        no-ops (CLOSED guard) and the handler must not announce a park that didn't happen."""
        from src.agents.handlers_state import handle_request_user_approval

        event = _make_event("evt-park-broadcast02", status=EventStatus.ACTIVE)
        await _seed(bb, event)
        await bb.redis.sadd(bb.EVENT_ACTIVE, event.id)
        await bb.close_event(event.id, "closed mid-flight", close_reason="user_closed")
        ctx = _FakeParkToolContext(bb)

        await handle_request_user_approval(ctx, event.id, {"plan_summary": "test"}, None)

        ctx.broadcast.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_resume_broadcasts_event_status_changed_active(self, bb):
        """resume_if_parked() must broadcast the resume transition symmetrically to park."""
        from src.agents.brain import Brain

        event = _make_event("evt-resume-broadcast01", status=EventStatus.WAITING_APPROVAL)
        await _seed(bb, event)
        await bb.redis.sadd(bb.EVENT_WAITING_APPROVAL, event.id)

        mock_broadcast = AsyncMock()
        brain = Brain(blackboard=bb, agents={}, broadcast=mock_broadcast)

        resumed = await brain.resume_if_parked(event.id)

        assert resumed is True
        mock_broadcast.assert_awaited_once_with({
            "type": "event_status_changed",
            "event_id": event.id,
            "status": "active",
        })


# =============================================================================
# 6. Idle timer scheduled with the extended approval timeout, not the
#    generic conversation timeout, at the two approval-park sites.
# =============================================================================


class TestApprovalParkUsesApprovalTimeout:

    @pytest.mark.asyncio
    async def test_request_user_approval_schedules_with_approval_timeout(self, bb):
        """handle_request_user_approval must arm the idle timer with
        get_approval_timeout(), not the shorter get_conversation_timeout()."""
        from src.agents.handlers_state import handle_request_user_approval

        event = _make_event("evt-approval-timeout01", status=EventStatus.ACTIVE)
        await _seed(bb, event)
        await bb.redis.sadd(bb.EVENT_ACTIVE, event.id)
        ctx = _FakeParkToolContext(bb)

        await handle_request_user_approval(ctx, event.id, {"plan_summary": "test"}, None)

        ctx.idle_timeout.schedule.assert_called_once_with(event.id, warning_sec=5400)

    @pytest.mark.asyncio
    async def test_wait_for_user_schedules_with_approval_timeout(self, bb):
        """handle_wait_for_user (which leaves the event ACTIVE, not WAITING_APPROVAL)
        must also arm the idle timer with get_approval_timeout() -- it's this
        extended timeout, not StalenessGuard[chat], that is its sole backstop."""
        from src.agents.handlers_state import handle_wait_for_user

        event = _make_event("evt-approval-timeout02", status=EventStatus.ACTIVE)
        await _seed(bb, event)
        await bb.redis.sadd(bb.EVENT_ACTIVE, event.id)
        ctx = _FakeParkToolContext(bb)

        await handle_wait_for_user(ctx, event.id, {"summary": "waiting on user"}, None)

        ctx.idle_timeout.schedule.assert_called_once_with(event.id, warning_sec=5400)

    @pytest.mark.asyncio
    async def test_wait_for_user_rejected_for_automated_source_no_timer(self, bb):
        """Automated sources (e.g. headhunter/aligner) never reach the idle-timer
        call at all -- wait_for_user is chat/slack-only. Regression guard for the
        '#5 automated sources must remain untouched' requirement."""
        from src.agents.handlers_state import handle_wait_for_user

        event = _make_event("evt-automated01", status=EventStatus.ACTIVE, source="headhunter")
        await _seed(bb, event)
        await bb.redis.sadd(bb.EVENT_ACTIVE, event.id)
        ctx = _FakeParkToolContext(bb)

        await handle_wait_for_user(ctx, event.id, {"summary": "n/a"}, None)

        ctx.idle_timeout.schedule.assert_not_called()
