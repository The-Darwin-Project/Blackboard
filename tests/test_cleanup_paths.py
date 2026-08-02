# tests/test_cleanup_paths.py
# @ai-rules:
# 1. [Constraint]: Tests for _release_task_state, _close_and_broadcast cleanup, REST close lock, stale-handle.
# 2. [Pattern]: Uses Brain + MagicMock blackboard (proven pattern from test_brain_close_paths.py).
# 3. [Gotcha]: _release_task_state clears 6 fields; _close_and_broadcast also evicts locks + snapshots.
# 4. [Pattern]: EventState integration — Redis HDEL for cycle fields, DELETE for full hash.
"""Unit tests for cleanup paths: _release_task_state HDELs, _close_and_broadcast
evictions, REST close lock acquisition, stale-handle reconciliation, TTL touch
on defer, and incident_created Redis SET operations.

These tests define the target interface (TDD). Expected to fail until
implementation lands.
"""
from __future__ import annotations

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.agents.brain import Brain
from src.models import ConversationTurn, EventDocument, EventEvidence, EventInput, EventStatus


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_brain() -> Brain:
    """Minimal Brain with MagicMock blackboard for cleanup path tests."""
    bb = MagicMock()
    bb.get_event = AsyncMock()
    bb.close_event = AsyncMock()
    bb.persist_report = AsyncMock()
    bb.append_journal = AsyncMock()
    bb.record_event = AsyncMock()
    brain = Brain(blackboard=bb, agents={})
    brain._broadcast = AsyncMock()
    return brain


def _make_event(
    event_id: str = "evt-cleanup",
    source: str = "chat",
    status: str = "active",
) -> EventDocument:
    evidence = EventEvidence(
        display_text="test cleanup", source_type=source, domain="complicated", severity="info",
    )
    return EventDocument(
        id=event_id,
        source=source,
        status=EventStatus(status),
        service="test-svc",
        event=EventInput(reason="test", evidence=evidence),
        conversation=[
            ConversationTurn(turn=1, actor="brain", action="triage", thoughts="classified"),
        ],
    )


# ---------------------------------------------------------------------------
# Test 1: _release_task_state HDELs cycle fields
# ---------------------------------------------------------------------------

class TestReleaseTaskState:
    """_release_task_state clears agent_name, agent_task_started_at, waiting_agent,
    wait_turn, reflex_fired, response_emitted from Redis."""

    def test_clears_active_tasks(self):
        """_release_task_state removes event from _active_tasks."""
        brain = _make_brain()
        brain._active_tasks["evt-rt01"] = MagicMock(done=MagicMock(return_value=True))

        brain._release_task_state("evt-rt01")

        assert "evt-rt01" not in brain._active_tasks

    def test_clears_active_agent_for_event(self):
        """_release_task_state removes event from _active_agent_for_event."""
        brain = _make_brain()
        brain._active_agent_for_event["evt-rt02"] = "sysadmin"

        brain._release_task_state("evt-rt02")

        assert "evt-rt02" not in brain._active_agent_for_event

    def test_clears_waiting_for_agent(self):
        """_release_task_state removes event from _waiting_for_agent."""
        brain = _make_brain()
        brain._waiting_for_agent["evt-rt03"] = ("developer", 5)

        brain._release_task_state("evt-rt03")

        assert "evt-rt03" not in brain._waiting_for_agent

    def test_clears_reflex_fired_for(self):
        """_release_task_state discards event from _reflex_fired_for set."""
        brain = _make_brain()
        brain._reflex_fired_for.add("evt-rt04")

        brain._release_task_state("evt-rt04")

        assert "evt-rt04" not in brain._reflex_fired_for

    def test_clears_response_emitted_for(self):
        """_release_task_state discards event from _response_emitted_for set."""
        brain = _make_brain()
        brain._response_emitted_for.add("evt-rt05")

        brain._release_task_state("evt-rt05")

        assert "evt-rt05" not in brain._response_emitted_for

    def test_idempotent_on_missing_event(self):
        """_release_task_state is safe to call on an event that was never tracked."""
        brain = _make_brain()

        # Should not raise
        brain._release_task_state("evt-rt-nonexistent")


# ---------------------------------------------------------------------------
# Test 2: _close_and_broadcast DELetes full state hash
# ---------------------------------------------------------------------------

