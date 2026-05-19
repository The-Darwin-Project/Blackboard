# BlackBoard/tests/test_brain_close_paths.py
# @ai-rules:
# 1. [Constraint]: No Redis — Brain._cleanup_stale_events with a MagicMock blackboard only.
# 2. [Pattern]: Asserts headhunter stale startup path calls process_event_feedback directly (no signal).
"""Brain startup close-path tests (stale headhunter + direct feedback)."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.agents.brain import Brain
from src.models import ConversationTurn, EventDocument, EventEvidence, EventInput


@pytest.mark.asyncio
async def test_cleanup_stale_headhunter_calls_direct_feedback():
    evidence = EventEvidence(
        display_text="GitLab MR",
        source_type="headhunter",
        severity="info",
        gitlab_context={"todo_id": 1, "project_id": 10, "mr_iid": 2},
    )
    event = EventDocument(
        id="evt-stale-hh",
        source="headhunter",
        service="group/repo",
        event=EventInput(reason="review", evidence=evidence),
        conversation=[
            ConversationTurn(turn=0, actor="headhunter", action="investigate", result="x"),
        ],
    )

    bb = MagicMock()
    bb.EVENT_ACTIVE = "darwin:event:active"
    bb.EVENT_QUEUE = "darwin:queue"
    bb.redis = MagicMock()
    bb.redis.srem = AsyncMock()
    bb.redis.lpush = AsyncMock()
    bb.get_active_events = AsyncMock(return_value=["evt-stale-hh"])
    bb.mark_turns_evaluated = AsyncMock()
    bb.get_event = AsyncMock(return_value=event)
    bb.close_event = AsyncMock()
    bb.persist_report = AsyncMock()
    bb.append_journal = AsyncMock()

    mock_hh = MagicMock()
    mock_hh.process_event_feedback = AsyncMock()

    brain = Brain(blackboard=bb, agents={"_headhunter": mock_hh})
    brain._broadcast = AsyncMock()

    await brain._cleanup_stale_events()

    mock_hh.process_event_feedback.assert_awaited_once_with("evt-stale-hh")
    bb.close_event.assert_awaited_once()
    brain._broadcast.assert_awaited()
