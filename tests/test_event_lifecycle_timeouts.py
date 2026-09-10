# tests/test_event_lifecycle_timeouts.py
# @ai-rules:
# 1. [Pattern]: Tests for idle timeout, on-ice transitions, thaw, and race guard.
# 2. [Constraint]: All Brain interactions use mocks -- no Redis, no LLM calls.
"""
Unit tests for Event Lifecycle Timeouts:
- IdleTimeoutManager (warn + close flow, cancel, race guard)
- On-ice transitions (freeze, thaw, guard policy)
- _waiting_for_user dict semantics
"""
from __future__ import annotations

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.models import ConversationTurn, EventDocument, EventInput, EventStatus, EventEvidence
from src.scheduling.idle_timeout import IdleTimeoutManager


# =============================================================================
# Helpers
# =============================================================================


def _make_event(
    event_id: str = "evt-test",
    source: str = "chat",
    status: EventStatus = EventStatus.ACTIVE,
) -> EventDocument:
    return EventDocument(
        id=event_id,
        source=source,
        service="test-svc",
        status=status,
        brain_phase="triage",
        event=EventInput(
            reason="Test event",
            evidence=EventEvidence(
                display_text="test", source_type=source,
                domain="complicated", severity="info",
            ),
        ),
    )


# =============================================================================
# 1. IdleTimeoutManager
# =============================================================================


class TestIdleTimeoutManager:

    @pytest.mark.asyncio
    async def test_warn_then_close_fires(self):
        """Timer fires warn, then close callback."""
        warned = []
        closed = []

        async def warn(eid: str) -> None:
            warned.append(eid)

        async def close(eid: str) -> None:
            closed.append(eid)

        with patch.dict("os.environ", {"IDLE_TIMEOUT_WARNING_SEC": "0", "IDLE_TIMEOUT_CLOSE_SEC": "0"}):
            mgr = IdleTimeoutManager(warn_callback=warn, close_callback=close)

        mgr.schedule("evt-1")
        await asyncio.sleep(0.1)
        assert "evt-1" in warned
        assert "evt-1" in closed

    @pytest.mark.asyncio
    async def test_cancel_prevents_callbacks(self):
        """Cancelling a timer prevents both warn and close."""
        warned = []
        closed = []

        async def warn(eid: str) -> None:
            warned.append(eid)

        async def close(eid: str) -> None:
            closed.append(eid)

        with patch.dict("os.environ", {"IDLE_TIMEOUT_WARNING_SEC": "10", "IDLE_TIMEOUT_CLOSE_SEC": "10"}):
            mgr = IdleTimeoutManager(warn_callback=warn, close_callback=close)

        mgr.schedule("evt-1")
        assert mgr.has_timer("evt-1")
        mgr.cancel("evt-1")
        assert not mgr.has_timer("evt-1")
        await asyncio.sleep(0.1)
        assert warned == []
        assert closed == []

    @pytest.mark.asyncio
    async def test_reschedule_resets_timer(self):
        """Calling schedule again cancels old timer and starts new one."""
        call_count = []

        async def warn(eid: str) -> None:
            call_count.append("warn")

        async def close(eid: str) -> None:
            call_count.append("close")

        with patch.dict("os.environ", {"IDLE_TIMEOUT_WARNING_SEC": "0", "IDLE_TIMEOUT_CLOSE_SEC": "0"}):
            mgr = IdleTimeoutManager(warn_callback=warn, close_callback=close)

        mgr.schedule("evt-1")
        mgr.schedule("evt-1")  # reschedule
        await asyncio.sleep(0.1)
        # Should only fire once (old timer cancelled)
        assert call_count.count("warn") == 1
        assert call_count.count("close") == 1


# =============================================================================
# 2. On-ice transitions (blackboard freeze/thaw)
# =============================================================================


class TestApprovalParkingTransitions:

    @pytest.mark.asyncio
    async def test_park_for_approval_moves_to_waiting_approval_set(self):
        """park_for_approval atomically moves event from active to waiting_approval."""
        from src.state.blackboard import BlackboardState
        event = _make_event()
        bb = MagicMock(spec=BlackboardState)
        bb.park_for_approval = AsyncMock()

        await bb.park_for_approval("evt-test")
        bb.park_for_approval.assert_awaited_once_with("evt-test")

    @pytest.mark.asyncio
    async def test_resume_from_approval_moves_back_to_active(self):
        """resume_from_approval atomically moves event from waiting_approval back to active."""
        from src.state.blackboard import BlackboardState
        bb = MagicMock(spec=BlackboardState)
        bb.resume_from_approval = AsyncMock()

        await bb.resume_from_approval("evt-test")
        bb.resume_from_approval.assert_awaited_once_with("evt-test")


# =============================================================================
# 4. Race guard (idle timeout close aborted if user responded)
# =============================================================================


