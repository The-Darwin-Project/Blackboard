# tests/test_staleness_guard.py
# @ai-rules:
# 1. [Constraint]: No Redis -- all tests use mocked blackboard and Brain state.
# 2. [Pattern]: Tests are isolated; each test rebuilds Brain partial state (no full start_event_loop).
# 3. [Gotcha]: CHAT_STALE_TTL env var controls TTL -- monkeypatch it to a short value for fast tests.
"""
Tests for the chat/slack StalenessGuard implementation (feat/evt-6c1f25f5).

Prioritized scenarios (from Brain/JARVIS alignment):
  1. Timer resets on active user engagement just before the 90-minute threshold.
  2. stale_close_count increments ONLY when a genuinely stale event is closed.
  3. All observability metrics (sweep_count, last_sweep_duration, error_count) update correctly.
"""
from __future__ import annotations

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.models import (
    ConversationTurn,
    EventDocument,
    EventEvidence,
    EventInput,
    EventStatus,
    FlowMetricsResponse,
)
from src.scheduling.triggers import StalenessGuard


# =============================================================================
# Helpers
# =============================================================================

TTL = 5400  # 90 minutes in seconds


def _make_event(
    event_id: str = "evt-chat",
    source: str = "slack",
    status: EventStatus = EventStatus.WAITING_APPROVAL,
    last_turn_age_seconds: float = 5401.0,  # stale by default
) -> EventDocument:
    """Build an EventDocument whose last conversation turn is `last_turn_age_seconds` old."""
    evidence = EventEvidence(
        display_text="test", source_type=source, domain="clear", severity="info",
    )
    event_input = EventInput(reason="hei", evidence=evidence, timeDate="2026-01-01T00:00:00Z")
    turn = ConversationTurn(
        turn=1,
        actor="brain",
        action="request_approval",
        timestamp=time.time() - last_turn_age_seconds,
    )
    return EventDocument(
        id=event_id,
        source=source,
        status=status,
        service="general",
        event=event_input,
        conversation=[turn],
    )


def _make_brain_with_event(
    event: EventDocument,
    in_waiting_for_user: bool = True,
) -> MagicMock:
    """Build a minimal Brain mock exposing only what _check_chat_staleness needs."""
    brain = MagicMock()
    brain._waiting_for_user = {event.id} if in_waiting_for_user else set()
    brain.blackboard = MagicMock()
    brain.blackboard.get_event = AsyncMock(return_value=event)
    brain._close_and_broadcast = AsyncMock()
    return brain


# =============================================================================
# 1. Timer-reset: active user engagement just before threshold
# =============================================================================


