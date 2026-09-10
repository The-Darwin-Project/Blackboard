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
import contextlib
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


def _bind_real_finish_close(brain: MagicMock, brain_cls) -> None:
    """Bind the real Brain._finish_idle_timeout_close onto a bare MagicMock
    `brain` -- otherwise `self._finish_idle_timeout_close(...)` inside the
    real (unbound) `_idle_timeout_close` resolves to an auto-vivified,
    non-async MagicMock attribute instead of running the actual close/skip
    decision."""
    async def _real(event_id, event):
        return await brain_cls._finish_idle_timeout_close(brain, event_id, event)
    brain._finish_idle_timeout_close = AsyncMock(side_effect=_real)


def _fake_close_and_broadcast(brain: MagicMock) -> AsyncMock:
    """A `_close_and_broadcast` stand-in that reproduces its one side effect
    these tests depend on: popping `_waiting_for_user` once the close
    genuinely completes. `_finish_idle_timeout_close` deliberately does NOT
    pop this itself (see its comment) -- doing so before the close actually
    succeeds would make the retry loop give up prematurely on a failure
    inside `_close_and_broadcast`."""
    async def _fake(event_id, *args, **kwargs):
        brain._waiting_for_user.pop(event_id, None)
    return AsyncMock(side_effect=_fake)


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
        brain._close_and_broadcast = _fake_close_and_broadcast(brain)
        _bind_real_finish_close(brain, Brain)

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
        _bind_real_finish_close(brain, Brain)

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
        brain._close_and_broadcast = _fake_close_and_broadcast(brain)
        _bind_real_finish_close(brain, Brain)

        await Brain._idle_timeout_close(brain, "evt-test")
        brain._close_and_broadcast.assert_awaited_once()
        assert "evt-test" not in brain._waiting_for_user


# =============================================================================
# 4a-2. HIGH fix (verification pass #2): get_event failure inside
#       _idle_timeout_close must actually recover, not just log-and-strand.
# =============================================================================


