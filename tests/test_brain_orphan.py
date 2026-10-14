# BlackBoard/tests/test_brain_orphan.py
# @ai-rules:
# 1. [Constraint]: No Redis -- MagicMock blackboard only.
# 2. [Pattern]: Follows test_brain_close_paths.py structure: Brain(blackboard=mock, agents={}).
# 3. [Pattern]: Tests orphan recovery via _handle_orphan_blank_event, error-turn-on-failure
#    via _process_event_inner, brain_phase init, set_phase idempotency.
# 4. [Gotcha]: Orphan tests call the extracted helper directly -- no logic duplication.
"""Tests for blank event orphan recovery, first-turn error catch-all, and brain_phase initialization."""
from __future__ import annotations

import time
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.agents.brain import Brain
from src.models import ConversationTurn, EventDocument, EventEvidence, EventInput, EventStatus


def _make_blank_event(
    event_id: str = "evt-orphan-1",
    processing_started_at: float | None = None,
    brain_phase: str | None = None,
) -> EventDocument:
    evidence = EventEvidence(
        display_text="Test MR", source_type="headhunter", severity="info",
    )
    event = EventDocument(
        id=event_id,
        source="headhunter",
        service="test/repo",
        brain_phase=brain_phase,
        event=EventInput(reason="test", evidence=evidence),
        conversation=[],
        processing_started_at=processing_started_at,
    )
    return event


def _make_brain() -> Brain:
    bb = MagicMock()
    bb.EVENT_ACTIVE = "darwin:event:active"
    bb.EVENT_QUEUE = "darwin:queue"
    bb.EVENT_PREFIX = "darwin:event:"
    bb.redis = MagicMock()
    bb.redis.lpush = AsyncMock()
    bb.get_event = AsyncMock()
    bb.append_turn = AsyncMock(return_value=1)
    bb.close_event = AsyncMock()
    bb.persist_report = AsyncMock()
    bb.append_journal = AsyncMock()
    bb.record_event = AsyncMock()
    bb.mark_turns_evaluated = AsyncMock()
    bb.mark_turns_status = AsyncMock()
    bb.mark_turn_status = AsyncMock()
    bb.stamp_event = AsyncMock()
    bb.update_event_phase = AsyncMock()
    bb.get_active_events = AsyncMock(return_value=[])
    bb.get_recent_closed_for_service = AsyncMock(return_value=[])
    bb.generate_mermaid = AsyncMock(return_value="")
    brain = Brain(blackboard=bb, agents={})
    brain._broadcast = AsyncMock()
    brain._broadcast_turn = AsyncMock()
    brain._broadcast_status_update = AsyncMock()
    return brain


# =========================================================================
# Orphan recovery -- calls extracted _handle_orphan_blank_event directly
# =========================================================================