class TestChatStalenessCheckTimerReset:
    """_check_chat_staleness uses the last conversation turn timestamp as the staleness anchor.

    A new turn added by the user just before the 90-minute mark resets the window --
    the event must NOT be closed prematurely.
    """

    @pytest.mark.asyncio
    async def test_event_not_stale_one_second_before_threshold(self, monkeypatch):
        """Event whose last turn is 89m 59s old (1s before TTL) must NOT be stale."""
        monkeypatch.setenv("CHAT_STALE_TTL", str(TTL))
        event = _make_event(last_turn_age_seconds=TTL - 1)
        brain = _make_brain_with_event(event)

        from src.agents.brain import Brain
        result = await Brain._check_chat_staleness(brain, event.id)

        assert result is False, "Event should NOT be stale 1s before the TTL boundary"

    @pytest.mark.asyncio
    async def test_event_stale_one_second_after_threshold(self, monkeypatch):
        """Event whose last turn is 90m 1s old (1s after TTL) must be stale."""
        monkeypatch.setenv("CHAT_STALE_TTL", str(TTL))
        event = _make_event(last_turn_age_seconds=TTL + 1)
        brain = _make_brain_with_event(event)

        from src.agents.brain import Brain
        result = await Brain._check_chat_staleness(brain, event.id)

        assert result is True, "Event should be stale 1s after the TTL boundary"

    @pytest.mark.asyncio
    async def test_new_turn_added_just_before_threshold_resets_timer(self, monkeypatch):
        """Simulates a user responding at T-89m59s: last turn is fresh → not stale."""
        monkeypatch.setenv("CHAT_STALE_TTL", str(TTL))

        # Event was originally created 95 minutes ago, but the user sent a message
        # at 89 minutes 59 seconds ago (just before the 90-minute deadline).
        event = _make_event(last_turn_age_seconds=TTL - 1)

        # Add the original old turn to the conversation to show the event has history
        old_turn = ConversationTurn(
            turn=0, actor="brain", action="response",
            timestamp=time.time() - (TTL + 300),  # 5 minutes beyond TTL (stale)
        )
        # The last turn is the fresh one (TTL - 1 seconds old) added in _make_event
        event.conversation.insert(0, old_turn)

        brain = _make_brain_with_event(event)

        from src.agents.brain import Brain
        result = await Brain._check_chat_staleness(brain, event.id)

        assert result is False, (
            "After user activity just before threshold, event must NOT be stale "
            "(last turn timestamp is the anchor, not queued_at)"
        )

    @pytest.mark.asyncio
    async def test_event_not_in_waiting_for_user_returns_false(self, monkeypatch):
        """Events NOT in _waiting_for_user are never stale (fast-path guard)."""
        monkeypatch.setenv("CHAT_STALE_TTL", str(TTL))
        event = _make_event(last_turn_age_seconds=TTL + 3600)  # very stale
        brain = _make_brain_with_event(event, in_waiting_for_user=False)

        from src.agents.brain import Brain
        result = await Brain._check_chat_staleness(brain, event.id)

        assert result is False

    @pytest.mark.asyncio
    async def test_headhunter_source_not_closed(self, monkeypatch):
        """Non-chat sources (headhunter) must be ignored even when past TTL."""
        monkeypatch.setenv("CHAT_STALE_TTL", str(TTL))
        event = _make_event(source="headhunter", last_turn_age_seconds=TTL + 3600)
        brain = _make_brain_with_event(event)

        from src.agents.brain import Brain
        result = await Brain._check_chat_staleness(brain, event.id)

        assert result is False, "Only chat/slack sources should trigger the TTL"

    @pytest.mark.asyncio
    async def test_deferred_status_not_closed(self, monkeypatch):
        """Events with DEFERRED status are exempt (they have their own re-activation path)."""
        monkeypatch.setenv("CHAT_STALE_TTL", str(TTL))
        event = _make_event(status=EventStatus.DEFERRED, last_turn_age_seconds=TTL + 3600)
        brain = _make_brain_with_event(event)

        from src.agents.brain import Brain
        result = await Brain._check_chat_staleness(brain, event.id)

        assert result is False, "DEFERRED events must not be closed by the chat guard"

    @pytest.mark.asyncio
    async def test_event_with_no_turns_not_stale(self, monkeypatch):
        """Events with empty conversation (no timestamp anchor) must not be closed."""
        monkeypatch.setenv("CHAT_STALE_TTL", str(TTL))
        event = _make_event()
        event.conversation = []  # no turns → last_turn_ts = 0.0 → returns False
        brain = _make_brain_with_event(event)

        from src.agents.brain import Brain
        result = await Brain._check_chat_staleness(brain, event.id)

        assert result is False, "No conversation turns → cannot determine staleness → must not close"


# =============================================================================
# 2. close_stale_chat_event — correct cleanup
# =============================================================================


class TestCloseStaleChat:
    """_close_stale_chat_event must discard event from _waiting_for_user before closing."""

    @pytest.mark.asyncio
    async def test_close_removes_from_waiting_for_user(self, monkeypatch):
        """After closure, event_id must not remain in _waiting_for_user."""
        event = _make_event()
        brain = _make_brain_with_event(event)

        from src.agents.brain import Brain
        await Brain._close_stale_chat_event(brain, event.id)

        assert event.id not in brain._waiting_for_user
        brain._close_and_broadcast.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_close_calls_broadcast_with_timeout_reason(self):
        """Closure must use close_reason='timeout' so journal and Slack get the right context."""
        event = _make_event()
        brain = _make_brain_with_event(event)

        from src.agents.brain import Brain
        await Brain._close_stale_chat_event(brain, event.id)

        _, kwargs = brain._close_and_broadcast.call_args
        assert kwargs.get("close_reason") == "timeout"


# =============================================================================
# 3. StalenessGuard metrics: stale_close_count, sweep counters, error_count
# =============================================================================


