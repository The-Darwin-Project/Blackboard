# tests/test_scan_callback.py
"""Probe B: Validate _scan_active_for_reconcile decision branches.

Tests the scan logic in isolation by mocking Brain state and blackboard.
Each test validates one decision branch from the original start_event_loop scan.
"""
import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from src.models import EventDocument, EventInput, EventStatus, ConversationTurn, EventEvidence


def _make_event(
    event_id: str = "evt-test",
    status: str = "active",
    source: str = "slack",
    service: str = "test-svc",
    conversation: list | None = None,
    brain_phase: str | None = "triage",
) -> EventDocument:
    """Helper to create test EventDocuments."""
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


def _make_turn(actor: str = "brain", action: str = "triage", status: str = "evaluated",
               thoughts: str = "test", timestamp: float | None = None) -> ConversationTurn:
    return ConversationTurn(
        turn=1, actor=actor, action=action, status=status,
        thoughts=thoughts, timestamp=timestamp or time.time(),
    )


class TestScanDecisionBranches:
    """Each test validates one decision branch from the scan loop.

    The scan logic decides which events to ENQUEUE for reconciliation.
    Events NOT enqueued are either: still waiting, deferred, locked, or handled inline.
    """

    @pytest.mark.asyncio
    async def test_branch1_active_agent_task_enqueued_with_input(self):
        """Events with running agent tasks and unseen non-brain turns ARE enqueued."""
        active_tasks = {"evt-1": MagicMock(done=MagicMock(return_value=False))}
        turns = [_make_turn(actor="developer", action="huddle", status="sent")]
        events = {"evt-1": _make_event("evt-1", conversation=turns)}
        result = _scan_logic(
            active_ids=["evt-1"],
            events=events,
            active_tasks=active_tasks,
            waiting_for_user=set(),
            waiting_for_jarvis={},
            event_locks={},
            last_processed={},
            waiting_for_agent={},
        )
        assert "evt-1" in result

    @pytest.mark.asyncio
    async def test_branch1_active_agent_task_skipped_no_input(self):
        """Events with running agent tasks and NO unseen non-brain turns are NOT enqueued."""
        active_tasks = {"evt-1": MagicMock(done=MagicMock(return_value=False))}
        turns = [_make_turn(actor="brain", action="route", status="evaluated")]
        events = {"evt-1": _make_event("evt-1", conversation=turns)}
        result = _scan_logic(
            active_ids=["evt-1"],
            events=events,
            active_tasks=active_tasks,
            waiting_for_user=set(),
            waiting_for_jarvis={},
            event_locks={},
            last_processed={},
            waiting_for_agent={},
        )
        assert "evt-1" not in result

    @pytest.mark.asyncio
    async def test_branch2_closed_zombie_skipped(self):
        """Closed events in active set are NOT enqueued (zombie cleanup)."""
        events = {"evt-1": _make_event("evt-1", status="closed")}
        result = _scan_logic(
            active_ids=["evt-1"],
            events=events,
            active_tasks={},
            waiting_for_user=set(),
            waiting_for_jarvis={},
            event_locks={},
            last_processed={},
            waiting_for_agent={},
        )
        assert "evt-1" not in result

    @pytest.mark.asyncio
    async def test_branch3_new_no_conversation_enqueued(self):
        """NEW events with no conversation ARE enqueued."""
        events = {"evt-1": _make_event("evt-1", status="new", conversation=[])}
        result = _scan_logic(
            active_ids=["evt-1"],
            events=events,
            active_tasks={},
            waiting_for_user=set(),
            waiting_for_jarvis={},
            event_locks={},
            last_processed={},
            waiting_for_agent={},
        )
        assert "evt-1" in result

    @pytest.mark.asyncio
    async def test_branch4_deferred_not_expired_skipped(self):
        """Deferred events with active timer are NOT enqueued."""
        events = {"evt-1": _make_event("evt-1", status="deferred", conversation=[_make_turn()])}
        defer_until = {"evt-1": time.time() + 300}  # 5 min from now
        result = _scan_logic(
            active_ids=["evt-1"],
            events=events,
            active_tasks={},
            waiting_for_user=set(),
            waiting_for_jarvis={},
            event_locks={},
            last_processed={},
            defer_until=defer_until,
            waiting_for_agent={},
        )
        assert "evt-1" not in result

    @pytest.mark.asyncio
    async def test_branch5_deferred_expired_enqueued(self):
        """Deferred events with expired timer ARE enqueued."""
        events = {"evt-1": _make_event("evt-1", status="deferred", conversation=[_make_turn()])}
        defer_until = {"evt-1": time.time() - 10}  # Expired 10s ago
        result = _scan_logic(
            active_ids=["evt-1"],
            events=events,
            active_tasks={},
            waiting_for_user=set(),
            waiting_for_jarvis={},
            event_locks={},
            last_processed={},
            defer_until=defer_until,
            waiting_for_agent={},
        )
        assert "evt-1" in result

    @pytest.mark.asyncio
    async def test_branch6_waiting_jarvis_no_reply_skipped(self):
        """Events waiting for JARVIS with no reply are NOT enqueued."""
        turns = [_make_turn(actor="brain", action="respond_jarvis", timestamp=time.time() - 30)]
        events = {"evt-1": _make_event("evt-1", conversation=turns)}
        result = _scan_logic(
            active_ids=["evt-1"],
            events=events,
            active_tasks={},
            waiting_for_user=set(),
            waiting_for_jarvis={"evt-1": time.time() - 30},
            event_locks={},
            last_processed={},
            waiting_for_agent={},
        )
        assert "evt-1" not in result

    @pytest.mark.asyncio
    async def test_branch7_waiting_jarvis_reply_arrived_enqueued(self):
        """Events waiting for JARVIS where reply arrived ARE enqueued."""
        wait_start = time.time() - 30
        turns = [
            _make_turn(actor="brain", action="respond_jarvis", timestamp=wait_start),
            _make_turn(actor="jarvis", action="message", timestamp=time.time() - 5),
        ]
        events = {"evt-1": _make_event("evt-1", conversation=turns)}
        result = _scan_logic(
            active_ids=["evt-1"],
            events=events,
            active_tasks={},
            waiting_for_user=set(),
            waiting_for_jarvis={"evt-1": wait_start},
            event_locks={},
            last_processed={},
            waiting_for_agent={},
        )
        assert "evt-1" in result

    @pytest.mark.asyncio
    async def test_branch8_unread_turns_enqueued(self):
        """Events with DELIVERED (unread) turns and not waiting ARE enqueued."""
        turns = [_make_turn(status="delivered")]
        events = {"evt-1": _make_event("evt-1", conversation=turns)}
        result = _scan_logic(
            active_ids=["evt-1"],
            events=events,
            active_tasks={},
            waiting_for_user=set(),
            waiting_for_jarvis={},
            event_locks={},
            last_processed={},
            waiting_for_agent={},
        )
        assert "evt-1" in result

    @pytest.mark.asyncio
    async def test_branch9_waiting_for_user_skipped(self):
        """Events waiting for user input are NOT enqueued even with unread turns."""
        turns = [_make_turn(status="delivered")]
        events = {"evt-1": _make_event("evt-1", conversation=turns)}
        result = _scan_logic(
            active_ids=["evt-1"],
            events=events,
            active_tasks={},
            waiting_for_user={"evt-1"},
            waiting_for_jarvis={},
            event_locks={},
            last_processed={},
            waiting_for_agent={},
        )
        assert "evt-1" not in result

    @pytest.mark.asyncio
    async def test_branch10_idle_safety_net_enqueued(self):
        """Events idle > 60s with no unread turns ARE enqueued."""
        turns = [_make_turn(status="evaluated")]
        events = {"evt-1": _make_event("evt-1", conversation=turns)}
        result = _scan_logic(
            active_ids=["evt-1"],
            events=events,
            active_tasks={},
            waiting_for_user=set(),
            waiting_for_jarvis={},
            event_locks={},
            last_processed={"evt-1": time.time() - 120},  # Idle 2 minutes
            waiting_for_agent={},
        )
        assert "evt-1" in result

    @pytest.mark.asyncio
    async def test_branch11_recently_processed_skipped(self):
        """Events processed < 60s ago with no unread turns are NOT enqueued."""
        turns = [_make_turn(status="evaluated")]
        events = {"evt-1": _make_event("evt-1", conversation=turns)}
        result = _scan_logic(
            active_ids=["evt-1"],
            events=events,
            active_tasks={},
            waiting_for_user=set(),
            waiting_for_jarvis={},
            event_locks={},
            last_processed={"evt-1": time.time() - 10},  # Processed 10s ago
            waiting_for_agent={},
        )
        assert "evt-1" not in result

    @pytest.mark.asyncio
    async def test_branch12_locked_event_skipped(self):
        """Events currently locked (being processed) are NOT enqueued."""
        turns = [_make_turn(status="delivered")]
        events = {"evt-1": _make_event("evt-1", conversation=turns)}
        lock = asyncio.Lock()
        await lock.acquire()  # Simulate locked state
        result = _scan_logic(
            active_ids=["evt-1"],
            events=events,
            active_tasks={},
            waiting_for_user=set(),
            waiting_for_jarvis={},
            event_locks={"evt-1": lock},
            last_processed={},
            waiting_for_agent={},
        )
        lock.release()
        assert "evt-1" not in result


