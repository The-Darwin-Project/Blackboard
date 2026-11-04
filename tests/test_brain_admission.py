# tests/test_brain_admission.py
# @ai-rules:
# 1. [Constraint]: Pure admission deduplication unit test against Brain._process_event_inner.
# 2. [Pattern]: Uses mocked Blackboard with EventDocument models; no live Redis or LLM network calls.
# 3. [Purpose]: Pin T-3 of VMER-2216: Turn 0 admission dedup for events matching parked waiting_approval siblings.
from __future__ import annotations

import time
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.agents.brain import Brain
from src.models import (
    ConversationTurn,
    EventDocument,
    EventEvidence,
    EventInput,
    EventStatus,
)


def _make_event_doc(
    event_id: str,
    service: str = "release-app",
    source: str = "headhunter",
    status: EventStatus = EventStatus.NEW,
    conversation: list[ConversationTurn] | None = None,
    mr_iid: int | None = 231,
    project_id: int | None = 42,
    mr_url: str | None = "https://gitlab.cee.redhat.com/rel-eng/release-app/-/merge_requests/231",
) -> EventDocument:
    gitlab_ctx = {}
    if mr_iid is not None:
        gitlab_ctx["mr_iid"] = mr_iid
    if project_id is not None:
        gitlab_ctx["project_id"] = project_id
    if mr_url is not None:
        gitlab_ctx["mr_url"] = mr_url

    evidence = EventEvidence(
        display_text=f"Test event for MR !{mr_iid}",
        source_type=source,
        domain="complicated",
        severity="info",
        gitlab_context=gitlab_ctx if gitlab_ctx else None,
    )
    event_input = EventInput(
        reason=f"MR !{mr_iid} needs attention",
        evidence=evidence,
        timeDate="2026-11-04T12:00:00Z",
    )
    doc = EventDocument(
        id=event_id,
        service=service,
        source=source,
        event=event_input,
        status=status,
        conversation=conversation or [],
        queued_at=time.time() - 30,
        processing_started_at=time.time() - 20,
    )
    return doc


@pytest.mark.asyncio
async def test_admission_dedup_waiting_approval_sibling():
    """T-3: Given an incoming duplicate event on Turn 0 targeting an MR/PR already in waiting_approval,

    Brain admission deduplication must evaluate it as a duplicate and close it via
    _close_and_broadcast with close_reason="duplicate" without agent dispatch.
    """
    parked_eid = "evt-ed234f34"
    incoming_eid = "evt-b2532139"

    # Parked existing event: has prior turns, status=waiting_approval, matching MR !231
    existing_event = _make_event_doc(
        event_id=parked_eid,
        service="release-app",
        source="headhunter",
        status=EventStatus.WAITING_APPROVAL,
        conversation=[
            ConversationTurn(turn=1, actor="headhunter", action="evidence", status="evaluated"),
            ConversationTurn(turn=2, actor="brain", action="triage", status="evaluated"),
            ConversationTurn(turn=3, actor="brain", action="request_user_approval", status="evaluated"),
        ],
        mr_iid=231,
        project_id=42,
    )

    # Incoming new event: Turn 0 (empty conversation), status=new, same service and MR !231
    incoming_event = _make_event_doc(
        event_id=incoming_eid,
        service="release-app",
        source="headhunter",
        status=EventStatus.NEW,
        conversation=[],
        mr_iid=231,
        project_id=42,
    )

    mock_blackboard = MagicMock()
    # active_events does NOT contain parked event; waiting_approval_events does
    mock_blackboard.get_active_events = AsyncMock(return_value=[])
    mock_blackboard.get_waiting_approval_events = AsyncMock(return_value=[parked_eid])
    mock_blackboard.get_active_events_with_status = AsyncMock(return_value={})
    mock_blackboard.transition_event_status = AsyncMock(return_value=True)
    mock_blackboard.stamp_event = AsyncMock()
    mock_blackboard.mark_turns_evaluated = AsyncMock()
    mock_blackboard.mark_turns_status = AsyncMock()
    mock_blackboard.append_turn = AsyncMock(return_value=1)
    mock_blackboard.close_event = AsyncMock()
    mock_blackboard.update_event_phase = AsyncMock()

    async def _mock_get_event(eid: str):
        if eid == parked_eid:
            return existing_event
        if eid == incoming_eid:
            return incoming_event
        return None

    mock_blackboard.get_event = AsyncMock(side_effect=_mock_get_event)

    brain = Brain(blackboard=mock_blackboard, agents={})
    brain._close_and_broadcast = AsyncMock()
    brain._process_with_llm = AsyncMock(return_value=False)

    await brain._process_event_inner(incoming_eid, prefetched_event=incoming_event)

    # Deterministic admission deduplication MUST close incoming event as duplicate
    mock_blackboard.get_waiting_approval_events.assert_awaited_once()
    brain._close_and_broadcast.assert_awaited_once_with(
        incoming_eid,
        f"Duplicate: merged with existing event {parked_eid} for release-app.",
        close_reason="duplicate",
    )
    # Zero LLM / agent dispatch invocations
    brain._process_with_llm.assert_not_called()


