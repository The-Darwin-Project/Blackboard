# BlackBoard/tests/test_silent_event_audit.py
# @ai-rules:
# 1. [Pattern]: Tests for JARVIS silent-event audit (_check_silent_events).
#    Mirrors _make_adapter() mock pattern from test_handoff.py.
# 2. [Constraint]: All Redis + broadcast + session interactions are mocked.
#    No live connections. Each test controls _brain.last_processed_time and
#    _brain.is_task_running via MagicMock side_effect.
# 3. [Gotcha]: _check_silent_events uses time.time() for staleness comparison.
#    Tests freeze time via monkeypatch or patch to control the 15-minute window.
# 4. [Gotcha]: send_client_content is on _session (AsyncMock), not _blackboard.
"""Unit tests for JARVIS silent-event audit in LiveAPIAdapter."""
from __future__ import annotations

import time
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.models import (
    ConversationTurn,
    EventDocument,
    EventEvidence,
    EventInput,
    EventStatus,
)


def _make_adapter(*, with_brain: bool = True, with_session: bool = True):
    """Build a LiveAPIAdapter with all dependencies mocked."""
    from src.adapters.live_api_adapter import LiveAPIAdapter

    blackboard = MagicMock()
    blackboard.redis = AsyncMock()
    archivist = AsyncMock()
    pulse_tracker = MagicMock()
    broadcast = AsyncMock()

    brain = MagicMock() if with_brain else None

    adapter = LiveAPIAdapter(
        blackboard=blackboard,
        archivist=archivist,
        pulse_tracker=pulse_tracker,
        broadcast=broadcast,
        brain=brain,
    )
    if with_session:
        adapter._session = MagicMock()
        adapter._session.send_client_content = AsyncMock()
    return adapter


def _make_event(
    event_id: str = "evt-test1",
    *,
    status: EventStatus = EventStatus.ACTIVE,
    domain: str = "complicated",
    source: str = "headhunter",
    brain_phase: str = "dispatch",
) -> EventDocument:
    evidence = EventEvidence(
        display_text="test evidence",
        source_type=source,
        domain=domain,
        severity="info",
    )
    return EventDocument(
        id=event_id,
        source=source,
        status=status,
        brain_phase=brain_phase,
        service="test-svc",
        event=EventInput(reason="test", evidence=evidence),
        conversation=[
            ConversationTurn(turn=1, actor="brain", action="triage"),
        ],
        queued_at=time.time() - 3600,
    )


# ---------------------------------------------------------------------------
# T-1: Audit fires for stale event
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_audit_fires_for_stale_event():
    """An event silent for >15 minutes with no task running triggers an audit."""
    adapter = _make_adapter()
    now = time.time()

    event = _make_event("evt-stale1")
    adapter._blackboard.get_active_events = AsyncMock(return_value=["evt-stale1"])
    adapter._blackboard.get_event = AsyncMock(return_value=event)
    adapter._brain.last_processed_time = MagicMock(return_value=now - 1000)
    adapter._brain.is_task_running = MagicMock(return_value=False)

    await adapter._check_silent_events()

    adapter._session.send_client_content.assert_awaited_once()
    call_args = adapter._session.send_client_content.call_args
    turns_arg = call_args.kwargs.get("turns") or call_args[1].get("turns") if call_args[1] else call_args[0][0]
    text = str(turns_arg)
    assert "[AUDIT]" in text


# ---------------------------------------------------------------------------
# T-2: Dedup prevents re-audit within threshold
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_dedup_prevents_reaudit_within_threshold():
    """If _last_audit_sent is recent for an event, no second audit fires."""
    adapter = _make_adapter()
    now = time.time()

    event = _make_event("evt-dup1")
    adapter._blackboard.get_active_events = AsyncMock(return_value=["evt-dup1"])
    adapter._blackboard.get_event = AsyncMock(return_value=event)
    adapter._brain.last_processed_time = MagicMock(return_value=now - 1000)
    adapter._brain.is_task_running = MagicMock(return_value=False)

    adapter._last_audit_sent["evt-dup1"] = now - 60  # audited 1 minute ago

    await adapter._check_silent_events()

    adapter._session.send_client_content.assert_not_awaited()


