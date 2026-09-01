# tests/test_brain_loop_plumbing.py
# @ai-rules:
# 1. [Constraint]: Tests for brain.py LLM loop plumbing — user interrupt, wait-guard scope, stale turns.
# 2. [Pattern]: Uses _make_event/_make_turn from test_scan_callback.py pattern. No live Redis or LLM.
# 3. [Gotcha]: ConversationTurn.status defaults to SENT. Set explicitly for DELIVERED/EVALUATED turns.
# 4. [Pattern]: T-4/T-5 use Brain + real _BrainToolContext — NOT AsyncMock(spec=ToolContext).
"""Unit tests for brain.py LLM iteration loop plumbing fixes.

Tests:
- User interrupt detection + injection
- _waiting_for_agent temporal scoping (both guards)
- Survivor turn number (cross-source merge)
- Handler post-yield race detection (T-4, T-5)
- Guard 1 precedence over Guard 7 (T-7)
"""
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.agents.brain import (
    Brain,
    _BrainToolContext,
    MAX_AGENT_ERROR_STREAK,
    AGENT_ERROR_BACKOFF_SECONDS,
)
from src.agents.handlers_state import handle_wait_for_agent
from src.models import (
    ConversationTurn,
    EventDocument,
    EventInput,
    EventEvidence,
    EventStatus,
    MessageStatus,
)


def _make_event(
    event_id: str = "evt-test",
    status: str = "active",
    source: str = "chat",
    service: str = "test-svc",
    conversation: list | None = None,
    brain_phase: str | None = "triage",
) -> EventDocument:
    evidence = EventEvidence(
        display_text="test", source_type=source, domain="complicated", severity="info",
    )
    event_input = EventInput(
        reason="test", evidence=evidence, timeDate="2026-01-01T00:00:00Z",
    )
    return EventDocument(
        id=event_id,
        source=source,
        status=EventStatus(status),
        brain_phase=brain_phase,
        service=service,
        event=event_input,
        conversation=conversation or [],
    )


def _make_turn(
    turn: int = 1,
    actor: str = "brain",
    action: str = "triage",
    status: str = "evaluated",
    thoughts: str = "test",
    timestamp: float | None = None,
    waitingFor: str | None = None,
) -> ConversationTurn:
    return ConversationTurn(
        turn=turn, actor=actor, action=action, status=status,
        thoughts=thoughts, timestamp=timestamp or time.time(),
        waitingFor=waitingFor,
    )