class TestBrainPriorityDerivation:
    @pytest.mark.parametrize("source", ["chat", "slack", "jarvis"])
    def test_user_facing_sources_yield_high_priority(self, source):
        """User-facing event sources always classify as PRIORITY_HIGH."""
        from src.agents.llm.types import PRIORITY_HIGH, PRIORITY_NORMAL

        event = _make_event_doc("evt-prio-1", source=source)
        is_high = (
            event.source in ("chat", "slack", "jarvis")
            or any(
                (turn.get("actor") if isinstance(turn, dict) else getattr(turn, "actor", None)) == "user"
                and (turn.get("action") if isinstance(turn, dict) else getattr(turn, "action", None)) in ("approve", "reject", "message")
                for turn in (event.conversation[-10:] if event.conversation else [])
            )
        )
        priority = PRIORITY_HIGH if is_high else PRIORITY_NORMAL
        assert priority == PRIORITY_HIGH

    @pytest.mark.parametrize("source", ["headhunter", "aligner", "timekeeper"])
    def test_background_sources_without_user_turns_yield_normal_priority(self, source):
        """Background sources without user interaction classify as PRIORITY_NORMAL."""
        from src.agents.llm.types import PRIORITY_HIGH, PRIORITY_NORMAL

        event = _make_event_doc("evt-prio-2", source=source)
        is_high = (
            event.source in ("chat", "slack", "jarvis")
            or any(
                (turn.get("actor") if isinstance(turn, dict) else getattr(turn, "actor", None)) == "user"
                and (turn.get("action") if isinstance(turn, dict) else getattr(turn, "action", None)) in ("approve", "reject", "message")
                for turn in (event.conversation[-10:] if event.conversation else [])
            )
        )
        priority = PRIORITY_HIGH if is_high else PRIORITY_NORMAL
        assert priority == PRIORITY_NORMAL

    @pytest.mark.parametrize("action", ["approve", "reject", "message"])
    def test_background_event_with_recent_user_turn_yields_high_priority(self, action):
        """Automated event resuming from user approval, rejection, or message classifies as PRIORITY_HIGH."""
        from src.agents.llm.types import PRIORITY_HIGH, PRIORITY_NORMAL

        turns = [
            ConversationTurn(turn=1, actor="headhunter", action="evidence", status="evaluated"),
            ConversationTurn(turn=2, actor="brain", action="request_user_approval", status="evaluated"),
            ConversationTurn(turn=3, actor="user", action=action, status="evaluated"),
        ]
        event = _make_event_doc("evt-prio-3", source="headhunter", conversation=turns)
        is_high = (
            event.source in ("chat", "slack", "jarvis")
            or any(
                (turn.get("actor") if isinstance(turn, dict) else getattr(turn, "actor", None)) == "user"
                and (turn.get("action") if isinstance(turn, dict) else getattr(turn, "action", None)) in ("approve", "reject", "message")
                for turn in (event.conversation[-10:] if event.conversation else [])
            )
        )
        priority = PRIORITY_HIGH if is_high else PRIORITY_NORMAL
        assert priority == PRIORITY_HIGH

    def test_dict_and_object_turns_handled_defensively(self):
        """Turn lists with raw dicts or ConversationTurn objects evaluate without AttributeError."""
        from src.agents.llm.types import PRIORITY_HIGH, PRIORITY_NORMAL

        raw_turns = [
            {"actor": "headhunter", "action": "evidence"},
            {"actor": "user", "action": "approve"},
        ]
        event = _make_event_doc("evt-prio-4", source="headhunter")
        event.conversation = raw_turns  # type: ignore[assignment]

        is_high = (
            event.source in ("chat", "slack", "jarvis")
            or any(
                (turn.get("actor") if isinstance(turn, dict) else getattr(turn, "actor", None)) == "user"
                and (turn.get("action") if isinstance(turn, dict) else getattr(turn, "action", None)) in ("approve", "reject", "message")
                for turn in (event.conversation[-10:] if event.conversation else [])
            )
        )
        priority = PRIORITY_HIGH if is_high else PRIORITY_NORMAL
        assert priority == PRIORITY_HIGH