class TestIdleCloseRetryOnGetEventFailure:
    """_run_timer's `finally` unconditionally drops the timer once
    _idle_timeout_close returns, and _scan_active_for_reconcile's idle safety
    net explicitly requires `not is_waiting` before ever re-enqueueing an
    event -- so a bare log-and-return on a transient get_event failure
    permanently strands a wait_for_user event with zero recovery path. The
    fix must actually re-arm a retry (or otherwise recover), not just log."""

    @pytest.mark.asyncio
    async def test_transient_failure_schedules_a_retry_instead_of_stranding(self):
        from src.agents.brain import Brain

        event = _make_event(status=EventStatus.ACTIVE)
        bb = MagicMock()
        bb.get_event = AsyncMock(side_effect=[Exception("redis timeout"), event])

        brain = Brain(blackboard=bb, agents={})
        brain._waiting_for_user[event.id] = time.time() - 900
        brain._close_and_broadcast = _fake_close_and_broadcast(brain)

        with patch.dict("os.environ", {"IDLE_TIMEOUT_CLOSE_RETRY_SEC": "0"}):
            await brain._idle_timeout_close(event.id)

            # First attempt failed -- must not have given up silently: a
            # retry task is tracked, and the event is still eligible (not
            # incorrectly popped from _waiting_for_user by the failure path).
            assert event.id in brain._idle_close_retry_tasks
            brain._close_and_broadcast.assert_not_awaited()
            assert event.id in brain._waiting_for_user

            # Let the retry actually run (IDLE_TIMEOUT_CLOSE_RETRY_SEC=0 --
            # get_event now succeeds per the side_effect list above).
            await asyncio.wait_for(brain._idle_close_retry_tasks[event.id], timeout=1.0)

        brain._close_and_broadcast.assert_awaited_once()
        assert event.id not in brain._waiting_for_user
        assert event.id not in brain._idle_close_retry_tasks

    @pytest.mark.asyncio
    async def test_persistent_failure_keeps_retrying_without_ever_closing(self):
        """A sustained outage must not fall back to an unconditional close --
        we don't know the event's real status, so retrying indefinitely is
        the safe choice over guessing."""
        from src.agents.brain import Brain

        bb = MagicMock()
        bb.get_event = AsyncMock(side_effect=Exception("redis still down"))

        brain = Brain(blackboard=bb, agents={})
        brain._waiting_for_user["evt-down"] = time.time() - 900
        brain._close_and_broadcast = AsyncMock()

        with patch.dict("os.environ", {"IDLE_TIMEOUT_CLOSE_RETRY_SEC": "0"}):
            await brain._idle_timeout_close("evt-down")
            retry_task = brain._idle_close_retry_tasks["evt-down"]
            # Let the (single, persistent) retry loop spin several times against
            # the sustained failure -- it must keep retrying, never give up and
            # force-close on a guess.
            await asyncio.sleep(0.05)

            assert brain._idle_close_retry_count["evt-down"] >= 2
            brain._close_and_broadcast.assert_not_awaited()
            assert "evt-down" in brain._waiting_for_user
            assert "evt-down" in brain._idle_close_retry_tasks
            assert not retry_task.done()  # still the same loop, still retrying

            retry_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await retry_task

    @pytest.mark.asyncio
    async def test_clear_waiting_cancels_pending_retry(self):
        """If the user responds (clear_waiting) while a retry is pending, the
        stale retry task must not be left to fire later against a resolved
        event."""
        from src.agents.brain import Brain

        bb = MagicMock()
        bb.get_event = AsyncMock(side_effect=Exception("still down"))
        brain = Brain(blackboard=bb, agents={})
        brain._waiting_for_user["evt-resolved"] = time.time()

        with patch.dict("os.environ", {"IDLE_TIMEOUT_CLOSE_RETRY_SEC": "60"}):
            await brain._idle_timeout_close("evt-resolved")
        assert "evt-resolved" in brain._idle_close_retry_tasks
        pending_task = brain._idle_close_retry_tasks["evt-resolved"]
        # Let the loop actually start and reach its asyncio.sleep(60) suspension
        # point before cancelling -- cancelling a task in the same tick it was
        # created (never yet scheduled) throws CancelledError before the
        # coroutine's own try/except ever runs, which isn't the realistic case
        # this test means to cover.
        await asyncio.sleep(0)
        assert not pending_task.done()

        brain.clear_waiting("evt-resolved")

        assert "evt-resolved" not in brain._idle_close_retry_tasks
        assert "evt-resolved" not in brain._idle_close_retry_count
        # Non-tautological check that cancellation actually took effect: the loop
        # is sleeping for 60s (IDLE_TIMEOUT_CLOSE_RETRY_SEC above), so if
        # clear_waiting's .cancel() call were silently broken (e.g. a no-op, or
        # cancelling the wrong task), this would still be sleeping and the
        # wait_for below would time out instead of completing almost instantly.
        await asyncio.wait_for(pending_task, timeout=1.0)
        assert pending_task.done()
        assert not pending_task.cancelled()  # coroutine caught CancelledError and returned cleanly

    @pytest.mark.asyncio
    async def test_failure_inside_close_sequence_also_retries(self):
        """HIGH fix (verification pass #3): the retry mechanism previously
        only guarded the initial get_event call. A failure inside
        _finish_idle_timeout_close's own call chain (_close_and_broadcast)
        must also trigger a retry, not propagate uncaught."""
        from src.agents.brain import Brain

        event = _make_event(status=EventStatus.ACTIVE)
        bb = MagicMock()
        bb.get_event = AsyncMock(return_value=event)  # the initial fetch always succeeds

        brain = Brain(blackboard=bb, agents={})
        brain._waiting_for_user[event.id] = time.time() - 900

        attempts: list[None] = []

        async def _close_side_effect(event_id, *args, **kwargs):
            attempts.append(None)
            if len(attempts) == 1:
                raise Exception("close_event watch/pipe.execute() failed")
            brain._waiting_for_user.pop(event_id, None)

        brain._close_and_broadcast = AsyncMock(side_effect=_close_side_effect)

        with patch.dict("os.environ", {"IDLE_TIMEOUT_CLOSE_RETRY_SEC": "0"}):
            await brain._idle_timeout_close(event.id)

            # The first attempt reached _close_and_broadcast (unlike the
            # old code, which only guarded the initial get_event) and that
            # call itself failed -- must still retry, not strand the event.
            assert len(attempts) == 1
            assert event.id in brain._idle_close_retry_tasks
            assert event.id in brain._waiting_for_user

            await asyncio.wait_for(brain._idle_close_retry_tasks[event.id], timeout=1.0)

        assert len(attempts) == 2
        assert event.id not in brain._waiting_for_user
        assert event.id not in brain._idle_close_retry_tasks
        assert event.id not in brain._idle_close_retry_count

    @pytest.mark.asyncio
    async def test_generation_aware_retry_abandons_stale_attempt_after_rearm(self):
        """MEDIUM fix (verification pass #3): if the event is re-armed
        (IdleTimeoutManager.schedule() called again -- e.g. via a fresh
        wait_for_user/classify_event re-arm) while a retry loop from an
        earlier failure is still in flight, the stale loop must abandon its
        close attempt rather than force-closing an event a new timer now
        owns."""
        from src.agents.brain import Brain

        bb = MagicMock()
        bb.get_event = AsyncMock(side_effect=Exception("still down"))

        brain = Brain(blackboard=bb, agents={})
        brain._waiting_for_user["evt-rearmed"] = time.time()
        brain._close_and_broadcast = AsyncMock()

        with patch.dict("os.environ", {"IDLE_TIMEOUT_CLOSE_RETRY_SEC": "0"}):
            await brain._idle_timeout_close("evt-rearmed")
        assert "evt-rearmed" in brain._idle_close_retry_tasks
        retry_task = brain._idle_close_retry_tasks["evt-rearmed"]

        # Simulate a legitimate re-arm: a fresh schedule() bumps the generation.
        # (warn_callback/close_callback are irrelevant here -- only the
        # generation counter matters for this test.)
        brain._idle_timeout.schedule("evt-rearmed", warning_sec=5100)
        brain._idle_timeout.cancel("evt-rearmed")  # don't actually let the new timer fire

        with patch.dict("os.environ", {"IDLE_TIMEOUT_CLOSE_RETRY_SEC": "0"}):
            await asyncio.wait_for(retry_task, timeout=1.0)

        # The stale loop must have abandoned its attempt: no force-close,
        # and it must not have even tried get_event again post-rearm.
        brain._close_and_broadcast.assert_not_awaited()
        assert bb.get_event.call_count == 1  # only the original failed attempt, no retry re-fetch
        assert retry_task.done()
        # The re-arm (still tracked in _waiting_for_user, per the schedule()
        # call above) is left alone for its own fresh timer to handle.
        assert "evt-rearmed" in brain._waiting_for_user