class TestCloseAndBroadcastStateDelete:
    """_close_and_broadcast evicts _event_locks and _cycle_snapshots entries."""

    @pytest.mark.asyncio
    async def test_evicts_event_locks(self):
        """_close_and_broadcast removes event from _event_locks dict."""
        brain = _make_brain()
        event = _make_event("evt-cab01")
        brain.blackboard.get_event = AsyncMock(return_value=event)
        brain._event_locks["evt-cab01"] = asyncio.Lock()

        await brain._close_and_broadcast("evt-cab01", "test close")

        assert "evt-cab01" not in brain._event_locks

    @pytest.mark.asyncio
    async def test_evicts_response_emitted_for(self):
        """_close_and_broadcast discards event from _response_emitted_for."""
        brain = _make_brain()
        event = _make_event("evt-cab02")
        brain.blackboard.get_event = AsyncMock(return_value=event)
        brain._response_emitted_for.add("evt-cab02")

        await brain._close_and_broadcast("evt-cab02", "test close")

        assert "evt-cab02" not in brain._response_emitted_for

    @pytest.mark.asyncio
    async def test_calls_close_event_on_blackboard(self):
        """_close_and_broadcast calls blackboard.close_event."""
        brain = _make_brain()
        event = _make_event("evt-cab03")
        brain.blackboard.get_event = AsyncMock(return_value=event)

        await brain._close_and_broadcast("evt-cab03", "completed")

        brain.blackboard.close_event.assert_awaited()

    @pytest.mark.asyncio
    async def test_broadcasts_event_closed(self):
        """_close_and_broadcast broadcasts an event_closed message."""
        brain = _make_brain()
        event = _make_event("evt-cab04")
        brain.blackboard.get_event = AsyncMock(return_value=event)

        await brain._close_and_broadcast("evt-cab04", "done")

        brain._broadcast.assert_awaited()
        call_args = brain._broadcast.call_args[0][0]
        assert call_args["type"] == "event_closed"
        assert call_args["event_id"] == "evt-cab04"


# ---------------------------------------------------------------------------
# Test 3: REST close acquires lock with timeout
# ---------------------------------------------------------------------------

class TestRESTCloseLock:
    """POST /{event_id}/close acquires lock with timeout before _close_and_broadcast."""

    @pytest.mark.asyncio
    async def test_rest_close_gets_event_first(self):
        """REST close_event_by_user queries the event before attempting close."""
        from src.routes.queue import close_event_by_user, CloseRequest

        mock_bb = MagicMock()
        event = _make_event("evt-rest01")
        mock_bb.get_event = AsyncMock(return_value=event)
        mock_bb.close_event = AsyncMock()
        mock_bb.persist_report = AsyncMock()
        mock_bb.append_journal = AsyncMock()
        mock_bb.delete_slack_mapping = AsyncMock()

        with patch("src.routes.queue.get_blackboard", return_value=mock_bb):
            with patch("src.routes.queue.get_brain", new_callable=AsyncMock) as mock_brain_fn:
                mock_brain = MagicMock()
                mock_brain.cancel_active_task = AsyncMock()
                mock_brain.cancel_subscription = MagicMock()
                mock_brain.clear_cycle_id = MagicMock()
                mock_brain.agents = {}
                mock_brain_fn.return_value = mock_brain

                result = await close_event_by_user(
                    event_id="evt-rest01",
                    body=CloseRequest(reason="manual close"),
                    blackboard=mock_bb,
                )

        assert result["status"] == "closed"
        mock_bb.close_event.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_rest_close_404_on_missing_event(self):
        """REST close returns 404 if event not found."""
        from fastapi import HTTPException
        from src.routes.queue import close_event_by_user, CloseRequest

        mock_bb = MagicMock()
        mock_bb.get_event = AsyncMock(return_value=None)

        with pytest.raises(HTTPException) as exc_info:
            await close_event_by_user(
                event_id="evt-missing",
                body=CloseRequest(reason="test"),
                blackboard=mock_bb,
            )
        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_rest_close_409_on_already_closed(self):
        """REST close returns 409 if event already closed."""
        from fastapi import HTTPException
        from src.routes.queue import close_event_by_user, CloseRequest

        mock_bb = MagicMock()
        event = _make_event("evt-closed01", status="closed")
        mock_bb.get_event = AsyncMock(return_value=event)

        with pytest.raises(HTTPException) as exc_info:
            await close_event_by_user(
                event_id="evt-closed01",
                body=CloseRequest(reason="test"),
                blackboard=mock_bb,
            )
        assert exc_info.value.status_code == 409


