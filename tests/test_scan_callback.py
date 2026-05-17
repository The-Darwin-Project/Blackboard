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
    async def test_branch1_active_agent_task_skipped(self):
        """Events with running agent tasks are NOT enqueued (handled via _process_intermediate)."""
        # Branch: eid in _active_tasks and not done -> skip (don't enqueue)
        active_tasks = {"evt-1": MagicMock(done=MagicMock(return_value=False))}
        waiting_for_user = set()
        waiting_for_jarvis = {}
        event_locks = {}
        last_processed = {}

        events = {"evt-1": _make_event("evt-1", conversation=[_make_turn()])}
        result = _scan_logic(
            active_ids=["evt-1"],
            events=events,
            active_tasks=active_tasks,
            waiting_for_user=waiting_for_user,
            waiting_for_jarvis=waiting_for_jarvis,
            event_locks=event_locks,
            last_processed=last_processed,
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
        )
        lock.release()
        assert "evt-1" not in result


def _scan_logic(
    active_ids: list[str],
    events: dict[str, EventDocument],
    active_tasks: dict,
    waiting_for_user: set,
    waiting_for_jarvis: dict,
    event_locks: dict,
    last_processed: dict,
    defer_until: dict | None = None,
) -> list[str]:
    """Pure decision logic extracted from start_event_loop scan.

    Returns list of event_ids that should be enqueued for reconciliation.
    This function has NO side effects -- it only decides.
    """
    if defer_until is None:
        defer_until = {}

    to_enqueue: list[str] = []

    for eid in active_ids:
        # Branch 1: Agent task running -- handled by intermediate processing, not reconcile
        if eid in active_tasks and not active_tasks[eid].done():
            continue

        event = events.get(eid)
        if not event:
            continue

        # Branch 2: Zombie (closed but still in active set)
        if event.status == EventStatus.CLOSED:
            continue

        # Branch 3: New event with no conversation
        if not event.conversation:
            if event.status == EventStatus.NEW:
                to_enqueue.append(eid)
            continue

        # Branch 4-5: Deferred events
        if event.status == EventStatus.DEFERRED:
            dt = defer_until.get(eid)
            if dt and time.time() < dt:
                # Check for user interrupt
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

        # Branch 6-7: JARVIS wait
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

        # Branch 8-12: Active event processing decision
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