class TestOrphanRequeue:
    """Event loop scan: blank event orphan recovery via helper method."""

    @pytest.mark.asyncio
    async def test_requeue_blank_event_with_processing_started(self):
        """Blank event older than 180s with processing_started_at triggers LPUSH."""
        brain = _make_brain()
        event = _make_blank_event(processing_started_at=time.time() - 240)

        await brain._handle_orphan_blank_event("evt-orphan-1", event)

        brain.blackboard.redis.lpush.assert_awaited_once_with("darwin:queue", "evt-orphan-1")
        assert brain._orphan_requeue_count["evt-orphan-1"] == 1

    @pytest.mark.asyncio
    async def test_requeue_blank_event_with_queued_at_fallback(self):
        """Blank event with processing_started_at=None but queued_at > 180s triggers LPUSH."""
        brain = _make_brain()
        event = _make_blank_event(processing_started_at=None)
        event.queued_at = time.time() - 240

        await brain._handle_orphan_blank_event("evt-orphan-1", event)

        brain.blackboard.redis.lpush.assert_awaited_once_with("darwin:queue", "evt-orphan-1")
        assert brain._orphan_requeue_count["evt-orphan-1"] == 1

    @pytest.mark.asyncio
    async def test_skip_blank_event_without_any_timestamp(self):
        """Blank event with both timestamps None is skipped (no LPUSH)."""
        brain = _make_brain()
        event = _make_blank_event(processing_started_at=None)
        event.queued_at = None

        await brain._handle_orphan_blank_event("evt-orphan-1", event)

        brain.blackboard.redis.lpush.assert_not_awaited()
        assert "evt-orphan-1" not in brain._orphan_requeue_count

    @pytest.mark.asyncio
    async def test_skip_blank_event_under_180s(self):
        """Blank event younger than 180s is NOT re-queued."""
        brain = _make_brain()
        event = _make_blank_event(processing_started_at=time.time() - 10)

        await brain._handle_orphan_blank_event("evt-orphan-1", event)

        brain.blackboard.redis.lpush.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_cap_at_3_closes_as_error(self):
        """After 3 re-queue attempts, event is closed with error turn."""
        brain = _make_brain()
        event = _make_blank_event(processing_started_at=time.time() - 240)
        brain._orphan_requeue_count["evt-orphan-1"] = 3

        brain.blackboard.get_event = AsyncMock(return_value=event)
        await brain._handle_orphan_blank_event("evt-orphan-1", event)

        brain.blackboard.redis.lpush.assert_not_awaited()
        calls = brain.blackboard.append_turn.await_args_list
        assert len(calls) >= 1
        written_turn = calls[-1].args[1]
        assert written_turn.action == "error"
        brain.blackboard.close_event.assert_awaited()
        assert "evt-orphan-1" not in brain._orphan_requeue_count

    @pytest.mark.asyncio
    async def test_count_cleared_on_close(self):
        """_orphan_requeue_count is cleaned up in _close_and_broadcast."""
        brain = _make_brain()
        brain._orphan_requeue_count["evt-cleanup"] = 2

        event = _make_blank_event(event_id="evt-cleanup")
        event.conversation = [ConversationTurn(turn=1, actor="brain", action="triage")]
        brain.blackboard.get_event = AsyncMock(return_value=event)

        await brain._close_and_broadcast("evt-cleanup", "test close")

        assert "evt-cleanup" not in brain._orphan_requeue_count

    @pytest.mark.asyncio
    async def test_count_cleared_on_successful_recovery(self):
        """_orphan_requeue_count is reset in _process_event_inner when event has turns."""
        brain = _make_brain()
        brain._orphan_requeue_count["evt-recover"] = 2

        event = _make_blank_event(event_id="evt-recover")
        event.conversation = [ConversationTurn(turn=1, actor="brain", action="triage")]
        event.status = EventStatus.ACTIVE
        event.brain_phase = "triage"
        brain.blackboard.get_event = AsyncMock(return_value=event)
        brain._get_adapter = AsyncMock(return_value=None)

        await brain._process_event_inner("evt-recover")

        assert "evt-recover" not in brain._orphan_requeue_count


# =========================================================================
# Error turn on failure -- drives _process_event_inner
# =========================================================================

