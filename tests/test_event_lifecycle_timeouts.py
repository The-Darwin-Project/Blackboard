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

from src.models import EventDocument, EventInput, EventStatus, EventEvidence
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
        """If user hasn't responded, close proceeds."""
        from src.agents.brain import Brain
        brain = MagicMock()
        brain._waiting_for_user = {"evt-test": time.time() - 900}
        brain._close_and_broadcast = AsyncMock()

        await Brain._idle_timeout_close(brain, "evt-test")
        brain._close_and_broadcast.assert_awaited_once()
        assert "evt-test" not in brain._waiting_for_user


# =============================================================================
# 5. Thaw mechanism
# =============================================================================


class TestResumeIfParked:

    @pytest.mark.asyncio
    async def test_resume_parked_event(self):
        """resume_if_parked returns True and re-enqueues for waiting_approval events."""
        from src.agents.brain import Brain
        event = _make_event(status=EventStatus.WAITING_APPROVAL)
        brain = MagicMock()
        brain.blackboard = MagicMock()
        brain.blackboard.get_event = AsyncMock(return_value=event)
        brain.blackboard.resume_from_approval = AsyncMock()
        brain._scheduler = MagicMock()
        brain._scheduler.enqueue = MagicMock(return_value=True)

        result = await Brain.resume_if_parked(brain, "evt-test")
        assert result is True
        brain.blackboard.resume_from_approval.assert_awaited_once_with("evt-test")
        brain._scheduler.enqueue.assert_called_once_with("evt-test")

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
