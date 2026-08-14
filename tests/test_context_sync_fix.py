# BlackBoard/tests/test_context_sync_fix.py
# @ai-rules:
# 1. [Constraint]: Regression tests for PR #184 (evt-4eeff00c) -- immediate enqueue on message
#    ingestion (RC-1) and in-memory DELIVERED sync after mark_turns_delivered (RC-2).
# 2. [Pattern]: Brain fixtures follow tests/test_brain_orphan.py -- Brain(blackboard=MagicMock(), agents={}).
# 3. [Pattern]: _scan_active_for_reconcile is exercised directly (the real method), not the
#    Probe-B mirror in test_scan_callback.py, because the mirror hard-codes the DELIVERED
#    transition as "status transition only in real scan" and therefore cannot catch RC-2.
# 4. [Gotcha]: Brain._memory_reflex_enabled defaults to False (env-gated) -- no background
#    asyncio.create_task warmup task is spawned by _scan_active_for_reconcile in these tests.
"""Regression tests for the brain.py context synchronization fix (PR #184).

Covers:
- Brain.enqueue_for_processing (Fix 1): new public method, scheduler delegation + safe no-op.
- _scan_active_for_reconcile in-memory DELIVERED sync (Fix 2): a freshly SENT turn must be
  visible as "unread" within the SAME scan pass, not the next one.
- Ingestion call sites (dashboard_ws, slack, queue.py REST) actually invoke the new method.
"""
from __future__ import annotations

import time
from unittest.mock import AsyncMock, MagicMock, patch

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
from src.scheduling.reconciler import ReconcileScheduler


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_brain() -> Brain:
    """Real Brain instance with a MagicMock blackboard (no Redis)."""
    bb = MagicMock()
    bb.EVENT_ACTIVE = "darwin:event:active"
    bb.EVENT_QUEUE = "darwin:queue"
    bb.EVENT_PREFIX = "darwin:event:"
    bb.redis = MagicMock()
    bb.redis.lpush = AsyncMock()
    bb.get_event = AsyncMock()
    bb.get_active_events_with_status = AsyncMock(return_value={})
    bb.append_turn = AsyncMock(return_value=1)
    bb.mark_turns_delivered = AsyncMock(return_value=1)
    bb.mark_turns_evaluated = AsyncMock()
    bb.mark_turns_status = AsyncMock()
    bb.stamp_event = AsyncMock()
    bb.update_event_phase = AsyncMock()
    bb.close_event = AsyncMock()
    bb.persist_report = AsyncMock()
    bb.append_journal = AsyncMock()
    bb.record_event = AsyncMock()
    bb.get_recent_closed_for_service = AsyncMock(return_value=[])
    bb.generate_mermaid = AsyncMock(return_value="")
    brain = Brain(blackboard=bb, agents={})
    brain._broadcast = AsyncMock()
    brain._broadcast_turn = AsyncMock()
    brain._broadcast_status_update = AsyncMock()
    return brain


def _make_event(
    event_id: str = "evt-sync-1",
    conversation: list | None = None,
    status: EventStatus = EventStatus.ACTIVE,
) -> EventDocument:
    evidence = EventEvidence(display_text="test", source_type="dashboard", severity="info")
    return EventDocument(
        id=event_id,
        source="chat",
        status=status,
        service="test-svc",
        event=EventInput(reason="test", evidence=evidence),
        conversation=conversation or [],
    )


def _make_turn(actor: str, action: str, status: MessageStatus, turn: int = 1) -> ConversationTurn:
    return ConversationTurn(turn=turn, actor=actor, action=action, status=status, thoughts="hi")


# ---------------------------------------------------------------------------
# Fix 1: Brain.enqueue_for_processing
# ---------------------------------------------------------------------------


class TestEnqueueForProcessing:
    def test_delegates_to_scheduler(self):
        """enqueue_for_processing forwards to the real scheduler and enqueues the event."""
        brain = _make_brain()
        scheduler = ReconcileScheduler(reconcile_fn=AsyncMock())
        brain._scheduler = scheduler

        assert brain.enqueue_for_processing("evt-1") is True
        assert "evt-1" in scheduler.tracked_event_ids()

    def test_dedup_matches_scheduler_semantics(self):
        """A second immediate call for the same event is a no-op (FairQueue dedup), same as
        the 8 pre-existing call sites in brain.py (agent wake, resume_if_parked, defer wake)."""
        brain = _make_brain()
        scheduler = ReconcileScheduler(reconcile_fn=AsyncMock())
        brain._scheduler = scheduler

        assert brain.enqueue_for_processing("evt-1") is True
        assert brain.enqueue_for_processing("evt-1") is False  # still pending -> dedup

    def test_safe_noop_when_scheduler_not_initialized(self):
        """Before start_event_loop() sets self._scheduler, the method must not raise."""
        brain = _make_brain()
        brain._scheduler = None

        assert brain.enqueue_for_processing("evt-1") is False