# =============================================================================
# 4a-3. Idle-close retry state cleanup at every _waiting_for_user-clearing site,
#       not just clear_waiting/stop_event_loop -- mirrors _clear_jarvis_wait.
# =============================================================================


class TestIdleCloseRetryCleanupAtOtherClearingSites:

    def _make_closeable_brain(self, event: EventDocument):
        from src.agents.brain import Brain
        bb = MagicMock()
        bb.get_event = AsyncMock(return_value=event)
        bb.close_event = AsyncMock()
        bb.persist_report = AsyncMock()
        bb.append_journal = AsyncMock()
        bb.record_event = AsyncMock()
        brain = Brain(blackboard=bb, agents={})
        brain._broadcast = AsyncMock()
        brain._broadcast_turn = AsyncMock()
        return brain

    @pytest.mark.asyncio
    async def test_close_and_broadcast_clears_idle_close_retry_state(self):
        """MEDIUM fix: _close_and_broadcast is the universal close choke point
        (used by every close reason, including idle_timeout itself) -- it must
        clear stray idle-close retry bookkeeping too, not just _waiting_for_user."""
        event = _make_event(event_id="evt-cleanup", status=EventStatus.ACTIVE)
        brain = self._make_closeable_brain(event)
        brain._waiting_for_user[event.id] = time.time()
        brain._idle_close_retry_count[event.id] = 3
        stray_task = asyncio.create_task(asyncio.sleep(60))
        brain._idle_close_retry_tasks[event.id] = stray_task

        await brain._close_and_broadcast(event.id, "test close")

        assert event.id not in brain._idle_close_retry_count
        assert event.id not in brain._idle_close_retry_tasks
        with contextlib.suppress(asyncio.CancelledError):
            await stray_task
        assert stray_task.cancelled()

    @pytest.mark.asyncio
    async def test_clear_waiting_for_user_tool_context_clears_idle_close_retry_state(self):
        """The ToolContext-facing clear_waiting_for_user (Protocol surface used
        by handlers) must not be a partial-cleanup variant that skips retry
        teardown -- it now delegates to the full clear_waiting."""
        from src.agents.brain import Brain
        brain = Brain(blackboard=MagicMock(), agents={})
        brain._waiting_for_user["evt-ctx"] = time.time()
        brain._idle_close_retry_count["evt-ctx"] = 1
        stray_task = asyncio.create_task(asyncio.sleep(60))
        brain._idle_close_retry_tasks["evt-ctx"] = stray_task

        brain._tool_ctx.clear_waiting_for_user("evt-ctx")

        assert "evt-ctx" not in brain._waiting_for_user
        assert "evt-ctx" not in brain._idle_close_retry_count
        assert "evt-ctx" not in brain._idle_close_retry_tasks
        with contextlib.suppress(asyncio.CancelledError):
            await stray_task
        assert stray_task.cancelled()

    @pytest.mark.asyncio
    async def test_idle_timeout_warn_vanished_event_clears_idle_close_retry_state(self):
        """_idle_timeout_warn's own "event vanished/closed" branch pops
        _waiting_for_user directly (bypassing clear_waiting) -- it must clear
        retry state too."""
        from src.agents.brain import Brain
        bb = MagicMock()
        bb.get_event = AsyncMock(return_value=None)  # vanished
        brain = Brain(blackboard=bb, agents={})
        brain._waiting_for_user["evt-vanished"] = time.time()
        brain._idle_close_retry_count["evt-vanished"] = 1
        stray_task = asyncio.create_task(asyncio.sleep(60))
        brain._idle_close_retry_tasks["evt-vanished"] = stray_task

        await brain._idle_timeout_warn("evt-vanished")

        assert "evt-vanished" not in brain._waiting_for_user
        assert "evt-vanished" not in brain._idle_close_retry_count
        assert "evt-vanished" not in brain._idle_close_retry_tasks
        with contextlib.suppress(asyncio.CancelledError):
            await stray_task
        assert stray_task.cancelled()


