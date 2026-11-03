# BlackBoard/tests/test_scan_reconcile_guards.py
# @ai-rules:
# 1. [Constraint]: Acceptance tests for Brain._scan_active_for_reconcile pre-branch error backoff, escalation, and thinking loop pacing.
# 2. [Pattern]: Validates T-3, T-4, T-5, T-6 using real Brain instance with mocked blackboard.
"""Unit and acceptance tests for reconcile scan error backoff, human escalation, and thinking loop pacing."""
import time
from unittest.mock import AsyncMock
import pytest

from src.agents.brain import Brain
from src.models import (
    ConversationTurn,
    EventDocument,
    EventEvidence,
    EventInput,
    EventStatus,
    MessageStatus,
)


def _make_event(
    event_id: str = "evt-err",
    status: str = "active",
    source: str = "aligner",
    service: str = "test-service",
    conversation: list | None = None,
) -> EventDocument:
    evidence = EventEvidence(display_text="test", source_type=source, domain="complicated", severity="error")
    event_input = EventInput(reason="test", evidence=evidence, timeDate="2026-01-01T00:00:00Z")
    return EventDocument(
        id=event_id,
        source=source,
        status=EventStatus(status),
        brain_phase="triage",
        service=service,
        event=event_input,
        conversation=conversation or [],
    )


def _make_brain(event: EventDocument) -> Brain:
    bb = AsyncMock()
    bb.get_active_events_with_status = AsyncMock(return_value={event.id: event.status.value})
    bb.get_event = AsyncMock(return_value=event)
    bb.mark_turns_delivered = AsyncMock()
    brain = Brain(blackboard=bb, agents={})
    brain._active_tasks = {}
    return brain


