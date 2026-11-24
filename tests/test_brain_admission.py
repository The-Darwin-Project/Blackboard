# tests/test_brain_admission.py
# @ai-rules:
# 1. [Constraint]: Brain unit tests with mocked Blackboard and real EventDocument/ConversationTurn models; no live Redis or LLM calls.
#    Three concerns: (a) VMER-2216 T-3 admission dedup via Brain._process_event_inner; (b) VMER-2246 LLM priority derivation;
#    (c) VMER-2483 Turn 0 Pass 1 Jira mission admission dedup.
# 2. [Constraint]: Priority tests MUST call the production derive_llm_priority (src/agents/llm/types.py). NEVER re-implement
#    the heuristic inline in a test -- a copy drifts from production and tests nothing (this happened once in PR #308).
# 3. [Pattern]: Priority boundary cases: last-3-turn window edge (-3 in, -4 out), approved_by sticky, user.message/approve/reject,
#    dict-or-object turns. Update these together with the helper.
# 4. [Purpose]: Pin VMER-2216 T-3 (Turn 0 admission dedup for parked waiting_approval siblings) and VMER-2483
#    (Turn 0 Pass 1 Jira mission admission dedup across concurrent/duplicate/mixed-type events).
from __future__ import annotations

import time
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.agents.brain import Brain
from src.agents.llm.types import PRIORITY_HIGH, PRIORITY_NORMAL, derive_llm_priority
from src.models import (
    ConversationTurn,
    EventDocument,
    EventEvidence,
    EventInput,
    EventStatus,
)


_UNSET: object = object()


def _make_event_doc(
    event_id: str,
    service: str = "release-app",
    source: str = "headhunter",
    status: EventStatus = EventStatus.NEW,
    conversation: list[ConversationTurn] | None = None,
    mr_iid: int | None | object = _UNSET,
    project_id: int | None | object = _UNSET,
    mr_url: str | None | object = _UNSET,
    subject_type: str = "service",
    jira_context: dict | None = None,
) -> EventDocument:
    is_jira = subject_type == "jira" or jira_context is not None
    if mr_iid is _UNSET:
        mr_iid = None if is_jira else 231
    if project_id is _UNSET:
        project_id = None if is_jira else 42
    if mr_url is _UNSET:
        mr_url = None if is_jira else "https://gitlab.cee.redhat.com/rel-eng/release-app/-/merge_requests/231"

    gitlab_ctx = {}
    if mr_iid is not None:
        gitlab_ctx["mr_iid"] = mr_iid
    if project_id is not None:
        gitlab_ctx["project_id"] = project_id
    if mr_url is not None:
        gitlab_ctx["mr_url"] = mr_url

    display_text = (
        f"Jira mission: {jira_context.get('issue_key', 'unknown')}"
        if jira_context is not None
        else f"Test event for MR !{mr_iid}"
    )
    reason = (
        f"Jira mission {jira_context.get('issue_key', 'unknown')} queued"
        if jira_context is not None
        else f"MR !{mr_iid} needs attention"
    )
    evidence = EventEvidence(
        display_text=display_text,
        source_type=source,
        domain="complicated",
        severity="info",
        gitlab_context=gitlab_ctx if gitlab_ctx else None,
        jira_context=jira_context,
    )
    event_input = EventInput(
        reason=reason,
        evidence=evidence,
        timeDate="2026-11-04T12:00:00Z",
    )
    doc = EventDocument(
        id=event_id,
        service=service,
        subject_type=subject_type,
        source=source,
        event=event_input,
        status=status,
        conversation=conversation or [],
        queued_at=time.time() - 30,
        processing_started_at=time.time() - 20,
    )
    return doc