# =============================================================================
# 4b. Approval timeout env var (IDLE_TIMEOUT_APPROVAL_SEC)
# =============================================================================


class TestApprovalTimeout:

    def test_default_is_5100_seconds(self):
        """Default approval timeout is 5100s -- slightly under CHAT_STALE_TTL (5400s) so the
        warn->close courtesy on WAITING_APPROVAL events completes with a real notice window
        before StalenessGuard[chat] becomes eligible to close (see QE fast-follow finding on
        evt-321b0b68: a default equal to CHAT_STALE_TTL collapsed that window to ~60s)."""
        from src.agents.brain import Brain
        event = _make_event()
        with patch.dict("os.environ", {}, clear=False):
            import os
            os.environ.pop("IDLE_TIMEOUT_APPROVAL_SEC", None)
            assert Brain._get_approval_timeout(MagicMock(), event) == 5100

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
# 4b-1. _get_idle_timeout_for_event must recognize wait_for_user (ACTIVE) parks,
#       not just WAITING_APPROVAL -- both rely on the long timeout as a real backstop.
# =============================================================================


class TestIsWaitForUserPark:

    def test_true_for_wait_for_user_turn(self):
        from src.agents.brain import Brain
        event = _make_event(status=EventStatus.ACTIVE)
        event.conversation = [
            ConversationTurn(turn=1, actor="brain", action="wait",
                              waitingFor="user", timestamp=time.time()),
        ]
        assert Brain._is_wait_for_user_park(event) is True

    def test_false_for_plain_text_response(self):
        """An ordinary conversational reply (no explicit wait_for_user call)
        must not be mistaken for a long-timeout park."""
        from src.agents.brain import Brain
        event = _make_event(status=EventStatus.ACTIVE)
        event.conversation = [
            ConversationTurn(turn=1, actor="brain", action="response",
                              timestamp=time.time()),
        ]
        assert Brain._is_wait_for_user_park(event) is False

    def test_false_for_wait_for_agent(self):
        """wait_for_agent also uses action="wait" but a different waitingFor
        value -- must not be conflated with wait_for_user."""
        from src.agents.brain import Brain
        event = _make_event(status=EventStatus.ACTIVE)
        event.conversation = [
            ConversationTurn(turn=1, actor="brain", action="wait",
                              waitingFor="agent:developer", timestamp=time.time()),
        ]
        assert Brain._is_wait_for_user_park(event) is False

    def test_false_for_wait_for_jarvis(self):
        from src.agents.brain import Brain
        event = _make_event(status=EventStatus.ACTIVE)
        event.conversation = [
            ConversationTurn(turn=1, actor="brain", action="wait",
                              waitingFor="jarvis", timestamp=time.time()),
        ]
        assert Brain._is_wait_for_user_park(event) is False

    def test_skips_trailing_courtesy_warning_turn(self):
        """A courtesy-warning turn appended after the wait_for_user park must
        not mask it -- the park is still the most recent substantive turn."""
        from src.agents.brain import Brain
        event = _make_event(status=EventStatus.ACTIVE)
        event.conversation = [
            ConversationTurn(turn=1, actor="brain", action="wait",
                              waitingFor="user", timestamp=time.time() - 100),
            ConversationTurn(turn=2, actor="brain", action="response",
                              is_courtesy_warning=True, timestamp=time.time()),
        ]
        assert Brain._is_wait_for_user_park(event) is True

    def test_false_for_empty_conversation(self):
        from src.agents.brain import Brain
        event = _make_event(status=EventStatus.ACTIVE)
        event.conversation = []
        assert Brain._is_wait_for_user_park(event) is False