class TestIdleTimeoutRaceGuard:

    @pytest.mark.asyncio
    async def test_close_aborted_when_not_waiting(self):
        """If user responded during the 5-min close window, close is aborted."""
        from src.agents.brain import Brain
        brain = MagicMock()
        brain._waiting_for_user = {}  # user already responded
        brain._close_and_broadcast = AsyncMock()

        await Brain._idle_timeout_close(brain, "evt-test")
        brain._close_and_broadcast.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_close_proceeds_when_still_waiting(self):
        """If user hasn't responded and the event isn't WAITING_APPROVAL, close proceeds."""
        from src.agents.brain import Brain
        brain = MagicMock()
        brain._waiting_for_user = {"evt-test": time.time() - 900}
        brain.blackboard = MagicMock()
        brain.blackboard.get_event = AsyncMock(return_value=_make_event(status=EventStatus.ACTIVE))
        brain._close_and_broadcast = AsyncMock()

        await Brain._idle_timeout_close(brain, "evt-test")
        brain._close_and_broadcast.assert_awaited_once()
        assert "evt-test" not in brain._waiting_for_user

    @pytest.mark.asyncio
    async def test_close_skipped_when_waiting_approval(self):
        """WAITING_APPROVAL events are not closed by the short idle timer -- StalenessGuard[chat]
        (CHAT_STALE_TTL) owns them instead. _waiting_for_user must stay populated so that guard
        can still see and act on the event."""
        from src.agents.brain import Brain
        brain = MagicMock()
        brain._waiting_for_user = {"evt-test": time.time() - 900}
        brain.blackboard = MagicMock()
        brain.blackboard.get_event = AsyncMock(
            return_value=_make_event(status=EventStatus.WAITING_APPROVAL)
        )
        brain._close_and_broadcast = AsyncMock()

        await Brain._idle_timeout_close(brain, "evt-test")
        brain._close_and_broadcast.assert_not_awaited()
        assert "evt-test" in brain._waiting_for_user

    @pytest.mark.asyncio
    async def test_close_proceeds_when_event_missing(self):
        """A vanished event (e.g. expired Redis key) falls through to the normal close path
        rather than being silently skipped."""
        from src.agents.brain import Brain
        brain = MagicMock()
        brain._waiting_for_user = {"evt-test": time.time() - 900}
        brain.blackboard = MagicMock()
        brain.blackboard.get_event = AsyncMock(return_value=None)
        brain._close_and_broadcast = AsyncMock()

        await Brain._idle_timeout_close(brain, "evt-test")
        brain._close_and_broadcast.assert_awaited_once()
        assert "evt-test" not in brain._waiting_for_user


# =============================================================================
# 4b. Approval timeout env var (IDLE_TIMEOUT_APPROVAL_SEC)
# =============================================================================


class TestApprovalTimeout:

    def test_default_is_5400_seconds(self):
        """Default approval timeout is 5400s (matches CHAT_STALE_TTL)."""
        from src.agents.brain import Brain
        event = _make_event()
        with patch.dict("os.environ", {}, clear=False):
            import os
            os.environ.pop("IDLE_TIMEOUT_APPROVAL_SEC", None)
            assert Brain._get_approval_timeout(MagicMock(), event) == 5400

    def test_respects_env_override(self):
        """IDLE_TIMEOUT_APPROVAL_SEC overrides the default."""
        from src.agents.brain import Brain
        event = _make_event()
        with patch.dict("os.environ", {"IDLE_TIMEOUT_APPROVAL_SEC": "120"}):
            assert Brain._get_approval_timeout(MagicMock(), event) == 120

    def test_longer_than_conversation_timeout(self):
        """The approval timeout must exceed the casual/conversation timeout, or approval
        parks get no benefit over a casual pause."""
        from src.agents.brain import Brain
        event = _make_event()
        with patch.dict("os.environ", {}, clear=False):
            import os
            os.environ.pop("IDLE_TIMEOUT_APPROVAL_SEC", None)
            os.environ.pop("IDLE_TIMEOUT_CONVERSATION_SEC", None)
            approval = Brain._get_approval_timeout(MagicMock(), event)
            conversation = Brain._get_conversation_timeout(MagicMock(), event)
            assert approval > conversation


# =============================================================================
# 4c. End-to-end: idle guard defers to StalenessGuard[chat] for real closure
# =============================================================================