def _build_admission_driver(
    existing_event: EventDocument,
    incoming_event: EventDocument,
    *,
    existing_in_waiting: bool = False,
) -> tuple[Brain, MagicMock]:
    """Protocol driver wiring a mocked Blackboard + Brain for Turn 0 admission tests."""
    mock_blackboard = MagicMock()
    if existing_in_waiting:
        mock_blackboard.get_active_events = AsyncMock(return_value=[])
        mock_blackboard.get_waiting_approval_events = AsyncMock(return_value=[existing_event.id])
    else:
        mock_blackboard.get_active_events = AsyncMock(return_value=[existing_event.id])
        mock_blackboard.get_waiting_approval_events = AsyncMock(return_value=[])

    mock_blackboard.get_active_events_with_status = AsyncMock(return_value={})
    mock_blackboard.record_event = AsyncMock()
    mock_blackboard.transition_event_status = AsyncMock(return_value=True)
    mock_blackboard.stamp_event = AsyncMock()
    mock_blackboard.mark_turns_evaluated = AsyncMock()
    mock_blackboard.mark_turns_status = AsyncMock()
    mock_blackboard.append_turn = AsyncMock(return_value=1)
    mock_blackboard.close_event = AsyncMock()
    mock_blackboard.update_event_phase = AsyncMock()

    async def _mock_get_event(eid: str):
        if eid == existing_event.id:
            return existing_event
        if eid == incoming_event.id:
            return incoming_event
        return None

    mock_blackboard.get_event = AsyncMock(side_effect=_mock_get_event)

    brain = Brain(blackboard=mock_blackboard, agents={})
    brain._close_and_broadcast = AsyncMock()
    brain._process_with_llm = AsyncMock(return_value=False)
    brain._get_adapter = AsyncMock(return_value=None)
    return brain, mock_blackboard


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

    brain, mock_blackboard = _build_admission_driver(
        existing_event, incoming_event, existing_in_waiting=True
    )

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
    """Guards against Brain re-introducing an inline priority heuristic instead of derive_llm_priority."""

    def test_brain_uses_production_helper(self):
        """Brain re-uses the same helper object (guards against a re-introduced inline heuristic)."""
        import src.agents.brain as brain_module
        from src.agents.llm.types import derive_llm_priority

        assert brain_module.derive_llm_priority is derive_llm_priority

    def test_brain_derives_priority_for_event_documents(self):
        """Smoketest derive_llm_priority against EventDocument models (full matrix in test_gemini_client_quota.py)."""
        chat_event = _make_event_doc("evt-prio-chat", source="chat")
        assert derive_llm_priority(chat_event) == PRIORITY_HIGH

        hh_event = _make_event_doc("evt-prio-hh", source="headhunter")
        assert derive_llm_priority(hh_event) == PRIORITY_NORMAL