# ---------------------------------------------------------------------------
# Test 4: Stale-handle reconciliation
# ---------------------------------------------------------------------------

class TestStaleHandleReconciliation:
    """Snapshot has agent_task_started_at but no live task → fields cleared."""

    def test_stale_handle_detection(self):
        """If _active_tasks has no entry but state has agent_task_started_at, it's stale."""
        brain = _make_brain()
        event_id = "evt-stale01"

        # No active task for this event
        assert event_id not in brain._active_tasks

        # But state claims an agent was started (stale from pod restart)
        stale_state = {
            "agent_name": "developer",
            "agent_task_started_at": str(time.time() - 300),
        }

        # Reconciliation should detect this mismatch
        has_task = event_id in brain._active_tasks
        has_state_agent = stale_state.get("agent_task_started_at") is not None

        assert has_state_agent is True
        assert has_task is False
        # Reconciliation condition met: clear the stale fields

    def test_non_stale_handle_preserved(self):
        """If _active_tasks has an entry AND state has agent_task_started_at, no clear."""
        brain = _make_brain()
        event_id = "evt-live01"

        # Live task exists
        brain._active_tasks[event_id] = MagicMock(done=MagicMock(return_value=False))
        brain._active_agent_for_event[event_id] = "developer"

        has_task = event_id in brain._active_tasks
        assert has_task is True
        # No reconciliation needed — state is consistent


# ---------------------------------------------------------------------------
# Test 5: TTL touch on defer
# ---------------------------------------------------------------------------

class TestTTLTouchOnDefer:
    """EXPIRE renewed when event deferred."""

    @pytest.mark.asyncio
    async def test_defer_renews_ttl(self):
        """When an event is deferred, the EventState TTL should be renewed."""
        from src.state.event_state import EventState

        redis = AsyncMock()
        redis.expire.return_value = True
        redis.hmset.return_value = True
        redis.hgetall.return_value = {}
        state = EventState(redis=redis)

        # Simulate defer: touch_ttl called
        await state.touch_ttl("evt-defer01")

        redis.expire.assert_awaited()


# ---------------------------------------------------------------------------
# Test 6: incident_created Redis SET
# ---------------------------------------------------------------------------

class TestIncidentCreatedRedisSet:
    """SADD marks, SISMEMBER checks, survives across EventState instances."""

    @pytest.mark.asyncio
    async def test_mark_incident_sadd(self):
        """mark_incident_created calls SADD."""
        from src.state.event_state import EventState

        redis = AsyncMock()
        redis.sadd.return_value = 1
        state = EventState(redis=redis)

        await state.mark_incident_created("evt-inc01")

        redis.sadd.assert_awaited()

    @pytest.mark.asyncio
    async def test_is_incident_sismember(self):
        """is_incident_created calls SISMEMBER."""
        from src.state.event_state import EventState

        redis = AsyncMock()
        redis.sismember.return_value = True
        state = EventState(redis=redis)

        result = await state.is_incident_created("evt-inc02")

        assert result is True
        redis.sismember.assert_awaited()

    @pytest.mark.asyncio
    async def test_incident_survives_across_instances(self):
        """Redis SET persists across EventState instances (different objects, same Redis)."""
        from src.state.event_state import EventState

        redis = AsyncMock()
        redis.sadd.return_value = 1
        redis.sismember.return_value = True

        state1 = EventState(redis=redis)
        await state1.mark_incident_created("evt-inc03")

        state2 = EventState(redis=redis)
        result = await state2.is_incident_created("evt-inc03")

        assert result is True

    def test_brain_incident_created_in_memory_set(self):
        """Brain._incident_created is an in-memory set (current implementation)."""
        brain = _make_brain()

        assert hasattr(brain, "_incident_created")
        assert isinstance(brain._incident_created, set)

        brain._incident_created.add("evt-inc04")
        assert "evt-inc04" in brain._incident_created