class TestStalenessGuardMetrics:
    """Verify that StalenessGuard observability counters update correctly."""

    def _make_scheduler(self, event_ids: list[str]) -> MagicMock:
        sched = MagicMock()
        sched.tracked_event_ids = MagicMock(return_value=set(event_ids))
        return sched

    @pytest.mark.asyncio
    async def test_stale_close_count_increments_only_for_stale_events(self):
        """stale_close_count must increment only when check_fn returns True."""
        stale_id = "evt-stale"
        fresh_id = "evt-fresh"

        async def check_fn(eid: str) -> bool:
            return eid == stale_id  # only stale_id is stale

        on_stale = AsyncMock()
        guard = StalenessGuard(check_fn=check_fn, on_stale=on_stale, interval=0.01, name="test")
        scheduler = self._make_scheduler([stale_id, fresh_id])

        # Run one sweep (drive start() through exactly one sleep+iteration)
        async def run_one_sweep():
            task = asyncio.create_task(guard.start(scheduler))
            await asyncio.sleep(0.05)  # let one interval elapse
            guard._running = False
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        await run_one_sweep()

        metrics = guard.metrics()
        # stale_close_count is cumulative; multiple sweeps may run — assert >= 1
        assert metrics["stale_close_count"] >= 1, (
            f"Expected stale_close_count>=1 (stale_id was stale), got {metrics['stale_close_count']}"
        )
        assert metrics["sweep_count"] >= 1
        # Key invariant: on_stale must NEVER have been called with fresh_id
        for call in on_stale.await_args_list:
            assert call.args[0] != fresh_id, (
                f"on_stale was called with fresh_id — non-stale event was incorrectly closed"
            )
        # And must have been called at least once with stale_id
        assert any(call.args[0] == stale_id for call in on_stale.await_args_list), (
            f"on_stale was never called with stale_id"
        )

    @pytest.mark.asyncio
    async def test_stale_close_count_zero_when_no_stale_events(self):
        """stale_close_count stays 0 when no events are stale."""
        async def check_fn(eid: str) -> bool:
            return False

        on_stale = AsyncMock()
        guard = StalenessGuard(check_fn=check_fn, on_stale=on_stale, interval=0.01, name="test")
        scheduler = self._make_scheduler(["evt-a", "evt-b", "evt-c"])

        async def run_one_sweep():
            task = asyncio.create_task(guard.start(scheduler))
            await asyncio.sleep(0.05)
            guard._running = False
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        await run_one_sweep()

        metrics = guard.metrics()
        assert metrics["stale_close_count"] == 0
        on_stale.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_sweep_count_and_last_sweep_at_update_after_each_sweep(self):
        """sweep_count increments and last_sweep_at is set after each sweep."""
        async def check_fn(eid: str) -> bool:
            return False

        guard = StalenessGuard(check_fn=check_fn, on_stale=AsyncMock(), interval=0.01, name="test")
        scheduler = self._make_scheduler(["evt-1"])

        before = time.time()

        async def run_two_sweeps():
            task = asyncio.create_task(guard.start(scheduler))
            await asyncio.sleep(0.08)  # two intervals at 0.01s + slack
            guard._running = False
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        await run_two_sweeps()

        metrics = guard.metrics()
        assert metrics["sweep_count"] >= 2, f"Expected >= 2 sweeps, got {metrics['sweep_count']}"
        assert metrics["last_sweep_at"] >= before, "last_sweep_at must be set after first sweep"

    @pytest.mark.asyncio
    async def test_last_sweep_duration_is_non_negative(self):
        """last_sweep_duration must be >= 0 after a sweep completes."""
        async def check_fn(eid: str) -> bool:
            return False

        guard = StalenessGuard(check_fn=check_fn, on_stale=AsyncMock(), interval=0.01, name="test")
        scheduler = self._make_scheduler(["evt-x"])

        async def run_one_sweep():
            task = asyncio.create_task(guard.start(scheduler))
            await asyncio.sleep(0.05)
            guard._running = False
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        await run_one_sweep()

        metrics = guard.metrics()
        assert metrics["last_sweep_duration"] >= 0.0

    @pytest.mark.asyncio
    async def test_error_count_increments_on_check_fn_exception(self):
        """Errors in check_fn must increment error_count and not crash the guard."""
        async def check_fn_raises(eid: str) -> bool:
            raise RuntimeError("simulated blackboard error")

        guard = StalenessGuard(
            check_fn=check_fn_raises, on_stale=AsyncMock(), interval=0.01, name="test"
        )
        scheduler = self._make_scheduler(["evt-err"])

        async def run_one_sweep():
            task = asyncio.create_task(guard.start(scheduler))
            await asyncio.sleep(0.05)
            guard._running = False
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        await run_one_sweep()

        metrics = guard.metrics()
        assert metrics["error_count"] >= 1, (
            f"error_count should be >= 1 after check_fn raised, got {metrics['error_count']}"
        )

    @pytest.mark.asyncio
    async def test_stale_close_count_accumulates_across_sweeps(self):
        """stale_close_count is cumulative: 1 stale event per sweep → count equals sweep_count."""
        async def check_fn(eid: str) -> bool:
            return True  # always stale

        guard = StalenessGuard(
            check_fn=check_fn, on_stale=AsyncMock(), interval=0.01, name="test"
        )
        scheduler = self._make_scheduler(["evt-always-stale"])

        async def run_three_sweeps():
            task = asyncio.create_task(guard.start(scheduler))
            await asyncio.sleep(0.12)  # ~3+ intervals
            guard._running = False
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        await run_three_sweeps()

        metrics = guard.metrics()
        assert metrics["stale_close_count"] == metrics["sweep_count"], (
            f"stale_close_count ({metrics['stale_close_count']}) should equal "
            f"sweep_count ({metrics['sweep_count']}) when all events are always stale"
        )

    def test_metrics_dict_has_all_required_keys(self):
        """metrics() must return all expected observability keys."""
        guard = StalenessGuard(
            check_fn=AsyncMock(return_value=False),
            on_stale=AsyncMock(),
            name="chat",
        )
        m = guard.metrics()
        expected_keys = {
            "name",
            "last_sweep_at",
            "last_sweep_duration",
            "sweep_count",
            "stale_close_count",
            "error_count",
        }
        assert expected_keys <= set(m.keys()), (
            f"Missing metrics keys: {expected_keys - set(m.keys())}"
        )
        assert m["name"] == "chat"

    def test_metrics_initial_values_are_zero(self):
        """Before any sweeps, all counters must be zero / falsy."""
        guard = StalenessGuard(
            check_fn=AsyncMock(return_value=False),
            on_stale=AsyncMock(),
            name="jarvis",
        )
        m = guard.metrics()
        assert m["sweep_count"] == 0
        assert m["stale_close_count"] == 0
        assert m["error_count"] == 0
        assert m["last_sweep_at"] == 0.0
        assert m["last_sweep_duration"] == 0.0