class TestJiraMissionAdmissionDedup:
    """VMER-2483: Turn 0 Pass 1 admission deduplication for concurrent Jira missions."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "existing_status,existing_in_waiting",
        [
            (EventStatus.ACTIVE, False),
            (EventStatus.WAITING_APPROVAL, True),
        ],
    )
    async def test_concurrent_jira_missions_same_project_are_both_admitted(
        self, existing_status: EventStatus, existing_in_waiting: bool
    ):
        """Given VMER-2463 active/waiting_approval and VMER-2464 incoming for service='vmer',
        Brain must NOT close VMER-2464 as duplicate and must admit it (NEW -> ACTIVE)."""
        existing_event = _make_event_doc(
            event_id="evt-existing",
            service="vmer",
            source="headhunter",
            status=existing_status,
            subject_type="jira",
            jira_context={"issue_key": "VMER-2463"},
            conversation=[
                ConversationTurn(turn=1, actor="brain", action="triage", status="evaluated"),
            ],
        )
        incoming_event = _make_event_doc(
            event_id="evt-incoming",
            service="vmer",
            source="headhunter",
            status=EventStatus.NEW,
            subject_type="jira",
            jira_context={"issue_key": "VMER-2464"},
            conversation=[],
        )
        brain, mock_blackboard = _build_admission_driver(
            existing_event, incoming_event, existing_in_waiting=existing_in_waiting
        )

        await brain._process_event_inner(incoming_event.id, prefetched_event=incoming_event)

        brain._close_and_broadcast.assert_not_called()
        mock_blackboard.transition_event_status.assert_awaited_once()

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "existing_status,existing_in_waiting",
        [
            (EventStatus.ACTIVE, False),
            (EventStatus.WAITING_APPROVAL, True),
        ],
    )
    async def test_duplicate_jira_mission_is_closed_with_exact_message_and_enriched_log(
        self, existing_status: EventStatus, existing_in_waiting: bool, caplog
    ):
        """Given VMER-2464 already active/waiting_approval and a second VMER-2464 incoming,
        Brain closes it as duplicate preserving the exact close message and logging 'Jira VMER-2464'."""
        existing_event = _make_event_doc(
            event_id="evt-existing",
            service="vmer",
            source="headhunter",
            status=existing_status,
            subject_type="jira",
            jira_context={"issue_key": "VMER-2464"},
            conversation=[
                ConversationTurn(turn=1, actor="brain", action="triage", status="evaluated"),
            ],
        )
        incoming_event = _make_event_doc(
            event_id="evt-incoming",
            service="vmer",
            source="headhunter",
            status=EventStatus.NEW,
            subject_type="jira",
            jira_context={"issue_key": "VMER-2464"},
            conversation=[],
        )
        brain, _ = _build_admission_driver(
            existing_event, incoming_event, existing_in_waiting=existing_in_waiting
        )

        with caplog.at_level("INFO", logger="src.agents.brain"):
            await brain._process_event_inner(incoming_event.id, prefetched_event=incoming_event)

        brain._close_and_broadcast.assert_awaited_once_with(
            "evt-incoming",
            "Duplicate: merged with existing event evt-existing for vmer.",
            close_reason="duplicate",
        )
        assert any("Jira VMER-2464" in r.message for r in caplog.records)
        brain._process_with_llm.assert_not_called()

    @pytest.mark.asyncio
    async def test_jira_mission_admitted_alongside_non_jira_event_same_service(self):
        """Given a non-Jira active event for service='vmer' and an incoming Jira mission VMER-2464,
        Brain must NOT dedup the Jira mission against the non-Jira event."""
        existing_event = _make_event_doc(
            event_id="evt-existing-svc",
            service="vmer",
            source="aligner",
            status=EventStatus.ACTIVE,
            subject_type="service",
            jira_context=None,
            mr_iid=None,
            project_id=None,
            mr_url=None,
            conversation=[
                ConversationTurn(turn=1, actor="brain", action="triage", status="evaluated"),
            ],
        )
        incoming_event = _make_event_doc(
            event_id="evt-incoming-jira",
            service="vmer",
            source="headhunter",
            status=EventStatus.NEW,
            subject_type="jira",
            jira_context={"issue_key": "VMER-2464"},
            conversation=[],
        )
        brain, mock_blackboard = _build_admission_driver(
            existing_event, incoming_event, existing_in_waiting=False
        )

        await brain._process_event_inner(incoming_event.id, prefetched_event=incoming_event)

        brain._close_and_broadcast.assert_not_called()
        mock_blackboard.transition_event_status.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_non_jira_event_admitted_alongside_active_jira_mission_same_service(self):
        """Reverse mixed-type: given an active Jira mission VMER-2464 for service='vmer'
        and an incoming non-Jira event for service='vmer', Brain must admit the incoming event."""
        existing_event = _make_event_doc(
            event_id="evt-existing-jira",
            service="vmer",
            source="headhunter",
            status=EventStatus.ACTIVE,
            subject_type="jira",
            jira_context={"issue_key": "VMER-2464"},
            conversation=[
                ConversationTurn(turn=1, actor="brain", action="triage", status="evaluated"),
            ],
        )
        incoming_event = _make_event_doc(
            event_id="evt-incoming-svc",
            service="vmer",
            source="aligner",
            status=EventStatus.NEW,
            subject_type="service",
            jira_context=None,
            mr_iid=None,
            project_id=None,
            mr_url=None,
            conversation=[],
        )
        brain, mock_blackboard = _build_admission_driver(
            existing_event, incoming_event, existing_in_waiting=False
        )

        await brain._process_event_inner(incoming_event.id, prefetched_event=incoming_event)

        brain._close_and_broadcast.assert_not_called()
        mock_blackboard.transition_event_status.assert_awaited_once()