class TestGetIdleTimeoutForEvent:
    """HIGH fix (verification pass #3): the status-aware helper must give
    wait_for_user (ACTIVE) parks the same extended timeout as WAITING_APPROVAL
    parks -- both docstrings/handlers call it their "sole backstop"."""

    def test_wait_for_user_active_park_gets_approval_timeout(self):
        from src.agents.brain import Brain
        event = _make_event(status=EventStatus.ACTIVE)
        event.conversation = [
            ConversationTurn(turn=1, actor="brain", action="wait",
                              waitingFor="user", timestamp=time.time()),
        ]
        brain = Brain(blackboard=MagicMock(), agents={})
        with patch.dict("os.environ", {"IDLE_TIMEOUT_APPROVAL_SEC": "5100", "IDLE_TIMEOUT_CONVERSATION_SEC": "900"}):
            assert brain._get_idle_timeout_for_event(event) == 5100

    def test_waiting_approval_status_gets_approval_timeout(self):
        from src.agents.brain import Brain
        event = _make_event(status=EventStatus.WAITING_APPROVAL)
        event.conversation = [
            ConversationTurn(turn=1, actor="brain", action="request_approval",
                              waitingFor="user", timestamp=time.time()),
        ]
        brain = Brain(blackboard=MagicMock(), agents={})
        with patch.dict("os.environ", {"IDLE_TIMEOUT_APPROVAL_SEC": "5100", "IDLE_TIMEOUT_CONVERSATION_SEC": "900"}):
            assert brain._get_idle_timeout_for_event(event) == 5100

    def test_plain_active_conversation_gets_short_timeout(self):
        from src.agents.brain import Brain
        event = _make_event(status=EventStatus.ACTIVE)
        event.conversation = [
            ConversationTurn(turn=1, actor="brain", action="response", timestamp=time.time()),
        ]
        brain = Brain(blackboard=MagicMock(), agents={})
        with patch.dict("os.environ", {"IDLE_TIMEOUT_APPROVAL_SEC": "5100", "IDLE_TIMEOUT_CONVERSATION_SEC": "900"}):
            assert brain._get_idle_timeout_for_event(event) == 900


# =============================================================================
# 4b-2. Notice-window invariant: APPROVAL_SEC + CLOSE_SEC < CHAT_STALE_TTL
# =============================================================================