# ---------------------------------------------------------------------------
# Fix 2: in-memory DELIVERED sync eliminates the two-scan delay (RC-2)
# ---------------------------------------------------------------------------


class TestScanActiveForReconcileImmediateVisibility:
    @pytest.mark.asyncio
    async def test_freshly_sent_turn_enqueued_within_single_scan(self):
        """RC-2 regression: a SENT turn on an otherwise-idle active event must be picked up
        for reconciliation in the SAME _scan_active_for_reconcile() call that marks it
        DELIVERED -- not the following scan cycle."""
        brain = _make_brain()
        turn = _make_turn("user", "message", MessageStatus.SENT)
        event = _make_event(conversation=[turn])

        brain.blackboard.get_active_events_with_status = AsyncMock(
            return_value={"evt-sync-1": "active"}
        )
        brain.blackboard.get_event = AsyncMock(return_value=event)

        to_enqueue = await brain._scan_active_for_reconcile()

        assert to_enqueue == ["evt-sync-1"]
        brain.blackboard.mark_turns_delivered.assert_awaited_once_with("evt-sync-1", 1)

    @pytest.mark.asyncio
    async def test_in_memory_turn_status_synced_to_delivered(self):
        """The exact Fix-2 side effect: after mark_turns_delivered, the in-memory turn
        object must be updated too, not just Redis."""
        brain = _make_brain()
        turn = _make_turn("user", "message", MessageStatus.SENT)
        event = _make_event(conversation=[turn])

        brain.blackboard.get_active_events_with_status = AsyncMock(
            return_value={"evt-sync-1": "active"}
        )
        brain.blackboard.get_event = AsyncMock(return_value=event)

        await brain._scan_active_for_reconcile()

        assert turn.status == MessageStatus.DELIVERED

    @pytest.mark.asyncio
    async def test_no_false_positive_when_no_unseen_turns_and_recently_processed(self):
        """Sanity/no-regression: an event with only EVALUATED turns and a recent
        last_processed timestamp is NOT enqueued (guard 10-11 unaffected by the fix)."""
        brain = _make_brain()
        turn = _make_turn("brain", "response", MessageStatus.EVALUATED)
        event = _make_event(conversation=[turn])

        brain.blackboard.get_active_events_with_status = AsyncMock(
            return_value={"evt-sync-1": "active"}
        )
        brain.blackboard.get_event = AsyncMock(return_value=event)
        brain._last_processed["evt-sync-1"] = time.time()

        to_enqueue = await brain._scan_active_for_reconcile()

        assert to_enqueue == []
        brain.blackboard.mark_turns_delivered.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_waiting_for_user_cleared_immediately_when_user_replies(self):
        """Interaction with the pre-existing user-message bypass (brain.py ~5195): when
        Brain is parked waiting_for_user and the user's reply arrives as a SENT turn, Fix 2
        makes it visible as DELIVERED in the SAME scan, so the bypass fires immediately
        instead of needing a second scan cycle to see it (this is the exact evt-4eeff00c
        symptom -- FRIDAY parked while a reply sits unseen for 5-10s)."""
        brain = _make_brain()
        turn = _make_turn("user", "message", MessageStatus.SENT)
        event = _make_event(conversation=[turn])

        brain.blackboard.get_active_events_with_status = AsyncMock(
            return_value={"evt-sync-1": "active"}
        )
        brain.blackboard.get_event = AsyncMock(return_value=event)
        brain._waiting_for_user["evt-sync-1"] = time.time()

        to_enqueue = await brain._scan_active_for_reconcile()

        assert to_enqueue == ["evt-sync-1"]
        assert "evt-sync-1" not in brain._waiting_for_user  # bypass cleared the wait
        assert turn.status == MessageStatus.DELIVERED

    @pytest.mark.asyncio
    async def test_waiting_for_user_suppresses_enqueue_for_non_user_turn(self):
        """Guard 9 still applies when the freshly-delivered turn is NOT from the user (e.g.
        a system/brain-authored turn) -- only an actual user reply clears the wait."""
        brain = _make_brain()
        turn = _make_turn("system", "evidence", MessageStatus.SENT)
        event = _make_event(conversation=[turn])

        brain.blackboard.get_active_events_with_status = AsyncMock(
            return_value={"evt-sync-1": "active"}
        )
        brain.blackboard.get_event = AsyncMock(return_value=event)
        brain._waiting_for_user["evt-sync-1"] = time.time()

        to_enqueue = await brain._scan_active_for_reconcile()

        assert to_enqueue == []
        assert "evt-sync-1" in brain._waiting_for_user  # still parked
        # Fix 2 still runs the Redis + in-memory sync regardless of the wait state
        assert turn.status == MessageStatus.DELIVERED


# ---------------------------------------------------------------------------
# Fix 1: ingestion call sites actually invoke enqueue_for_processing
# ---------------------------------------------------------------------------