# ---------------------------------------------------------------------------
# T-3: Concurrent: only stale event audited
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_only_stale_event_audited_when_mixed():
    """With 2 events — 1 recently active, 1 stale — only the stale one is audited."""
    adapter = _make_adapter()
    now = time.time()

    active_event = _make_event("evt-active")
    stale_event = _make_event("evt-stale2")

    async def mock_get_event(eid):
        return active_event if eid == "evt-active" else stale_event

    adapter._blackboard.get_active_events = AsyncMock(
        return_value=["evt-active", "evt-stale2"],
    )
    adapter._blackboard.get_event = AsyncMock(side_effect=mock_get_event)

    def mock_last_processed(eid):
        return now - 60 if eid == "evt-active" else now - 1000

    adapter._brain.last_processed_time = MagicMock(side_effect=mock_last_processed)
    adapter._brain.is_task_running = MagicMock(return_value=False)

    await adapter._check_silent_events()

    adapter._session.send_client_content.assert_awaited_once()
    call_args = adapter._session.send_client_content.call_args
    turns_arg = call_args.kwargs.get("turns") or call_args[1].get("turns") if call_args[1] else call_args[0][0]
    text = str(turns_arg)
    assert "evt-stale2" in text
    assert "evt-active" not in text


# ---------------------------------------------------------------------------
# T-4: CASUAL domain exempt
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_casual_domain_exempt_from_audit():
    """Events with domain=casual are never included in silent-event audits."""
    adapter = _make_adapter()
    now = time.time()

    casual_event = _make_event("evt-casual", domain="casual", source="chat")
    adapter._blackboard.get_active_events = AsyncMock(return_value=["evt-casual"])
    adapter._blackboard.get_event = AsyncMock(return_value=casual_event)
    adapter._brain.last_processed_time = MagicMock(return_value=now - 1000)
    adapter._brain.is_task_running = MagicMock(return_value=False)

    await adapter._check_silent_events()

    adapter._session.send_client_content.assert_not_awaited()


# ---------------------------------------------------------------------------
# T-5: Handoff guard suppresses audit
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_handoff_guard_suppresses_audit():
    """When _collecting_handoff is True, the audit does not fire."""
    adapter = _make_adapter()
    now = time.time()

    event = _make_event("evt-ho1")
    adapter._blackboard.get_active_events = AsyncMock(return_value=["evt-ho1"])
    adapter._blackboard.get_event = AsyncMock(return_value=event)
    adapter._brain.last_processed_time = MagicMock(return_value=now - 1000)
    adapter._brain.is_task_running = MagicMock(return_value=False)

    adapter._collecting_handoff = True

    await adapter._check_silent_events()

    adapter._session.send_client_content.assert_not_awaited()


# ---------------------------------------------------------------------------
# T-6: Task running skips audit
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_task_running_skips_audit():
    """Event is stale but is_task_running=True — not audited."""
    adapter = _make_adapter()
    now = time.time()

    event = _make_event("evt-busy1")
    adapter._blackboard.get_active_events = AsyncMock(return_value=["evt-busy1"])
    adapter._blackboard.get_event = AsyncMock(return_value=event)
    adapter._brain.last_processed_time = MagicMock(return_value=now - 1000)
    adapter._brain.is_task_running = MagicMock(return_value=True)

    await adapter._check_silent_events()

    adapter._session.send_client_content.assert_not_awaited()


# ---------------------------------------------------------------------------
# T-7: Deferred events exempt
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_deferred_events_exempt_from_audit():
    """Events with status=deferred are not included in silent-event audits."""
    adapter = _make_adapter()
    now = time.time()

    deferred_event = _make_event("evt-def1", status=EventStatus.DEFERRED)
    adapter._blackboard.get_active_events = AsyncMock(return_value=["evt-def1"])
    adapter._blackboard.get_event = AsyncMock(return_value=deferred_event)
    adapter._brain.last_processed_time = MagicMock(return_value=now - 1000)
    adapter._brain.is_task_running = MagicMock(return_value=False)

    await adapter._check_silent_events()

    adapter._session.send_client_content.assert_not_awaited()


# ---------------------------------------------------------------------------
# T-8: Multiple stale events batched
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_multiple_stale_events_batched():
    """3 stale events produce a single send_client_content call containing all 3."""
    adapter = _make_adapter()
    now = time.time()

    events = {
        f"evt-s{i}": _make_event(f"evt-s{i}") for i in range(1, 4)
    }

    adapter._blackboard.get_active_events = AsyncMock(
        return_value=list(events.keys()),
    )
    adapter._blackboard.get_event = AsyncMock(
        side_effect=lambda eid: events[eid],
    )
    adapter._brain.last_processed_time = MagicMock(return_value=now - 1000)
    adapter._brain.is_task_running = MagicMock(return_value=False)

    await adapter._check_silent_events()

    adapter._session.send_client_content.assert_awaited_once()
    call_args = adapter._session.send_client_content.call_args
    turns_arg = call_args.kwargs.get("turns") or call_args[1].get("turns") if call_args[1] else call_args[0][0]
    text = str(turns_arg)
    for eid in events:
        assert eid in text, f"Expected {eid} in batched audit message"