# =============================================================================
# 4. FlowMetricsResponse model includes staleness_guards field
# =============================================================================


class TestFlowMetricsResponseModel:
    """Verify the /flow response model carries the staleness_guards field."""

    def test_staleness_guards_field_defaults_to_empty_list(self):
        """FlowMetricsResponse must default staleness_guards to [] for backward compat."""
        resp = FlowMetricsResponse()
        assert hasattr(resp, "staleness_guards")
        assert resp.staleness_guards == []

    def test_staleness_guards_field_accepts_list_of_dicts(self):
        """staleness_guards must accept a list of metric dicts from guard.metrics()."""
        guard_metrics = {
            "name": "chat",
            "last_sweep_at": 1716220000.0,
            "last_sweep_duration": 0.002,
            "sweep_count": 10,
            "stale_close_count": 2,
            "error_count": 0,
        }
        resp = FlowMetricsResponse(staleness_guards=[guard_metrics])
        assert len(resp.staleness_guards) == 1
        assert resp.staleness_guards[0]["name"] == "chat"
        assert resp.staleness_guards[0]["stale_close_count"] == 2

    def test_staleness_guards_for_both_jarvis_and_chat_guards(self):
        """Both jarvis and chat guards should appear in the response."""
        guards = [
            {"name": "jarvis", "stale_close_count": 0, "sweep_count": 5,
             "last_sweep_at": 1716220100.0, "last_sweep_duration": 0.001, "error_count": 0},
            {"name": "chat", "stale_close_count": 1, "sweep_count": 2,
             "last_sweep_at": 1716220200.0, "last_sweep_duration": 0.003, "error_count": 0},
        ]
        resp = FlowMetricsResponse(staleness_guards=guards)
        names = {g["name"] for g in resp.staleness_guards}
        assert "jarvis" in names
        assert "chat" in names