# =========================================================================
# Test 1: User interrupt detected
# =========================================================================
class TestUserInterruptDetection:
    def test_user_interrupt_detected(self):
        """User turn after turn_snapshot → interrupt detected, response_emitted reset."""
        turn_snapshot = 2
        conversation = [
            _make_turn(turn=1, actor="brain", action="triage", status="evaluated"),
            _make_turn(turn=2, actor="brain", action="route", status="evaluated"),
            _make_turn(turn=3, actor="user", action="message", status="sent"),
        ]
        event = _make_event(conversation=conversation)
        is_intermediate = False
        response_emitted_for: set[str] = {"evt-test"}

        user_interrupt_turn: int | None = None
        response_emitted = True
        if not is_intermediate:
            new_user_turns = [
                t for t in event.conversation[turn_snapshot:]
                if t.actor == "user" and t.status.value in ("sent", "delivered")
            ]
            if new_user_turns:
                user_interrupt_turn = new_user_turns[-1].turn
                response_emitted = False
                response_emitted_for.discard("evt-test")

        assert user_interrupt_turn == 3
        assert response_emitted is False
        assert "evt-test" not in response_emitted_for

    def test_user_interrupt_skipped_intermediate(self):
        """Intermediate mode skips interrupt detection."""
        turn_snapshot = 1
        conversation = [
            _make_turn(turn=1, actor="brain", action="wait", status="evaluated"),
            _make_turn(turn=2, actor="user", action="message", status="sent"),
        ]
        event = _make_event(conversation=conversation)
        is_intermediate = True

        user_interrupt_turn: int | None = None
        if not is_intermediate:
            new_user_turns = [
                t for t in event.conversation[turn_snapshot:]
                if t.actor == "user" and t.status.value in ("sent", "delivered")
            ]
            if new_user_turns:
                user_interrupt_turn = new_user_turns[-1].turn

        assert user_interrupt_turn is None

    def test_user_interrupt_safety_net(self):
        """turn_snapshot is NOT modified by interrupt detection — user turn stays for scan safety net."""
        turn_snapshot = 2
        original_snapshot = turn_snapshot
        conversation = [
            _make_turn(turn=1, actor="brain", action="triage", status="evaluated"),
            _make_turn(turn=2, actor="brain", action="route", status="evaluated"),
            _make_turn(turn=3, actor="user", action="message", status="delivered"),
        ]
        event = _make_event(conversation=conversation)
        is_intermediate = False

        user_interrupt_turn: int | None = None
        if not is_intermediate:
            new_user_turns = [
                t for t in event.conversation[turn_snapshot:]
                if t.actor == "user" and t.status.value in ("sent", "delivered")
            ]
            if new_user_turns:
                user_interrupt_turn = new_user_turns[-1].turn

        assert user_interrupt_turn == 3
        assert turn_snapshot == original_snapshot

    def test_user_interrupt_iteration0_fallback(self):
        """Iteration 0 has no re-fetch — user turns arriving after snapshot aren't visible yet."""
        turn_snapshot = 3
        conversation = [
            _make_turn(turn=1, actor="brain", action="triage", status="evaluated"),
            _make_turn(turn=2, actor="brain", action="route", status="evaluated"),
            _make_turn(turn=3, actor="brain", action="wait", status="evaluated"),
        ]
        event = _make_event(conversation=conversation)
        is_intermediate = False

        user_interrupt_turn: int | None = None
        if not is_intermediate:
            new_user_turns = [
                t for t in event.conversation[turn_snapshot:]
                if t.actor == "user" and t.status.value in ("sent", "delivered")
            ]
            if new_user_turns:
                user_interrupt_turn = new_user_turns[-1].turn

        assert user_interrupt_turn is None


# =========================================================================
# Test 5-6: _process_event_inner wait guard scoping
# =========================================================================
class TestWaitGuardScope:
    def test_wait_guard_scoped_to_post_wait(self):
        """JARVIS DELIVERED at idx 3, wait set at idx 5 → guard holds (old turns don't false-clear)."""
        conversation = [
            _make_turn(turn=1, actor="brain", action="triage", status="evaluated"),
            _make_turn(turn=2, actor="brain", action="route", status="evaluated"),
            _make_turn(turn=3, actor="brain", action="wait", status="evaluated"),
            _make_turn(turn=4, actor="jarvis", action="message", status="delivered"),
            _make_turn(turn=5, actor="brain", action="thoughts", status="evaluated"),
            _make_turn(turn=6, actor="brain", action="wait", status="evaluated"),
        ]
        wait_turn = 6
        waiting_for_agent = {"evt-test": ("developer", wait_turn)}

        has_response = any(
            t.status.value == "delivered" and t.actor != "brain"
            for t in conversation[wait_turn:]
        )
        assert not has_response, "Guard should hold: JARVIS turn is before wait_turn"

    def test_wait_guard_clears_on_post_wait_agent(self):
        """Agent DELIVERED at idx 7, wait at idx 5 → cleared."""
        conversation = [
            _make_turn(turn=1, actor="brain", action="triage", status="evaluated"),
            _make_turn(turn=2, actor="brain", action="route", status="evaluated"),
            _make_turn(turn=3, actor="brain", action="wait", status="evaluated"),
            _make_turn(turn=4, actor="jarvis", action="message", status="delivered"),
            _make_turn(turn=5, actor="brain", action="wait", status="evaluated"),
            _make_turn(turn=6, actor="brain", action="thoughts", status="evaluated"),
            _make_turn(turn=7, actor="developer", action="result", status="delivered"),
        ]
        wait_turn = 5
        waiting_for_agent = {"evt-test": ("developer", wait_turn)}

        has_response = any(
            t.status.value == "delivered" and t.actor != "brain"
            for t in conversation[wait_turn:]
        )
        assert has_response, "Guard should clear: developer turn is after wait_turn"