class TestErrorTurnOnFailure:
    """_process_event_inner catch-all: writes error turn when LLM fails before first turn."""

    @pytest.mark.asyncio
    async def test_error_turn_written_on_blank_failure(self):
        """When LLM path throws before any turn, an error turn is written."""
        brain = _make_brain()
        event = _make_blank_event(processing_started_at=time.time())
        event.status = EventStatus.ACTIVE
        event.brain_phase = "triage"

        brain.blackboard.get_event = AsyncMock(return_value=event)
        brain._get_adapter = AsyncMock(side_effect=RuntimeError("LLM unavailable"))

        with pytest.raises(RuntimeError, match="LLM unavailable"):
            await brain._process_event_inner("evt-orphan-1")

        calls = brain.blackboard.append_turn.await_args_list
        assert len(calls) >= 1
        written_turn = calls[-1].args[1]
        assert written_turn.action == "error"
        assert "LLM unavailable" in written_turn.thoughts

    @pytest.mark.asyncio
    async def test_error_turn_marked_evaluated(self):
        """Error turn is marked evaluated immediately to prevent hot retry loop."""
        brain = _make_brain()
        event = _make_blank_event(processing_started_at=time.time())
        event.status = EventStatus.ACTIVE
        event.brain_phase = "triage"

        brain.blackboard.get_event = AsyncMock(return_value=event)
        brain._get_adapter = AsyncMock(side_effect=RuntimeError("LLM down"))

        with pytest.raises(RuntimeError, match="LLM down"):
            await brain._process_event_inner("evt-orphan-1")

        brain.blackboard.mark_turns_status.assert_awaited()

    @pytest.mark.asyncio
    async def test_no_error_turn_if_conversation_exists(self):
        """When event already has a turn before failure, no duplicate error turn is written."""
        brain = _make_brain()
        event = _make_blank_event(processing_started_at=time.time())
        event.status = EventStatus.ACTIVE
        event.brain_phase = "triage"
        event.conversation = [ConversationTurn(turn=1, actor="brain", action="triage")]

        brain.blackboard.get_event = AsyncMock(return_value=event)
        brain._get_adapter = AsyncMock(side_effect=RuntimeError("LLM crash"))

        with pytest.raises(RuntimeError, match="LLM crash"):
            await brain._process_event_inner("evt-orphan-1")

        for call in brain.blackboard.append_turn.await_args_list:
            written_turn = call.args[1]
            assert written_turn.action != "error", "Error turn should NOT be written when conversation exists"


# =========================================================================
# evt-996e33ec: seeded user turns (atomic ingestion)
# =========================================================================

def _make_seeded_chat_event(
    event_id: str = "evt-seeded-1",
    processing_started_at: float | None = None,
    queued_at: float | None = None,
) -> EventDocument:
    """A chat event as create_event(initial_turns=[T1]) now produces it."""
    event = EventDocument(
        id=event_id,
        source="chat",
        service="general",
        brain_phase="triage",
        event=EventInput(
            reason="Hi Friday",
            evidence=EventEvidence(display_text="Hi Friday", source_type="chat", severity="info"),
        ),
        conversation=[ConversationTurn(turn=1, actor="user", action="message", thoughts="Hi Friday")],
        processing_started_at=processing_started_at,
        queued_at=queued_at if queued_at is not None else time.time(),
    )
    event.status = EventStatus.ACTIVE
    return event