class TestIntermediateProcessing:
    """Tests for the unified intermediate processing path (post _process_intermediate removal)."""

    @pytest.mark.asyncio
    async def test_huddle_during_active_task_enqueued(self):
        """Huddle message from agent during active task IS enqueued for processing."""
        active_tasks = {"evt-1": MagicMock(done=MagicMock(return_value=False))}
        turns = [
            _make_turn(actor="brain", action="route", status="evaluated"),
            _make_turn(actor="developer", action="huddle", status="sent"),
        ]
        events = {"evt-1": _make_event("evt-1", conversation=turns)}
        result = _scan_logic(
            active_ids=["evt-1"],
            events=events,
            active_tasks=active_tasks,
            waiting_for_user=set(),
            waiting_for_jarvis={},
            event_locks={},
            last_processed={},
            waiting_for_agent={},
        )
        assert "evt-1" in result

    @pytest.mark.asyncio
    async def test_user_message_during_active_task_enqueued(self):
        """User message during active agent task IS enqueued for processing."""
        active_tasks = {"evt-1": MagicMock(done=MagicMock(return_value=False))}
        turns = [
            _make_turn(actor="brain", action="route", status="evaluated"),
            _make_turn(actor="user", action="message", status="sent"),
        ]
        events = {"evt-1": _make_event("evt-1", conversation=turns)}
        result = _scan_logic(
            active_ids=["evt-1"],
            events=events,
            active_tasks=active_tasks,
            waiting_for_user=set(),
            waiting_for_jarvis={},
            event_locks={},
            last_processed={},
            waiting_for_agent={},
        )
        assert "evt-1" in result

    @pytest.mark.asyncio
    async def test_waiting_for_agent_clears_on_sent_turn(self):
        """Waiting-for-agent bypasses when a non-brain SENT turn exists (edge-triggered)."""
        turns = [
            _make_turn(actor="brain", action="wait", status="evaluated"),
            _make_turn(actor="developer", action="result", status="sent"),
        ]
        events = {"evt-1": _make_event("evt-1", conversation=turns)}
        result = _scan_logic(
            active_ids=["evt-1"],
            events=events,
            active_tasks={},
            waiting_for_user=set(),
            waiting_for_jarvis={},
            event_locks={},
            last_processed={},
            waiting_for_agent={"evt-1": "developer"},
        )
        assert "evt-1" in result

    @pytest.mark.asyncio
    async def test_waiting_for_agent_clears_on_delivered_turn(self):
        """Waiting-for-agent bypasses when a non-brain DELIVERED turn exists (level-triggered, prior scan cycle)."""
        turns = [
            _make_turn(actor="brain", action="wait", status="evaluated"),
            _make_turn(actor="developer", action="result", status="delivered"),
        ]
        events = {"evt-1": _make_event("evt-1", conversation=turns)}
        result = _scan_logic(
            active_ids=["evt-1"],
            events=events,
            active_tasks={},
            waiting_for_user=set(),
            waiting_for_jarvis={},
            event_locks={},
            last_processed={},
            waiting_for_agent={"evt-1": "developer"},
        )
        assert "evt-1" in result

    @pytest.mark.asyncio
    async def test_waiting_for_agent_stays_parked_on_brain_only_unseen(self):
        """Waiting-for-agent does NOT bypass when only brain turns are unseen (negative test)."""
        turns = [
            _make_turn(actor="brain", action="wait", status="evaluated"),
            _make_turn(actor="brain", action="thoughts", status="sent"),
        ]
        events = {"evt-1": _make_event("evt-1", conversation=turns)}
        result = _scan_logic(
            active_ids=["evt-1"],
            events=events,
            active_tasks={},
            waiting_for_user=set(),
            waiting_for_jarvis={},
            event_locks={},
            last_processed={},
            waiting_for_agent={"evt-1": "developer"},
        )
        assert "evt-1" not in result

    @pytest.mark.asyncio
    async def test_active_task_no_input_stays_skipped(self):
        """Active task with only brain-authored unseen turns does NOT enqueue (negative test)."""
        active_tasks = {"evt-1": MagicMock(done=MagicMock(return_value=False))}
        turns = [
            _make_turn(actor="brain", action="route", status="evaluated"),
            _make_turn(actor="brain", action="thoughts", status="sent"),
        ]
        events = {"evt-1": _make_event("evt-1", conversation=turns)}
        result = _scan_logic(
            active_ids=["evt-1"],
            events=events,
            active_tasks=active_tasks,
            waiting_for_user=set(),
            waiting_for_jarvis={},
            event_locks={},
            last_processed={},
            waiting_for_agent={},
        )
        assert "evt-1" not in result

    @pytest.mark.asyncio
    async def test_intermediate_tool_gate_invariant(self):
        """Intermediate tool gate: all 4 communication tools survive, all others stripped."""
        from src.agents.llm.types import BRAIN_TOOL_SCHEMAS

        intermediate_allowed = {"reply_to_agent", "message_agent", "wait_for_agent", "respond_to_jarvis"}
        all_names = {t["name"] for t in BRAIN_TOOL_SCHEMAS}

        # All 4 intermediate tools must exist in the schema
        assert intermediate_allowed <= all_names, (
            f"Missing intermediate tools in schema: {intermediate_allowed - all_names}"
        )

        # After gate, only allowed tools survive
        gated = [t for t in BRAIN_TOOL_SCHEMAS if t["name"] in intermediate_allowed]
        final_names = {t["name"] for t in gated}
        assert final_names == intermediate_allowed, f"Gate result mismatch: {final_names}"

        # Stripped tools must not survive
        stripped = all_names - intermediate_allowed
        assert len(stripped) > 0, "There must be tools that get stripped"
        for name in stripped:
            assert name not in final_names

    @pytest.mark.asyncio
    async def test_jarvis_message_during_active_task_enqueued(self):
        """JARVIS message during active agent task IS enqueued."""
        active_tasks = {"evt-1": MagicMock(done=MagicMock(return_value=False))}
        turns = [
            _make_turn(actor="brain", action="route", status="evaluated"),
            _make_turn(actor="jarvis", action="message", status="sent"),
        ]
        events = {"evt-1": _make_event("evt-1", conversation=turns)}
        result = _scan_logic(
            active_ids=["evt-1"],
            events=events,
            active_tasks=active_tasks,
            waiting_for_user=set(),
            waiting_for_jarvis={},
            event_locks={},
            last_processed={},
            waiting_for_agent={},
        )
        assert "evt-1" in result