# =========================================================================
# Test 7-8: Scan Guard 7 scoping
# =========================================================================
class TestScanGuard7Scope:
    def test_scan_guard7_unseen_fast_path(self):
        """Guard 7 wakes on fresh sent non-brain turn in unseen (edge-triggered)."""
        conversation = [
            _make_turn(turn=1, actor="brain", action="wait", status="evaluated"),
            _make_turn(turn=2, actor="developer", action="result", status="sent"),
        ]
        wait_turn = 1

        unseen = [t for t in conversation if t.status.value == "sent"]
        has_participant_input = any(t.actor != "brain" for t in unseen)
        if not has_participant_input:
            has_participant_input = any(
                t.status.value == "delivered" and t.actor != "brain"
                for t in conversation[wait_turn:]
            )
        assert has_participant_input, "Edge-triggered fast-path should wake on sent developer turn"

    def test_scan_guard7_delivered_boundary(self):
        """Guard 7 delivered check scoped to post-wait_turn only — pre-wait JARVIS doesn't wake."""
        conversation = [
            _make_turn(turn=1, actor="brain", action="triage", status="evaluated"),
            _make_turn(turn=2, actor="jarvis", action="message", status="delivered"),
            _make_turn(turn=3, actor="brain", action="route", status="evaluated"),
            _make_turn(turn=4, actor="brain", action="wait", status="evaluated"),
        ]
        wait_turn = 4

        unseen = [t for t in conversation if t.status.value == "sent"]
        has_participant_input = any(t.actor != "brain" for t in unseen)
        if not has_participant_input:
            has_participant_input = any(
                t.status.value == "delivered" and t.actor != "brain"
                for t in conversation[wait_turn:]
            )
        assert not has_participant_input, "Pre-wait JARVIS delivered turn should not wake Guard 7"


# =========================================================================
# Test 9: Survivor turn number (cross-source merge)
# =========================================================================
class TestSurvivorTurnNumber:
    def test_survivor_turn_number(self):
        """Cross-source merge at L841 uses _next_turn_number(eid) for survivor event, not event_id."""
        survivor_conversation = [
            _make_turn(turn=1, actor="brain", action="triage", status="evaluated"),
            _make_turn(turn=2, actor="brain", action="route", status="evaluated"),
            _make_turn(turn=3, actor="sysadmin", action="result", status="delivered"),
        ]
        current_conversation = [
            _make_turn(turn=1, actor="brain", action="triage", status="evaluated"),
        ]
        survivor = _make_event(event_id="evt-survivor", source="headhunter", conversation=survivor_conversation)
        current = _make_event(event_id="evt-current", source="aligner", conversation=current_conversation)

        survivor_next = len(survivor.conversation) + 1
        current_next = len(current.conversation) + 1

        assert survivor_next == 4, "Survivor event has 3 turns, next should be 4"
        assert current_next == 2, "Current event has 1 turn, next should be 2"
        assert survivor_next != current_next, "Using wrong event would produce wrong turn number"