class TestSeededUserTurnLifecycle:
    @pytest.mark.asyncio
    async def test_event_created_recorded_once_with_seeded_turn(self):
        """B-T10: BRAIN_EVENT_CREATED keys off processing_started_at, not blank conversation."""
        from src.models import EventType

        brain = _make_brain()
        brain._get_adapter = AsyncMock(side_effect=RuntimeError("stop here"))

        first = _make_seeded_chat_event(processing_started_at=None)
        brain.blackboard.get_event = AsyncMock(return_value=first)
        with pytest.raises(RuntimeError, match="stop here"):
            await brain._process_event_inner("evt-seeded-1")
        created = [
            c for c in brain.blackboard.record_event.await_args_list
            if c.args[0] == EventType.BRAIN_EVENT_CREATED
        ]
        assert len(created) == 1
        brain.blackboard.stamp_event.assert_awaited()

        brain.blackboard.record_event.reset_mock()
        second = _make_seeded_chat_event(processing_started_at=time.time() - 5)
        brain.blackboard.get_event = AsyncMock(return_value=second)
        with pytest.raises(RuntimeError, match="stop here"):
            await brain._process_event_inner("evt-seeded-1")
        assert not [
            c for c in brain.blackboard.record_event.await_args_list
            if c.args[0] == EventType.BRAIN_EVENT_CREATED
        ]

    @pytest.mark.asyncio
    async def test_first_processing_error_with_seeded_turn_writes_error_turn(self):
        """B-T12: a chat event holding only T1 still gets the first-processing error turn,
        and T1 plus the error turn (by number) are PROCESSED."""
        from src.models import MessageStatus

        brain = _make_brain()
        event = _make_seeded_chat_event(processing_started_at=time.time())
        brain.blackboard.get_event = AsyncMock(return_value=event)
        brain.blackboard.append_turn = AsyncMock(return_value=2)
        brain._get_adapter = AsyncMock(side_effect=RuntimeError("LLM unavailable"))

        with pytest.raises(RuntimeError, match="LLM unavailable"):
            await brain._process_event_inner("evt-seeded-1")

        written = brain.blackboard.append_turn.await_args_list[-1].args[1]
        assert written.action == "error"
        brain.blackboard.mark_turns_status.assert_awaited_with(
            "evt-seeded-1", up_to_turn=1, status=MessageStatus.PROCESSED,
        )
        brain.blackboard.mark_turn_status.assert_awaited_with(
            "evt-seeded-1", 2, MessageStatus.PROCESSED,
        )

    @pytest.mark.asyncio
    async def test_blank_chat_event_within_grace_defers(self):
        """B-T13a: a blank chat event inside the grace window returns before stamping."""
        brain = _make_brain()
        event = _make_seeded_chat_event(queued_at=time.time())
        event.conversation = []
        brain.blackboard.get_event = AsyncMock(return_value=event)

        await brain._process_event_inner("evt-seeded-1")

        brain.blackboard.stamp_event.assert_not_awaited()
        brain.blackboard.record_event.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_blank_chat_event_after_grace_processes(self):
        """B-T13b: past the grace window the legacy behaviour resumes (nothing loops forever)."""
        brain = _make_brain()
        event = _make_seeded_chat_event(queued_at=time.time() - 60)
        event.conversation = []
        brain.blackboard.get_event = AsyncMock(return_value=event)
        brain._get_adapter = AsyncMock(side_effect=RuntimeError("stop here"))

        with pytest.raises(RuntimeError, match="stop here"):
            await brain._process_event_inner("evt-seeded-1")

        brain.blackboard.stamp_event.assert_awaited()


