# tests/test_brain_admission.py
# @ai-rules:
# 1. [Constraint]: Brain unit tests with mocked Blackboard and real EventDocument/ConversationTurn models; no live Redis or LLM calls.
#    Two concerns: (a) VMER-2216 T-3 admission dedup via Brain._process_event_inner; (b) VMER-2246 LLM priority derivation.
# 2. [Constraint]: Priority tests MUST call the production derive_llm_priority (src/agents/llm/types.py). NEVER re-implement
#    the heuristic inline in a test -- a copy drifts from production and tests nothing (this happened once in PR #308).
# 3. [Pattern]: Priority boundary cases: last-3-turn window edge (-3 in, -4 out), approved_by sticky, user.message/approve/reject,
#    dict-or-object turns. Update these together with the helper.
# 4. [Purpose]: Pin T-3 of VMER-2216: Turn 0 admission dedup for events matching parked waiting_approval siblings.
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