# =========================================================================
# T-4, T-5: handle_wait_for_agent post-yield race detection
# =========================================================================
class TestHandlerPostYieldRace:
    """Post-yield validation in handle_wait_for_agent detects task completion race."""

    @staticmethod
    def _make_handler_brain(event: EventDocument | None = None) -> Brain:
        bb = MagicMock()
        bb.get_event = AsyncMock(return_value=event or _make_event())
        brain = Brain(blackboard=bb, agents={})
        brain._append_and_broadcast = AsyncMock(return_value=5)
        brain._broadcast_turn = AsyncMock()
        return brain

    @staticmethod
    def _latest_wait_turn(brain: Brain) -> ConversationTurn:
        return brain._append_and_broadcast.await_args.args[1]

    @pytest.mark.asyncio
    async def test_handler_post_yield_clears_when_task_gone(self):
        """T-4: task completed during yield → post-check clears waiting_for_agent."""
        brain = self._make_handler_brain()
        brain._active_agent_for_event["evt-test"] = "sysadmin"
        # Task is gone — completed during the append_and_broadcast yield
        # (is_task_running returns False)

        ctx = _BrainToolContext(brain)
        await handle_wait_for_agent(ctx, "evt-test", {"summary": "waiting"}, None)

        assert "evt-test" not in brain._waiting_for_agent, (
            "Post-yield check must clear waiting_for_agent when task is gone"
        )

    @pytest.mark.asyncio
    async def test_handler_no_clear_when_task_running(self):
        """T-5: task still running → waiting_for_agent stays set."""
        brain = self._make_handler_brain()
        brain._active_agent_for_event["evt-test"] = "sysadmin"
        brain._active_tasks["evt-test"] = MagicMock(
            done=MagicMock(return_value=False),
        )

        ctx = _BrainToolContext(brain)
        await handle_wait_for_agent(ctx, "evt-test", {"summary": "waiting"}, None)

        assert "evt-test" in brain._waiting_for_agent, (
            "waiting_for_agent must stay set when task is still running"
        )
        agent_name, wait_turn = brain._waiting_for_agent["evt-test"]
        assert agent_name == "sysadmin"
        assert wait_turn == 5  # returned by _append_and_broadcast mock

    @pytest.mark.asyncio
    async def test_handler_adds_nudge_evidence_after_two_prior_epoch_waits(self):
        event = _make_event(conversation=[
            _make_turn(turn=1, actor="brain", action="route"),
            _make_turn(turn=2, actor="brain", action="wait", waitingFor="agent:sysadmin"),
            _make_turn(turn=3, actor="brain", action="wait", waitingFor="agent:sysadmin"),
        ])
        brain = self._make_handler_brain(event=event)
        brain._active_agent_for_event["evt-test"] = "sysadmin"

        ctx = _BrainToolContext(brain)
        await handle_wait_for_agent(ctx, "evt-test", {"summary": "waiting"}, None)

        turn = self._latest_wait_turn(brain)
        assert "Wait #" in turn.evidence

    @pytest.mark.asyncio
    async def test_handler_first_wait_has_no_nudge_evidence(self):
        event = _make_event(conversation=[
            _make_turn(turn=1, actor="brain", action="route"),
        ])
        brain = self._make_handler_brain(event=event)
        brain._active_agent_for_event["evt-test"] = "sysadmin"

        ctx = _BrainToolContext(brain)
        await handle_wait_for_agent(ctx, "evt-test", {"summary": "waiting"}, None)

        turn = self._latest_wait_turn(brain)
        assert turn.evidence is None

    @pytest.mark.asyncio
    async def test_handler_keeps_summary_in_thoughts_and_puts_nudge_in_evidence(self):
        event = _make_event(conversation=[
            _make_turn(turn=1, actor="brain", action="route"),
            _make_turn(turn=2, actor="brain", action="wait", waitingFor="agent:sysadmin"),
            _make_turn(turn=3, actor="brain", action="wait", waitingFor="agent:sysadmin"),
        ])
        brain = self._make_handler_brain(event=event)
        brain._active_agent_for_event["evt-test"] = "sysadmin"

        ctx = _BrainToolContext(brain)
        await handle_wait_for_agent(ctx, "evt-test", {"summary": "doing X"}, None)

        turn = self._latest_wait_turn(brain)
        assert turn.thoughts == "doing X"
        assert "Wait #" in turn.evidence

    @pytest.mark.asyncio
    async def test_handler_second_wait_still_has_no_nudge_evidence(self):
        event = _make_event(conversation=[
            _make_turn(turn=1, actor="brain", action="route"),
            _make_turn(turn=2, actor="brain", action="wait", waitingFor="agent:sysadmin"),
        ])
        brain = self._make_handler_brain(event=event)
        brain._active_agent_for_event["evt-test"] = "sysadmin"

        ctx = _BrainToolContext(brain)
        await handle_wait_for_agent(ctx, "evt-test", {"summary": "waiting"}, None)

        turn = self._latest_wait_turn(brain)
        assert turn.evidence is None

    @pytest.mark.asyncio
    async def test_handler_writes_wait_turn_when_get_event_raises(self):
        """H1: a Redis blip on the nudge-count read must not abort the critical
        wait-turn write -- degrade to epoch_waits=0 and proceed unconditionally."""
        brain = self._make_handler_brain()
        brain._active_agent_for_event["evt-test"] = "sysadmin"
        brain._active_tasks["evt-test"] = MagicMock(done=MagicMock(return_value=False))
        brain.blackboard.get_event = AsyncMock(side_effect=RuntimeError("redis blip"))

        ctx = _BrainToolContext(brain)
        await handle_wait_for_agent(ctx, "evt-test", {"summary": "waiting"}, None)

        brain._append_and_broadcast.assert_awaited_once()
        turn = self._latest_wait_turn(brain)
        assert turn.action == "wait"
        assert turn.waitingFor == "agent:sysadmin"
        assert turn.evidence is None
        assert "evt-test" in brain._waiting_for_agent