class TestScanReconcileGuards:
    @pytest.mark.asyncio
    async def test_t3_error_turn_within_backoff_is_not_enqueued(self):
        """T-3: When the trailing turn is action='error' and backoff has not elapsed, event is NOT enqueued."""
        turns = [
            ConversationTurn(
                turn=1,
                actor="brain",
                action="error",
                status=MessageStatus.SENT,
                thoughts="LLM stream timed out (no chunks for 120.0s) after 2 attempts",
                timestamp=time.time(),
            )
        ]
        event = _make_event("evt-err-1", conversation=turns)
        brain = _make_brain(event)

        # First scan attempt within backoff window (e.g. 10s into 30s backoff)
        brain._last_error_retry["evt-err-1"] = time.time() - 10.0
        result = await brain._scan_active_for_reconcile()

        assert "evt-err-1" not in result

    @pytest.mark.asyncio
    async def test_t4_error_turn_after_backoff_is_enqueued_and_paces_next(self):
        """T-4: When backoff has elapsed for 1 error, event is enqueued once, _last_error_retry updated, and next scan skips."""
        turns = [
            ConversationTurn(
                turn=1,
                actor="brain",
                action="error",
                status=MessageStatus.SENT,
                thoughts="LLM stream timed out",
                timestamp=time.time() - 35.0,
            )
        ]
        event = _make_event("evt-err-2", conversation=turns)
        brain = _make_brain(event)
        brain._last_processed["evt-err-2"] = time.time() - 35.0
        brain._last_error_retry["evt-err-2"] = time.time() - 35.0

        # First scan: backoff (30s) expired -> enqueued
        result = await brain._scan_active_for_reconcile()
        assert "evt-err-2" in result
        # Check retry anchor was updated to current time
        assert time.time() - brain._last_error_retry["evt-err-2"] < 2.0

        # Immediate subsequent scan within new backoff -> skipped
        result_subsequent = await brain._scan_active_for_reconcile()
        assert "evt-err-2" not in result_subsequent

    @pytest.mark.asyncio
    async def test_t5_three_consecutive_errors_escalates_to_human(self):
        """T-5: When 3 consecutive errors occur, _escalate_to_human is invoked once and event is skipped."""
        turns = [
            ConversationTurn(turn=1, actor="brain", action="error", status=MessageStatus.DELIVERED, thoughts="Err 1"),
            ConversationTurn(turn=2, actor="brain", action="error", status=MessageStatus.DELIVERED, thoughts="Err 2"),
            ConversationTurn(turn=3, actor="brain", action="error", status=MessageStatus.SENT, thoughts="Err 3"),
        ]
        event = _make_event("evt-err-3", conversation=turns)
        brain = _make_brain(event)
        brain._escalate_to_human = AsyncMock()

        result = await brain._scan_active_for_reconcile()

        assert "evt-err-3" not in result
        assert "evt-err-3" in brain._escalated_error_events
        brain._escalate_to_human.assert_called_once()
        args, _ = brain._escalate_to_human.call_args
        assert args[0] == "evt-err-3"
        assert args[2] == 3  # consecutive errors

        # Next scan does NOT call escalation again (de-duped)
        brain._escalate_to_human.reset_mock()
        result_2 = await brain._scan_active_for_reconcile()
        assert "evt-err-3" not in result_2
        brain._escalate_to_human.assert_not_called()

    @pytest.mark.asyncio
    async def test_error_escalation_cleared_when_non_error_turn_breaks_streak(self):
        """When a non-error turn breaks trailing errors streak, _escalated_error_events is cleared and future streak can escalate again."""
        turns = [
            ConversationTurn(turn=1, actor="brain", action="error", status=MessageStatus.DELIVERED, thoughts="Err 1"),
            ConversationTurn(turn=2, actor="brain", action="error", status=MessageStatus.DELIVERED, thoughts="Err 2"),
            ConversationTurn(turn=3, actor="brain", action="error", status=MessageStatus.SENT, thoughts="Err 3"),
        ]
        event = _make_event("evt-err-recovery", conversation=turns)
        brain = _make_brain(event)
        brain._escalate_to_human = AsyncMock()

        # Step 1: 3 errors -> escalated
        await brain._scan_active_for_reconcile()
        assert "evt-err-recovery" in brain._escalated_error_events
        assert brain._escalate_to_human.call_count == 1

        # Step 2: Non-error turn (e.g. user reply or brain response) breaks the streak
        event.conversation.append(
            ConversationTurn(turn=4, actor="user", action="message", status=MessageStatus.DELIVERED, thoughts="Let's retry")
        )
        brain._last_processed["evt-err-recovery"] = time.time() - 100.0

        # Scan should clear escalated status and enqueue event
        result = await brain._scan_active_for_reconcile()
        assert "evt-err-recovery" in result
        assert "evt-err-recovery" not in brain._escalated_error_events
        assert "evt-err-recovery" not in brain._last_error_retry

        # Step 3: Later, 3 fresh errors occur
        event.conversation.extend([
            ConversationTurn(turn=5, actor="brain", action="error", status=MessageStatus.DELIVERED, thoughts="New Err 1"),
            ConversationTurn(turn=6, actor="brain", action="error", status=MessageStatus.DELIVERED, thoughts="New Err 2"),
            ConversationTurn(turn=7, actor="brain", action="error", status=MessageStatus.SENT, thoughts="New Err 3"),
        ])
        brain._escalate_to_human.reset_mock()
        await brain._scan_active_for_reconcile()

        # Should escalate again for the new streak
        assert "evt-err-recovery" in brain._escalated_error_events
        assert brain._escalate_to_human.call_count == 1

    @pytest.mark.asyncio
    async def test_escalation_failure_backs_off_and_does_not_retry_storm(self):
        """When _escalate_to_human raises an exception, the event backs off 60s without spamming on every scan."""
        turns = [
            ConversationTurn(turn=1, actor="brain", action="error", status=MessageStatus.DELIVERED, thoughts="Err 1"),
            ConversationTurn(turn=2, actor="brain", action="error", status=MessageStatus.DELIVERED, thoughts="Err 2"),
            ConversationTurn(turn=3, actor="brain", action="error", status=MessageStatus.SENT, thoughts="Err 3"),
        ]
        event = _make_event("evt-err-storm", conversation=turns)
        brain = _make_brain(event)
        brain._escalate_to_human = AsyncMock(side_effect=RuntimeError("Slack unavailable"))

        # Scan 1: Escalation fails
        result = await brain._scan_active_for_reconcile()
        assert "evt-err-storm" not in result
        assert "evt-err-storm" not in brain._escalated_error_events
        assert brain._escalate_to_human.call_count == 1

        # Scan 2 (immediate / within 60s): Backoff active, no retry storm
        result_2 = await brain._scan_active_for_reconcile()
        assert "evt-err-storm" not in result_2
        assert brain._escalate_to_human.call_count == 1  # Not called again

        # Scan 3 (after 60s backoff): Retries escalation
        brain._last_error_retry["evt-err-storm"] = time.time() - 65.0
        result_3 = await brain._scan_active_for_reconcile()
        assert "evt-err-storm" not in result_3
        assert brain._escalate_to_human.call_count == 2

    @pytest.mark.asyncio
    async def test_escalate_to_human_failure_does_not_mutate_waiting_for_user(self):
        """_escalate_to_human sets _waiting_for_user only after successful completion, not on partial failure."""
        event = _make_event("evt-esc-fail")
        brain = _make_brain(event)
        brain._execute_function_call = AsyncMock(side_effect=RuntimeError("Slack down"))

        with pytest.raises(RuntimeError):
            await brain._escalate_to_human("evt-esc-fail", event, 3, 180.0)

        assert "evt-esc-fail" not in brain._waiting_for_user

    @pytest.mark.asyncio
    async def test_t6_thinking_loop_guard_paces_re_enqueue_after_30m(self):
        """T-6: When trailing_thoughts >= 2 and idle >= 1800s, event re-enqueues once, paces for 300s, and next scan skips."""
        turns = [
            ConversationTurn(turn=1, actor="brain", action="thoughts", status=MessageStatus.EVALUATED, thoughts="Plan A"),
            ConversationTurn(turn=2, actor="brain", action="thoughts", status=MessageStatus.EVALUATED, thoughts="Plan B"),
        ]
        event = _make_event("evt-think-1", conversation=turns)
        brain = _make_brain(event)

        # Under 1800s (e.g. 500s) -> suppressed by thinking loop guard
        brain._last_processed["evt-think-1"] = time.time() - 500.0
        result_early = await brain._scan_active_for_reconcile()
        assert "evt-think-1" not in result_early

        # Over 1800s (e.g. 1900s) -> re-enqueued with bypass pacing
        brain._last_processed["evt-think-1"] = time.time() - 1900.0
        result_due = await brain._scan_active_for_reconcile()
        assert "evt-think-1" in result_due
        assert "evt-think-1" in brain._thinking_bypass_time

        # Next scan before 300s bypass pacing elapsed -> skipped
        result_paced = await brain._scan_active_for_reconcile()
        assert "evt-think-1" not in result_paced

    @pytest.mark.asyncio
    async def test_thinking_loop_guard_bypassed_by_unread_turn(self):
        """Unread delivered turn enqueues immediately even if trailing turns had consecutive thoughts."""
        turns = [
            ConversationTurn(turn=1, actor="brain", action="thoughts", status=MessageStatus.EVALUATED, thoughts="Plan A"),
            ConversationTurn(turn=2, actor="brain", action="thoughts", status=MessageStatus.EVALUATED, thoughts="Plan B"),
            ConversationTurn(turn=3, actor="user", action="message", status=MessageStatus.DELIVERED, thoughts="Hello?"),
        ]
        event = _make_event("evt-think-unread", conversation=turns)
        brain = _make_brain(event)
        brain._last_processed["evt-think-unread"] = time.time() - 100.0

        result = await brain._scan_active_for_reconcile()
        assert "evt-think-unread" in result

    @pytest.mark.asyncio
    async def test_thinking_loop_guard_escalates_to_human_after_three_bypasses(self):
        """After 3 bypass attempts, thinking loop escalates to human oncall and does not re-enqueue."""
        turns = [
            ConversationTurn(turn=1, actor="brain", action="thoughts", status=MessageStatus.EVALUATED, thoughts="Plan A"),
            ConversationTurn(turn=2, actor="brain", action="thoughts", status=MessageStatus.EVALUATED, thoughts="Plan B"),
        ]
        event = _make_event("evt-think-esc", conversation=turns)
        brain = _make_brain(event)
        brain._escalate_to_human = AsyncMock()

        # Set 3 prior bypass attempts and idle >= 1800s
        brain._thinking_bypass_count["evt-think-esc"] = 3
        brain._last_processed["evt-think-esc"] = time.time() - 1900.0

        result = await brain._scan_active_for_reconcile()
        assert "evt-think-esc" not in result
        brain._escalate_to_human.assert_called_once()
        assert "evt-think-esc" in brain._escalated_thinking_events