class TestBlankEventGraceGuardClauses:
    """Pins every clause/boundary of the blank-event grace guard in _process_event_inner
    (@ai-rules #33; evt-996e33ec) so single-clause mutants die."""

    _NOW = 1_700_000_000.0

    @staticmethod
    async def _run(brain, event):
        brain.blackboard.get_event = AsyncMock(return_value=event)
        brain._get_adapter = AsyncMock(side_effect=RuntimeError("stop here"))
        try:
            await brain._process_event_inner(event.id)
            return "returned"
        except RuntimeError as e:
            assert "stop here" in str(e)
            return "processed"

    def _blank(self, *, source="chat", age=1.0, processing_started_at=None, queued_at="auto"):
        event = _make_seeded_chat_event(
            processing_started_at=processing_started_at,
            queued_at=self._NOW - age,
        )
        event.conversation = []
        event.source = source
        if queued_at != "auto":
            event.queued_at = queued_at
        return event

    @pytest.mark.asyncio
    @pytest.mark.parametrize("source", ["aligner", "jira", "headhunter"])
    async def test_blank_non_user_source_is_not_delayed(self, source):
        """Automated sources are legitimately created blank: never held by the grace window."""
        from unittest.mock import patch

        brain = _make_brain()
        with patch("src.agents.brain.time.time", return_value=self._NOW):
            outcome = await self._run(brain, self._blank(source=source, age=1.0))
        assert outcome == "processed"
        brain.blackboard.stamp_event.assert_awaited()

    @pytest.mark.asyncio
    async def test_blank_slack_event_within_grace_defers(self):
        from unittest.mock import patch

        brain = _make_brain()
        with patch("src.agents.brain.time.time", return_value=self._NOW):
            outcome = await self._run(brain, self._blank(source="slack", age=1.0))
        assert outcome == "returned"
        brain.blackboard.stamp_event.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_processing_started_at_bypasses_grace(self):
        """An already-stamped blank event (orphan re-queue) must proceed, not be deferred again."""
        from unittest.mock import patch

        brain = _make_brain()
        event = self._blank(source="chat", age=1.0, processing_started_at=self._NOW - 1.0)
        with patch("src.agents.brain.time.time", return_value=self._NOW):
            outcome = await self._run(brain, event)
        assert outcome == "processed"

    @pytest.mark.asyncio
    async def test_missing_queued_at_does_not_defer(self):
        """queued_at=None (legacy docs) must not be treated as 'just queued'."""
        from unittest.mock import patch

        brain = _make_brain()
        with patch("src.agents.brain.time.time", return_value=self._NOW):
            outcome = await self._run(brain, self._blank(source="chat", queued_at=None))
        assert outcome == "processed"

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "age,expected",
        [(0.0, "returned"), (9.99, "returned"), (10.0, "processed"), (10.01, "processed")],
    )
    async def test_grace_window_boundary(self, age, expected):
        """Exactly _BLANK_USER_EVENT_GRACE_SECONDS (10s) is OUT of the window (strict <)."""
        from unittest.mock import patch

        from src.agents.brain import _BLANK_USER_EVENT_GRACE_SECONDS

        assert _BLANK_USER_EVENT_GRACE_SECONDS == 10.0
        brain = _make_brain()
        with patch("src.agents.brain.time.time", return_value=self._NOW):
            outcome = await self._run(brain, self._blank(source="chat", age=age))
        assert outcome == expected

    @pytest.mark.asyncio
    async def test_seeded_non_blank_chat_event_is_not_delayed(self):
        """A chat event WITH its seeded turn is never held by the blank-event guard."""
        from unittest.mock import patch

        brain = _make_brain()
        event = _make_seeded_chat_event(queued_at=self._NOW - 1.0)
        with patch("src.agents.brain.time.time", return_value=self._NOW):
            outcome = await self._run(brain, event)
        assert outcome == "processed"


class TestHasNonUserTurnsSeedAware:
    """_has_non_user_turns vs the Slack follow-up brain.context seed (restart / first-error paths)."""

    @staticmethod
    def _slack_followup(*extra: ConversationTurn) -> EventDocument:
        event = _make_seeded_chat_event(processing_started_at=time.time())
        event.source = "slack"
        event.conversation = [
            ConversationTurn(turn=1, actor="brain", action="context", thoughts="prior ctx", source="system"),
            ConversationTurn(turn=2, actor="user", action="message", thoughts="and now?", source="slack"),
            *extra,
        ]
        return event

    def test_seeded_context_and_user_turns_are_not_brain_activity(self):
        from src.agents.brain import _has_non_user_turns

        assert _has_non_user_turns(self._slack_followup().conversation) is False

    def test_real_brain_turn_after_seed_counts(self):
        from src.agents.brain import _has_non_user_turns

        reply = ConversationTurn(turn=3, actor="brain", action="response", thoughts="hi")
        assert _has_non_user_turns(self._slack_followup(reply).conversation) is True

    def test_brain_context_without_system_source_counts(self):
        """Only the creation seed (source=system) is exempt; other brain.context turns are real."""
        from src.agents.brain import _has_non_user_turns

        turns = [ConversationTurn(turn=1, actor="brain", action="context", thoughts="x", source="slack")]
        assert _has_non_user_turns(turns) is True

    def test_agent_turn_counts_and_empty_is_false(self):
        from src.agents.brain import _has_non_user_turns

        assert _has_non_user_turns([]) is False
        assert _has_non_user_turns(
            [ConversationTurn(turn=1, actor="developer", action="result", thoughts="done")]
        ) is True

    @pytest.mark.asyncio
    async def test_first_error_path_writes_error_turn_for_slack_followup(self):
        """The Brain failing on a [context, user] follow-up still records the error turn."""
        brain = _make_brain()
        event = self._slack_followup()
        brain.blackboard.get_event = AsyncMock(return_value=event)
        brain.blackboard.append_turn = AsyncMock(return_value=3)
        brain._get_adapter = AsyncMock(side_effect=RuntimeError("LLM unavailable"))

        with pytest.raises(RuntimeError, match="LLM unavailable"):
            await brain._process_event_inner(event.id)

        written = brain.blackboard.append_turn.await_args_list[-1].args[1]
        assert written.action == "error"

    @pytest.mark.asyncio
    async def test_restart_cleanup_keeps_unprocessed_slack_followup(self):
        """Restart cleanup must NOT close a Slack follow-up the Brain never answered."""
        brain = _make_brain()
        event = self._slack_followup()
        event.status = EventStatus.ACTIVE
        brain.blackboard.get_active_events = AsyncMock(return_value=[event.id])
        brain.blackboard.get_event = AsyncMock(return_value=event)
        brain.blackboard.redis.srem = AsyncMock()
        brain._close_and_broadcast = AsyncMock()

        await brain._cleanup_stale_events()

        brain._close_and_broadcast.assert_not_awaited()
        brain.blackboard.close_event.assert_not_awaited()