# =========================================================================
# T-7: Guard 1 precedence over Guard 7 (regression)
# =========================================================================
class TestGuard1Precedence:
    """Guard 1 (running task) takes precedence over Guard 7 (waiting_for_agent)."""

    def test_guard1_precedence_jarvis_running_task(self):
        """T-7: Running task + JARVIS sent turn + waiting_for_agent → Guard 1 catches.

        Regression: Guard 7's new task-liveness check must NOT fire when
        Guard 1 already handles the event via its running-task continue.
        """
        conversation = [
            _make_turn(turn=1, actor="brain", action="route", status="evaluated"),
            _make_turn(turn=2, actor="jarvis", action="message", status="sent"),
        ]
        active_task = MagicMock(done=MagicMock(return_value=False))
        waiting_for_agent = {"evt-test": ("developer", 1)}

        # Guard 1 condition: task is running (not done)
        guard1_fires = not active_task.done()
        assert guard1_fires, "Precondition: Guard 1 must fire for running task"

        # Guard 1 finds unseen non-brain input (JARVIS sent turn) → enqueues
        unseen = [t for t in conversation if t.status.value == "sent"]
        has_new_input = any(t.actor != "brain" for t in unseen) or any(
            t.status.value == "delivered" and t.actor != "brain"
            for t in conversation
        )
        assert has_new_input, "Guard 1 should detect JARVIS sent turn as new input"

        # Guard 1's continue prevents Guard 7 from executing;
        # waiting_for_agent dict must remain intact
        assert "evt-test" in waiting_for_agent, (
            "waiting_for_agent must survive — Guard 7 never reached after Guard 1 continue"
        )