def _nudge_turn(n: int, status: MessageStatus = MessageStatus.EVALUATED) -> ConversationTurn:
    return ConversationTurn(
        turn=n, actor="user", action="message", source="automated", status=status,
        thoughts="Automated health check: idle.",
    )


def _running_task():
    from unittest.mock import MagicMock
    task = MagicMock()
    task.done.return_value = False
    return task


class TestEscalationRaceGuard:
    """M2: re-verify no live worker / held lock immediately before _escalate_to_human."""

    @staticmethod
    def _three_errors(eid: str):
        return [
            ConversationTurn(turn=1, actor="brain", action="error", status=MessageStatus.DELIVERED, thoughts="E1"),
            ConversationTurn(turn=2, actor="brain", action="error", status=MessageStatus.DELIVERED, thoughts="E2"),
            ConversationTurn(turn=3, actor="brain", action="error", status=MessageStatus.EVALUATED, thoughts="E3"),
        ]

    @pytest.mark.asyncio
    async def test_error_escalation_skipped_when_worker_starts_after_guard1(self):
        eid = "evt-race-task"
        event = _make_event(eid, conversation=self._three_errors(eid))
        brain = _make_brain(event)
        brain._escalate_to_human = AsyncMock()

        async def get_event_then_worker_starts(_eid):
            brain._active_tasks[_eid] = _running_task()  # Guard 1 already passed; worker appears now
            return event

        brain.blackboard.get_event = AsyncMock(side_effect=get_event_then_worker_starts)

        result = await brain._scan_active_for_reconcile()

        assert eid not in result
        brain._escalate_to_human.assert_not_called()
        # Nothing stamped, so the next scan can still escalate once the worker is gone
        assert eid not in brain._escalated_error_events
        assert eid not in brain._last_error_retry

    @pytest.mark.asyncio
    async def test_error_escalation_skipped_when_event_lock_held_then_proceeds_after_release(self):
        eid = "evt-race-lock"
        event = _make_event(eid, conversation=self._three_errors(eid))
        brain = _make_brain(event)
        brain._escalate_to_human = AsyncMock()

        async with brain._event_locks[eid]:
            result = await brain._scan_active_for_reconcile()
            assert eid not in result
            brain._escalate_to_human.assert_not_called()
            assert eid not in brain._escalated_error_events

        await brain._scan_active_for_reconcile()
        brain._escalate_to_human.assert_called_once()
        assert eid in brain._escalated_error_events

    @pytest.mark.asyncio
    async def test_finished_task_does_not_block_escalation(self):
        from unittest.mock import MagicMock
        eid = "evt-race-done"
        event = _make_event(eid, conversation=self._three_errors(eid))
        brain = _make_brain(event)
        brain._escalate_to_human = AsyncMock()
        done_task = MagicMock()
        done_task.done.return_value = True

        async def get_event_with_done_task(_eid):
            brain._active_tasks[_eid] = done_task
            return event

        brain.blackboard.get_event = AsyncMock(side_effect=get_event_with_done_task)
        # Guard 1 sees no task on entry; the done task registered mid-scan must not block
        await brain._scan_active_for_reconcile()

        brain._escalate_to_human.assert_called_once()

    @pytest.mark.asyncio
    async def test_thinking_escalation_skipped_when_worker_starts_after_guard1(self):
        eid = "evt-race-think"
        turns = [
            ConversationTurn(turn=1, actor="brain", action="thoughts", status=MessageStatus.EVALUATED, thoughts="A"),
            ConversationTurn(turn=2, actor="brain", action="thoughts", status=MessageStatus.EVALUATED, thoughts="B"),
        ]
        event = _make_event(eid, conversation=turns)
        brain = _make_brain(event)
        brain._escalate_to_human = AsyncMock()
        brain._thinking_bypass_count[eid] = 3
        brain._last_processed[eid] = time.time() - 1900.0

        async def get_event_then_worker_starts(_eid):
            brain._active_tasks[_eid] = _running_task()
            return event

        brain.blackboard.get_event = AsyncMock(side_effect=get_event_then_worker_starts)

        await brain._scan_active_for_reconcile()

        brain._escalate_to_human.assert_not_called()
        assert eid not in brain._escalated_thinking_events
        assert eid not in brain._thinking_bypass_time


