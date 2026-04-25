# BlackBoard/tests/test_brain_orphan.py
# @ai-rules:
# 1. [Constraint]: No Redis -- MagicMock blackboard only.
# 2. [Pattern]: Follows test_brain_close_paths.py structure: Brain(blackboard=mock, agents={}).
# 3. [Pattern]: Tests orphan recovery via _handle_orphan_blank_event, error-turn-on-failure
#    via _process_event_inner, brain_phase init, set_phase idempotency.
# 4. [Gotcha]: Orphan tests call the extracted helper directly -- no logic duplication.
"""Tests for blank event orphan recovery, first-turn error catch-all, and brain_phase initialization."""
from __future__ import annotations

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

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
    bb.append_turn = AsyncMock()
    bb.close_event = AsyncMock()
    bb.persist_report = AsyncMock()
    bb.append_journal = AsyncMock()
    bb.record_event = AsyncMock()
    bb.mark_turns_evaluated = AsyncMock()
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
        """Blank event older than 60s with processing_started_at triggers LPUSH."""
        brain = _make_brain()
        event = _make_blank_event(processing_started_at=time.time() - 120)

        await brain._handle_orphan_blank_event("evt-orphan-1", event)

        brain.blackboard.redis.lpush.assert_awaited_once_with("darwin:queue", "evt-orphan-1")
        assert brain._orphan_requeue_count["evt-orphan-1"] == 1

    @pytest.mark.asyncio
    async def test_requeue_blank_event_with_queued_at_fallback(self):
        """Blank event with processing_started_at=None but queued_at > 60s triggers LPUSH."""
        brain = _make_brain()
        event = _make_blank_event(processing_started_at=None)
        event.queued_at = time.time() - 120

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
    async def test_skip_blank_event_under_60s(self):
        """Blank event younger than 60s is NOT re-queued."""
        brain = _make_brain()
        event = _make_blank_event(processing_started_at=time.time() - 10)

        await brain._handle_orphan_blank_event("evt-orphan-1", event)

        brain.blackboard.redis.lpush.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_cap_at_3_closes_as_error(self):
        """After 3 re-queue attempts, event is closed with error turn."""
        brain = _make_brain()
        event = _make_blank_event(processing_started_at=time.time() - 120)
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

        brain.blackboard.mark_turns_evaluated.assert_awaited()

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
# Phase initialization
# =========================================================================

class TestPhaseInitialization:
    """brain_phase set at creation + set_phase idempotent guard."""

    @pytest.mark.asyncio
    async def test_create_event_sets_brain_phase_triage(self):
        """New events should have brain_phase='triage' from create_event."""
        from src.state.blackboard import BlackboardState
        bb = MagicMock(spec=BlackboardState)
        bb.redis = MagicMock()
        bb.redis.set = AsyncMock()
        bb.redis.sadd = AsyncMock()
        bb.redis.lpush = AsyncMock()
        bb.EVENT_PREFIX = "darwin:event:"
        bb.EVENT_ACTIVE = "darwin:event:active"
        bb.EVENT_QUEUE = "darwin:queue"

        real_bb = BlackboardState.__new__(BlackboardState)
        real_bb.redis = bb.redis
        real_bb.EVENT_PREFIX = bb.EVENT_PREFIX
        real_bb.EVENT_ACTIVE = bb.EVENT_ACTIVE
        real_bb.EVENT_QUEUE = bb.EVENT_QUEUE

        evidence = EventEvidence(
            display_text="test", source_type="chat", severity="info",
        )
        event_id = await real_bb.create_event(
            source="chat", service="test-svc", reason="test", evidence=evidence,
        )

        import json
        stored_call = bb.redis.set.await_args
        stored_json = json.loads(stored_call.args[1])
        assert stored_json["brain_phase"] == "triage"

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
    async def test_set_phase_triage_when_already_triage_is_noop(self):
        """set_phase('triage') when brain_phase=='triage' is idempotent no-op."""
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