# =========================================================================
# T-2 (scan-lifecycle-fix-188): Error-result produces action="error"
# =========================================================================
class TestErrorResultTurnType:
    """Error result from dispatch_to_agent must write action='error', not 'execute'.

    Regression: Before the fix, "Error: ..." strings from dispatch passed through
    the normal result path and received action="execute", making it impossible for
    the Brain to distinguish agent errors from successful execution in conversation.
    """

    @staticmethod
    def _make_brain_for_run_agent_task() -> Brain:
        bb = AsyncMock()
        bb.get_event = AsyncMock(return_value=_make_event(
            event_id="evt-err", source="chat", conversation=[],
        ))
        bb.stamp_event = AsyncMock()
        bb.mark_turn_status = AsyncMock()
        bb.get_service = AsyncMock(return_value=None)
        brain = Brain(blackboard=bb, agents={})
        brain._ws_mode = "reverse"
        brain._append_and_broadcast = AsyncMock(return_value=5)
        brain._broadcast = AsyncMock()
        brain._broadcast_turn = AsyncMock()
        brain._broadcast_status_update = AsyncMock()
        brain._next_turn_number = AsyncMock(return_value=2)
        brain._is_event_closed = AsyncMock(return_value=False)
        brain._emit_executive_pulse = AsyncMock()
        brain.write_event_to_volume = AsyncMock()
        brain._scheduler = MagicMock()
        brain._scheduler.enqueue = MagicMock()
        brain._dispatch_semaphore = None
        brain._ephemeral_provisioner = None
        return brain

    @pytest.mark.asyncio
    async def test_error_result_writes_action_error(self):
        """T-2: dispatch returns 'Error: ...' → turn.action='error', no stamp_event, re-enqueue."""
        brain = self._make_brain_for_run_agent_task()

        mock_registry = AsyncMock()
        mock_registry.get_available = AsyncMock(return_value=None)
        mock_bridge = MagicMock()

        with (
            patch("src.dependencies.get_registry_and_bridge", return_value=(mock_registry, mock_bridge)),
            patch("src.agents.brain.dispatch_to_agent", new_callable=AsyncMock) as mock_dispatch,
        ):
            mock_dispatch.return_value = ("Error: Agent busy, task rejected.", None)

            await brain._run_agent_task(
                event_id="evt-err",
                agent_name="developer",
                agent=None,
                task="Fix the bug",
                event_md_path="/tmp/evt.md",
            )

        # Verify turn was written with action="error"
        assert brain._append_and_broadcast.call_count >= 1
        # Find the turn written after dispatch (skip initial "starting..." progress broadcast)
        written_turns = [
            call.args[1] for call in brain._append_and_broadcast.call_args_list
            if hasattr(call.args[1], "action")
        ]
        error_turns = [t for t in written_turns if t.action == "error"]
        assert len(error_turns) == 1, (
            f"Expected exactly one error turn, got actions: {[t.action for t in written_turns]}"
        )
        assert "Agent busy" in error_turns[0].thoughts or "Agent busy" in (error_turns[0].result or "")

        # stamp_event must NOT be called for errors (no last_completed_at)
        brain.blackboard.stamp_event.assert_not_called()

        # Event should be re-enqueued for Brain to decide next steps
        brain._scheduler.enqueue.assert_called_with("evt-err")

    @pytest.mark.asyncio
    async def test_successful_result_writes_action_execute(self):
        """Positive control: non-error dispatch result still produces action='execute'."""
        brain = self._make_brain_for_run_agent_task()

        mock_registry = AsyncMock()
        mock_registry.get_available = AsyncMock(return_value=None)
        mock_bridge = MagicMock()

        with (
            patch("src.dependencies.get_registry_and_bridge", return_value=(mock_registry, mock_bridge)),
            patch("src.agents.brain.dispatch_to_agent", new_callable=AsyncMock) as mock_dispatch,
        ):
            mock_dispatch.return_value = ("All done. Changes committed to branch.", "session-123")

            await brain._run_agent_task(
                event_id="evt-err",
                agent_name="developer",
                agent=None,
                task="Fix the bug",
                event_md_path="/tmp/evt.md",
            )

        written_turns = [
            call.args[1] for call in brain._append_and_broadcast.call_args_list
            if hasattr(call.args[1], "action")
        ]
        execute_turns = [t for t in written_turns if t.action == "execute"]
        assert len(execute_turns) == 1, (
            f"Expected action='execute' for successful result, got: {[t.action for t in written_turns]}"
        )

        # stamp_event IS called on success
        brain.blackboard.stamp_event.assert_called_once()