class TestApprovalNoticeWindowInvariant:
    """assert_approval_notice_window() must fail fast if the three independently
    configured env vars (IDLE_TIMEOUT_APPROVAL_SEC, IDLE_TIMEOUT_CLOSE_SEC,
    CHAT_STALE_TTL) drift into a state that inverts the courtesy notice window
    on WAITING_APPROVAL events (sum > ttl), and warn on the zero-margin boundary
    (sum == ttl, matching the current production defaults) -- this exact class
    of drift already caused the evt-321b0b68 QE fast-follow finding (5400s
    default vs 5100s)."""

    def test_defaults_do_not_raise(self):
        """Production defaults (5100, 300, 5400) sit exactly on the zero-margin
        boundary (5100 + 300 == 5400) -- this must not raise (it would break
        every default-config startup), but it does log a warning flagging the
        zero margin."""
        from src.scheduling.idle_timeout import assert_approval_notice_window
        assert_approval_notice_window(5100, 300, 5400)

    def test_warns_but_does_not_raise_when_sum_equals_ttl(self, caplog):
        """Boundary case: sum == ttl is a zero-margin race, not an inversion --
        it must warn, not raise."""
        from src.scheduling.idle_timeout import assert_approval_notice_window
        with caplog.at_level("WARNING"):
            assert_approval_notice_window(5100, 300, 5400)
        assert "zero margin" in caplog.text

    def test_raises_when_sum_exceeds_ttl(self):
        from src.scheduling.idle_timeout import assert_approval_notice_window
        with pytest.raises(ValueError, match="Idle-timeout invariant violated"):
            assert_approval_notice_window(5400, 300, 5400)

    def test_brain_init_raises_on_misconfigured_env(self):
        """Brain.__init__ must enforce the invariant at construction time, not
        just leave it as an unvalidated docstring claim."""
        from src.agents.brain import Brain
        with patch.dict("os.environ", {
            "IDLE_TIMEOUT_APPROVAL_SEC": "5400",
            "CHAT_STALE_TTL": "5400",
        }):
            with pytest.raises(ValueError, match="Idle-timeout invariant violated"):
                Brain(blackboard=MagicMock(), agents={})


# =============================================================================
# 4c. End-to-end: idle guard defers to StalenessGuard[chat] for real closure
# =============================================================================


class TestApprovalParkSurvivesIdleThenStalenessCloses:
    """Ties Guard A (IdleTimeoutManager + the real _idle_timeout_warn/_idle_timeout_close)
    and Guard B (_check_chat_staleness / _close_stale_chat_event) together end-to-end, at
    an accelerated timescale, to prove the actual production sequencing from
    evt-321b0b68: a WAITING_APPROVAL event survives the short idle-close attempt, its
    courtesy warning does not reset StalenessGuard[chat]'s clock, and the event is only
    closed once by the staleness guard once it is genuinely stale."""

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
        brain._next_turn_number = AsyncMock(return_value=2)

        async def _append(eid, turn, ev=None):
            event.conversation.append(turn)
            return turn.turn

        brain._append_and_broadcast = AsyncMock(side_effect=_append)
        _bind_real_finish_close(brain, Brain)

        # --- Guard A: the real IdleTimeoutManager, driving the real bound
        # _idle_timeout_warn and _idle_timeout_close, at a millisecond timescale
        # standing in for the ~20 minute production warn->close window. Using the
        # real warn callback (not an AsyncMock) exercises the actual fallback
        # courtesy-warning turn append (event.source == "chat" here), which is
        # exactly the path that used to reset StalenessGuard[chat]'s clock.
        with patch.dict("os.environ", {"IDLE_TIMEOUT_CLOSE_SEC": "0"}):
            mgr = IdleTimeoutManager(
                warn_callback=lambda eid: Brain._idle_timeout_warn(brain, eid),
                close_callback=lambda eid: Brain._idle_timeout_close(brain, eid),
            )
        mgr.schedule(event.id, warning_sec=0.01)
        await asyncio.sleep(0.15)

        # The courtesy warning fired and appended its turn...
        brain._append_and_broadcast.assert_awaited_once()
        assert any(t.is_courtesy_warning for t in event.conversation)

        # ...but the event survived close: still WAITING_APPROVAL, never closed,
        # and still tracked in _waiting_for_user so Guard B can see it.
        brain._close_and_broadcast.assert_not_awaited()
        assert event.id in brain._waiting_for_user

        # --- Guard B: StalenessGuard[chat]'s real check+close pair now takes
        # over, using a tiny CHAT_STALE_TTL to stand in for the ~90 minute
        # production threshold. The pre-seeded conversation turn (1hr old) is
        # already past it -- and, crucially, the just-appended courtesy-warning
        # turn (timestamped "now") must NOT mask that staleness.
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