class TestThinkingBypassNotResetByNudge:
    """M4: automated nudge turns must not reset _thinking_bypass_count (3-strike cap)."""

    @staticmethod
    def _thoughts_then_nudge():
        return [
            ConversationTurn(turn=1, actor="brain", action="thoughts", status=MessageStatus.EVALUATED, thoughts="A"),
            ConversationTurn(turn=2, actor="brain", action="thoughts", status=MessageStatus.EVALUATED, thoughts="B"),
            _nudge_turn(3),
        ]

    @pytest.mark.asyncio
    async def test_scan_keeps_bypass_count_when_trailing_turn_is_nudge(self):
        eid = "evt-nudge-scan"
        event = _make_event(eid, conversation=self._thoughts_then_nudge())
        brain = _make_brain(event)
        brain._thinking_bypass_count[eid] = 2
        brain._thinking_bypass_time[eid] = time.time() - 400
        brain._escalated_thinking_events.add(eid)
        brain._last_processed[eid] = time.time() - 120.0

        await brain._scan_active_for_reconcile()

        assert brain._thinking_bypass_count.get(eid) == 2
        assert eid in brain._thinking_bypass_time
        assert eid in brain._escalated_thinking_events

    @pytest.mark.asyncio
    async def test_scan_still_resets_on_real_progress_turn(self):
        eid = "evt-progress-scan"
        turns = self._thoughts_then_nudge() + [
            ConversationTurn(turn=4, actor="developer", action="execute", status=MessageStatus.EVALUATED, result="done"),
        ]
        event = _make_event(eid, conversation=turns)
        brain = _make_brain(event)
        brain._thinking_bypass_count[eid] = 2
        brain._thinking_bypass_time[eid] = time.time() - 400
        brain._last_processed[eid] = time.time() - 120.0

        await brain._scan_active_for_reconcile()

        assert eid not in brain._thinking_bypass_count
        assert eid not in brain._thinking_bypass_time

    @pytest.mark.asyncio
    @pytest.mark.parametrize("trailing,expect_kept", [("nudge", True), ("agent", False)])
    async def test_process_event_reset_site_respects_nudge(self, trailing, expect_kept):
        """The process_event reset (brain.py 'Clear thinking bypass count') keeps state across nudges only."""
        from unittest.mock import MagicMock
        eid = "evt-nudge-proc"
        last = _nudge_turn(3) if trailing == "nudge" else ConversationTurn(
            turn=3, actor="developer", action="execute", status=MessageStatus.DELIVERED, result="done",
        )
        turns = self._thoughts_then_nudge()[:2] + [last]
        event = _make_event(eid, conversation=turns)
        brain = _make_brain(event)
        bb = brain.blackboard
        bb.EVENT_PREFIX = "darwin:event:"
        bb.get_event = AsyncMock(return_value=event)
        bb.stamp_event = AsyncMock()
        bb.record_event = AsyncMock()
        brain._broadcast = AsyncMock()
        brain._get_adapter = AsyncMock(side_effect=RuntimeError("stop here"))
        brain._thinking_bypass_count[eid] = 2
        brain._thinking_bypass_time[eid] = 123.0
        event.processing_started_at = time.time() - 5

        with pytest.raises(Exception):
            await brain._process_event_inner(eid)

        assert (eid in brain._thinking_bypass_count) is expect_kept
        assert (eid in brain._thinking_bypass_time) is expect_kept