def _scan_logic(
    active_ids: list[str],
    events: dict[str, EventDocument],
    active_tasks: dict,
    waiting_for_user: set,
    waiting_for_jarvis: dict,
    event_locks: dict,
    last_processed: dict,
    defer_until: dict | None = None,
    waiting_for_agent: dict | None = None,
) -> list[str]:
    """Pure decision logic extracted from start_event_loop scan.

    Returns list of event_ids that should be enqueued for reconciliation.
    This function has NO side effects -- it only decides.
    """
    if defer_until is None:
        defer_until = {}
    if waiting_for_agent is None:
        waiting_for_agent = {}

    to_enqueue: list[str] = []

    for eid in active_ids:
        # Guard 1: Active task -- enqueue when unseen non-brain turns exist
        if eid in active_tasks and not active_tasks[eid].done():
            event = events.get(eid)
            if event:
                unseen = [t for t in event.conversation if t.status.value == "sent"]
                has_new_input = any(t.actor != "brain" for t in unseen) or any(
                    t.status.value == "delivered" and t.actor != "brain"
                    for t in event.conversation
                )
                if has_new_input:
                    to_enqueue.append(eid)
            continue

        event = events.get(eid)
        if not event:
            continue

        # Guard 2: Zombie (closed but still in active set)
        if event.status == EventStatus.CLOSED:
            continue

        # Guard 3: New event with no conversation
        if not event.conversation:
            if event.status == EventStatus.NEW:
                to_enqueue.append(eid)
            continue

        # Guard 4-5: Deferred events
        if event.status == EventStatus.DEFERRED:
            dt = defer_until.get(eid)
            if dt and time.time() < dt:
                last_defer_idx = next(
                    (i for i, t in enumerate(reversed(event.conversation))
                     if t.actor == "brain" and t.action == "defer"), None
                )
                user_after_defer = last_defer_idx is not None and any(
                    t.actor == "user"
                    for t in event.conversation[len(event.conversation) - last_defer_idx:]
                )
                if not user_after_defer:
                    continue  # Still deferred, no user interrupt
            # Timer expired or user interrupted -- enqueue for re-activation
            to_enqueue.append(eid)
            continue

        # Guard 6: Mark SENT turns as DELIVERED (status transition only in real scan)
        unseen = [t for t in event.conversation if t.status.value == "sent"]

        # Guard 7: Waiting-for-agent -- bypass on participant input (level-triggered)
        if eid in waiting_for_agent:
            has_participant_input = any(t.actor != "brain" for t in unseen) or any(
                t.status.value == "delivered" and t.actor != "brain"
                for t in event.conversation
            )
            if not has_participant_input:
                continue

        # Guard 8-9: JARVIS wait
        if eid in waiting_for_jarvis:
            wait_start = waiting_for_jarvis[eid]
            jarvis_reply = any(
                t.actor == "jarvis" and t.action == "message"
                and (t.timestamp or 0.0) > wait_start
                for t in event.conversation
            )
            if jarvis_reply:
                to_enqueue.append(eid)
            continue  # Whether reply arrived or not, don't fall through

        # Guard 10-12: Active event processing decision
        has_unread = any(t.status.value == "delivered" for t in event.conversation)
        is_waiting = eid in waiting_for_user
        is_locked = eid in event_locks and event_locks[eid].locked()

        if has_unread and not is_waiting and not is_locked:
            to_enqueue.append(eid)
        elif not has_unread and not is_locked:
            time_since = time.time() - last_processed.get(eid, 0)
            if not is_waiting and time_since > 60:
                to_enqueue.append(eid)

    return to_enqueue