# =========================================================================
# QE regression (PR #192 HIGH finding follow-up): _agent_error_streak
# circuit-breaker/backoff transitions in _run_agent_task's error gate.
# =========================================================================
class TestAgentErrorCircuitBreaker:
    """Consecutive 'Error:' dispatch results for the same event must not
    re-enqueue unconditionally forever.

    Regression: before this fix, every "Error: ..." dispatch result re-enqueued
    the event immediately with zero backoff, so a deterministically failing
    agent looped forever (error -> enqueue -> dispatch -> error). The fix caps
    consecutive error results per event_id in `_agent_error_streak`:
      - streak 1 (of MAX_AGENT_ERROR_STREAK=3): immediate re-enqueue (legacy
        behavior preserved, covered by TestErrorResultTurnType above).
      - streak 2..last-1: defer via `_defer_event_safely` with backoff =
        AGENT_ERROR_BACKOFF_SECONDS * (streak - 1).
      - streak == MAX_AGENT_ERROR_STREAK: circuit-breaks -- pops the streak
        counter and force-closes the event via `_close_and_broadcast` instead
        of re-enqueueing or deferring.
    """

    @staticmethod
    def _make_brain_for_circuit_breaker(initial_streak: int = 0) -> Brain:
        brain = TestErrorResultTurnType._make_brain_for_run_agent_task()
        brain.execute_tool_locked = AsyncMock(return_value=None)
        brain._close_and_broadcast = AsyncMock()
        if initial_streak:
            brain._agent_error_streak["evt-err"] = initial_streak
        return brain

    @staticmethod
    def _patched_dispatch(brain: Brain, error_text: str = "Error: agent crashed"):
        mock_registry = AsyncMock()
        mock_registry.get_available = AsyncMock(return_value=None)
        mock_bridge = MagicMock()
        mock_dispatch_cm = patch(
            "src.agents.brain.dispatch_to_agent", new_callable=AsyncMock,
        )
        return (
            patch("src.dependencies.get_registry_and_bridge", return_value=(mock_registry, mock_bridge)),
            mock_dispatch_cm,
            error_text,
        )

    async def _run_with_error(self, brain: Brain, error_text: str = "Error: agent crashed"):
        registry_patch, dispatch_patch, error_text = self._patched_dispatch(brain, error_text)
        with registry_patch, dispatch_patch as mock_dispatch:
            mock_dispatch.return_value = (error_text, None)
            await brain._run_agent_task(
                event_id="evt-err",
                agent_name="developer",
                agent=None,
                task="Fix the bug",
                event_md_path="/tmp/evt.md",
            )

    @pytest.mark.asyncio
    async def test_streak_1_immediate_reenqueue_no_defer_no_close(self):
        """First consecutive error (streak=1): immediate re-enqueue, no defer, no circuit-break."""
        brain = self._make_brain_for_circuit_breaker(initial_streak=0)

        await self._run_with_error(brain)

        assert brain._agent_error_streak.get("evt-err") == 1
        brain._scheduler.enqueue.assert_called_once_with("evt-err")
        brain.execute_tool_locked.assert_not_called()
        brain._close_and_broadcast.assert_not_called()

    @pytest.mark.asyncio
    async def test_streak_2_defers_with_backoff_no_immediate_reenqueue(self):
        """Second consecutive error (streak=2): defers via execute_tool_locked(defer_event),
        with backoff = AGENT_ERROR_BACKOFF_SECONDS * (streak - 1); no immediate re-enqueue."""
        brain = self._make_brain_for_circuit_breaker(initial_streak=1)

        await self._run_with_error(brain)

        assert brain._agent_error_streak.get("evt-err") == 2
        brain._scheduler.enqueue.assert_not_called()
        brain._close_and_broadcast.assert_not_called()
        brain.execute_tool_locked.assert_called_once()
        call = brain.execute_tool_locked.call_args
        assert call.args[0] == "evt-err"
        assert call.args[1] == "defer_event"
        assert call.args[2]["delay_seconds"] == AGENT_ERROR_BACKOFF_SECONDS * (2 - 1)

    @pytest.mark.asyncio
    async def test_streak_3_trips_breaker_and_closes_event(self):
        """Third consecutive error (streak == MAX_AGENT_ERROR_STREAK): circuit-breaks --
        closes the event instead of re-enqueueing or deferring, and clears the streak."""
        brain = self._make_brain_for_circuit_breaker(initial_streak=MAX_AGENT_ERROR_STREAK - 1)

        await self._run_with_error(brain)

        assert "evt-err" not in brain._agent_error_streak, (
            "Streak counter must be cleared once the breaker trips"
        )
        brain._scheduler.enqueue.assert_not_called()
        brain.execute_tool_locked.assert_not_called()
        brain._close_and_broadcast.assert_called_once()
        close_call = brain._close_and_broadcast.call_args
        assert close_call.args[0] == "evt-err"
        assert close_call.kwargs.get("close_reason") == "error"

    @pytest.mark.asyncio
    async def test_streak_resets_after_non_error_result(self):
        """A successful (non-error) dispatch result clears any prior error streak."""
        brain = self._make_brain_for_circuit_breaker(initial_streak=2)

        registry_patch, dispatch_patch, _ = self._patched_dispatch(brain)
        with registry_patch, dispatch_patch as mock_dispatch:
            mock_dispatch.return_value = ("All done. Changes committed.", "session-123")
            await brain._run_agent_task(
                event_id="evt-err",
                agent_name="developer",
                agent=None,
                task="Fix the bug",
                event_md_path="/tmp/evt.md",
            )

        assert "evt-err" not in brain._agent_error_streak, (
            "Streak must reset to allow a fresh error streak after a successful result"
        )