class TestApprovalParkSurvivesIdleThenStalenessCloses:
    """Ties Guard A (IdleTimeoutManager + _idle_timeout_close) and Guard B
    (_check_chat_staleness / _close_stale_chat_event) together end-to-end, at an
    accelerated timescale, to prove the actual production sequencing from
    evt-321b0b68: a WAITING_APPROVAL event survives the short idle-close attempt,
    and is only closed once by the staleness guard once it is genuinely stale."""

    @pytest.mark.asyncio
    async def test_real_timer_skips_close_while_waiting_approval_then_staleness_closes(self):
        from src.agents.brain import Brain

        event = _make_event(status=EventStatus.WAITING_APPROVAL)
        # Last turn far enough in the past that a tiny CHAT_STALE_TTL is already exceeded.
        event.conversation = [
            ConversationTurn(turn=1, actor="brain", action="request_approval",
                              timestamp=time.time() - 3600)
        ]

        brain = MagicMock()
        brain._waiting_for_user = {event.id: time.time() - 3600}
        brain.blackboard = MagicMock()
        brain.blackboard.get_event = AsyncMock(return_value=event)
        brain._close_and_broadcast = AsyncMock()

        # --- Guard A: the real IdleTimeoutManager, driving the real bound
        # _idle_timeout_close, at a millisecond timescale standing in for the
        # ~20 minute production warn->close window.
        with patch.dict("os.environ", {"IDLE_TIMEOUT_CLOSE_SEC": "0"}):
            mgr = IdleTimeoutManager(
                warn_callback=AsyncMock(),
                close_callback=lambda eid: Brain._idle_timeout_close(brain, eid),
            )
        mgr.schedule(event.id, warning_sec=0.01)
        await asyncio.sleep(0.15)

        # The event survived: still WAITING_APPROVAL, never closed, and still
        # tracked in _waiting_for_user so Guard B can see it.
        brain._close_and_broadcast.assert_not_awaited()
        assert event.id in brain._waiting_for_user

        # --- Guard B: StalenessGuard[chat]'s real check+close pair now takes
        # over, using a tiny CHAT_STALE_TTL to stand in for the ~90 minute
        # production threshold. The pre-seeded conversation turn (1hr old) is
        # already past it.
        with patch.dict("os.environ", {"CHAT_STALE_TTL": "1"}):
            is_stale = await Brain._check_chat_staleness(brain, event.id)
        assert is_stale is True

        await Brain._close_stale_chat_event(brain, event.id)
        brain._close_and_broadcast.assert_awaited_once_with(
            event.id,
            summary="Chat session timed out waiting for user approval",
            close_reason="timeout",
        )
        assert event.id not in brain._waiting_for_user

    @pytest.mark.asyncio
    async def test_staleness_guard_does_not_fire_before_ttl_elapsed(self):
        """Guard B must not consider a freshly-parked WAITING_APPROVAL event stale --
        only genuinely abandoned events (past CHAT_STALE_TTL since the last turn) trigger it."""
        from src.agents.brain import Brain

        event = _make_event(status=EventStatus.WAITING_APPROVAL)
        event.conversation = [
            ConversationTurn(turn=1, actor="brain", action="request_approval",
                              timestamp=time.time())  # just parked
        ]
        brain = MagicMock()
        brain._waiting_for_user = {event.id: time.time()}
        brain.blackboard = MagicMock()
        brain.blackboard.get_event = AsyncMock(return_value=event)

        with patch.dict("os.environ", {"CHAT_STALE_TTL": "5400"}):
            is_stale = await Brain._check_chat_staleness(brain, event.id)
        assert is_stale is False


# =============================================================================
# 5. Thaw mechanism
# =============================================================================


class TestResumeIfParked:

    @pytest.mark.asyncio
    async def test_resume_parked_event(self):
        """resume_if_parked returns True, re-enqueues, and broadcasts the resume transition
        for waiting_approval events (event_status_changed -- #240: the UI queue sidebar
        must refresh on resume, not just on close)."""
        from src.agents.brain import Brain
        event = _make_event(status=EventStatus.WAITING_APPROVAL)
        brain = MagicMock()
        brain.blackboard = MagicMock()
        brain.blackboard.get_event = AsyncMock(return_value=event)
        brain.blackboard.resume_from_approval = AsyncMock()
        brain._scheduler = MagicMock()
        brain._scheduler.enqueue = MagicMock(return_value=True)
        brain._broadcast = AsyncMock()

        result = await Brain.resume_if_parked(brain, "evt-test")
        assert result is True
        brain.blackboard.resume_from_approval.assert_awaited_once_with("evt-test")
        brain._scheduler.enqueue.assert_called_once_with("evt-test")
        brain._broadcast.assert_awaited_once_with({
            "type": "event_status_changed",
            "event_id": "evt-test",
            "status": "active",
        })

    @pytest.mark.asyncio
    async def test_no_resume_for_active_event(self):
        """resume_if_parked returns False for non-waiting_approval events."""
        from src.agents.brain import Brain
        event = _make_event(status=EventStatus.ACTIVE)
        brain = MagicMock()
        brain.blackboard = MagicMock()
        brain.blackboard.get_event = AsyncMock(return_value=event)

        result = await Brain.resume_if_parked(brain, "evt-test")
        assert result is False


# =============================================================================
# 6. _waiting_for_user dict semantics
# =============================================================================


class TestWaitingForUserDict:

    def test_dict_supports_in_operator(self):
        """Dict supports `event_id in self._waiting_for_user` like set did."""
        waiting: dict[str, float] = {"evt-1": time.time()}
        assert "evt-1" in waiting
        assert "evt-2" not in waiting

    def test_pop_removes_and_returns_default(self):
        """Dict .pop(key, None) works as .discard() replacement."""
        waiting: dict[str, float] = {"evt-1": time.time()}
        waiting.pop("evt-1", None)
        assert "evt-1" not in waiting
        waiting.pop("evt-missing", None)  # no error

    def test_get_returns_timestamp(self):
        """Dict .get() returns wait_start_timestamp for threshold checks."""
        ts = time.time()
        waiting: dict[str, float] = {"evt-1": ts}
        assert waiting.get("evt-1") == ts
        assert waiting.get("evt-2") is None