# =========================================================================
# Phase initialization
# =========================================================================

class TestPhaseInitialization:
    """brain_phase set at creation + set_phase idempotent guard."""

    @pytest.mark.asyncio
    async def test_create_event_sets_brain_phase_triage(self):
        """New events should have brain_phase='triage' from create_event."""
        import fakeredis.aioredis
        from src.state.blackboard import BlackboardState

        real_bb = BlackboardState(redis=fakeredis.aioredis.FakeRedis())
        evidence = EventEvidence(
            display_text="test", source_type="chat", severity="info",
        )
        event_id = await real_bb.create_event(
            source="chat", service="test-svc", reason="test", evidence=evidence,
        )

        stored = await real_bb.get_event(event_id)
        assert stored.brain_phase == "triage"

    @pytest.mark.asyncio
    async def test_set_phase_triage_when_none_writes_turn(self):
        """set_phase('triage') when brain_phase is None should persist (NOT no-op)."""
        brain = _make_brain()
        event = _make_blank_event(brain_phase=None)
        event.conversation = [ConversationTurn(turn=1, actor="brain", action="triage")]
        brain.blackboard.get_event = AsyncMock(return_value=event)

        result = await brain._execute_function_call(
            "evt-orphan-1", "set_phase",
            {"phase": "triage", "reasoning": "Initial triage"},
            response_parts=None,
        )

        assert result is True
        brain.blackboard.update_event_phase.assert_awaited_once_with("evt-orphan-1", "triage")

    @pytest.mark.asyncio
    async def test_set_phase_triage_when_already_triage_writes_confirmation(self):
        """set_phase('triage') when brain_phase=='triage' writes a confirmation turn and re-invokes."""
        brain = _make_brain()
        event = _make_blank_event(brain_phase="triage")
        event.conversation = [ConversationTurn(turn=1, actor="brain", action="triage")]
        brain.blackboard.get_event = AsyncMock(return_value=event)

        result = await brain._execute_function_call(
            "evt-orphan-1", "set_phase",
            {"phase": "triage", "reasoning": "Re-triage"},
            response_parts=None,
        )

        assert result is True
        brain.blackboard.update_event_phase.assert_not_awaited()
        brain.blackboard.append_turn.assert_awaited_once()
        appended = brain.blackboard.append_turn.call_args[0][1]
        assert appended.action == "phase"
        assert "(confirmed)" in appended.thoughts