class TestDashboardWsIngestionEnqueues:
    def _make_adapter(self):
        from src.adapters.dashboard_ws import DashboardWSAdapter

        blackboard = AsyncMock()
        brain = MagicMock()
        brain.clear_waiting = MagicMock()
        brain.resume_if_parked = AsyncMock()
        brain.enqueue_for_processing = MagicMock()
        adapter = DashboardWSAdapter(brain=brain, blackboard=blackboard, auth_enabled=False)
        return adapter, blackboard, brain

    @pytest.mark.asyncio
    async def test_user_message_enqueues_immediately(self):
        adapter, blackboard, brain = self._make_adapter()
        blackboard.get_event.return_value = _make_event(conversation=[])
        ws = AsyncMock()
        user = MagicMock(label="Tal")

        await adapter._handle_user_message(
            ws, {"event_id": "evt-sync-1", "message": "hello"}, user
        )

        brain.enqueue_for_processing.assert_called_once_with("evt-sync-1")

    @pytest.mark.asyncio
    async def test_approve_enqueues_immediately(self):
        adapter, blackboard, brain = self._make_adapter()
        blackboard.get_event.return_value = _make_event(conversation=[])
        ws = AsyncMock()
        user = MagicMock(label="Tal")

        await adapter._handle_approve(ws, {"event_id": "evt-sync-1"}, user)

        brain.enqueue_for_processing.assert_called_once_with("evt-sync-1")

    @pytest.mark.asyncio
    async def test_user_message_no_enqueue_when_event_missing(self):
        """Guard: unknown event_id must short-circuit before any brain call."""
        adapter, blackboard, brain = self._make_adapter()
        blackboard.get_event.return_value = None
        ws = AsyncMock()
        user = MagicMock(label="Tal")

        await adapter._handle_user_message(
            ws, {"event_id": "evt-missing", "message": "hello"}, user
        )

        brain.enqueue_for_processing.assert_not_called()

    @pytest.mark.asyncio
    async def test_user_message_no_enqueue_when_message_empty(self):
        """Guard: missing message text short-circuits before the blackboard lookup."""
        adapter, blackboard, brain = self._make_adapter()
        ws = AsyncMock()
        user = MagicMock(label="Tal")

        await adapter._handle_user_message(
            ws, {"event_id": "evt-sync-1", "message": ""}, user
        )

        blackboard.get_event.assert_not_called()
        brain.enqueue_for_processing.assert_not_called()


class TestSlackIngestionEnqueues:
    @pytest.mark.asyncio
    async def test_threaded_reply_enqueues_immediately(self):
        """Reuses the SlackChannel test harness from test_slack_channel.py to confirm the
        new call is wired into the real on_dm_message handler, not just the diff."""
        from tests.test_slack_channel import _make_channel, _mock_event_doc, _dm_event, _user_info_response

        sc, captured = _make_channel()
        on_dm = captured["event:message"]
        sc._brain.enqueue_for_processing = MagicMock()

        event_doc = _mock_event_doc(event_id="evt-exist01", status="active")
        sc._blackboard.get_event_by_slack_thread.return_value = "evt-exist01"
        sc._blackboard.get_event.return_value = event_doc

        client = AsyncMock()
        client.users_info.return_value = _user_info_response("Charlie")

        await on_dm(_dm_event(text="follow up", thread_ts="1700000001.000001"), client)

        sc._brain.enqueue_for_processing.assert_called_once_with("evt-exist01")


class TestQueueRouteIngestionEnqueues:
    @pytest.mark.asyncio
    async def test_approve_event_route_enqueues_immediately(self):
        from src.routes import queue as queue_routes

        event = _make_event(event_id="evt-sync-1", conversation=[])
        blackboard = AsyncMock()
        blackboard.get_event.return_value = event

        brain = MagicMock()
        brain.clear_waiting = MagicMock()
        brain.resume_if_parked = AsyncMock(return_value=True)
        brain.enqueue_for_processing = MagicMock()

        with patch.object(queue_routes, "get_brain", AsyncMock(return_value=brain)):
            result = await queue_routes.approve_event(
                event_id="evt-sync-1", blackboard=blackboard
            )

        assert result["status"] == "approved"
        brain.enqueue_for_processing.assert_called_once_with("evt-sync-1")

    @pytest.mark.asyncio
    async def test_reject_event_route_enqueues_immediately(self):
        from src.routes import queue as queue_routes

        event = _make_event(event_id="evt-sync-1", conversation=[])
        blackboard = AsyncMock()
        blackboard.get_event.return_value = event

        brain = MagicMock()
        brain.clear_waiting = MagicMock()
        brain.resume_if_parked = AsyncMock(return_value=True)
        brain.enqueue_for_processing = MagicMock()

        with patch.object(queue_routes, "get_brain", AsyncMock(return_value=brain)):
            result = await queue_routes.reject_event(
                event_id="evt-sync-1", blackboard=blackboard
            )

        assert result["status"] == "rejected"
        brain.enqueue_for_processing.assert_called_once_with("evt-sync-1")
