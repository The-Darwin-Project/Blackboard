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
