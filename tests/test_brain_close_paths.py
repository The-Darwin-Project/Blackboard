# BlackBoard/tests/test_brain_close_paths.py
# @ai-rules:
# 1. [Constraint]: No Redis — Brain._cleanup_stale_events with a MagicMock blackboard only.
# 2. [Pattern]: Asserts headhunter stale startup path calls process_event_feedback directly (no signal).
# 3. [Pattern]: TOCTOU coverage (T-16/T-17) uses Brain._close_and_broadcast directly via a
#    minimal MagicMock blackboard, mirroring test_brain_orphan.py's _make_brain() helper --
#    that pattern is proven safe for exercising the full _close_and_broadcast body.
"""Brain startup close-path tests (stale headhunter + direct feedback) and the
terminal-state close-gate's TOCTOU recheck extension (GitHub #155/#156, plan Step 6).
"""
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


# ---------------------------------------------------------------------------
# TOCTOU sentinel extension (plan: terminal-state-close-gate, Step 6)
#
# NOTE: at authoring time, Brain._close_and_broadcast's recheck condition is
# still `if close_reason == "resolved":` (the pre-Step-6 state) -- the target
# is `if close_reason in _LLM_CLOSE_REASONS:` covering all 4 LLM-driven values.
# T-16 is written against that target and is expected to fail for the 3
# non-"resolved" values until Step 6 lands. T-17 exercises a real, already
# -correct production call path (brain.py's "duplicate" close, ~line 958-961)
# and should pass both before and after Step 6.
# ---------------------------------------------------------------------------

def _make_brain_for_toctou() -> Brain:
    """Minimal Brain + MagicMock blackboard sufficient to exercise the full
    _close_and_broadcast body without crashing on unmocked bb attributes
    (mirrors test_brain_orphan.py's _make_brain(), proven against this exact
    method in that file's test_count_cleared_on_close)."""
    bb = MagicMock()
    bb.get_event = AsyncMock()
    bb.close_event = AsyncMock()
    bb.persist_report = AsyncMock()
    bb.append_journal = AsyncMock()
    bb.record_event = AsyncMock()
    brain = Brain(blackboard=bb, agents={})
    brain._broadcast = AsyncMock()
    return brain


def _event_with_late_message(event_id: str, source: str = "aligner") -> EventDocument:
    """A not-yet-closed event whose latest turn is an unevaluated user.message --
    the exact condition has_unevaluated_close_blocker() is designed to detect."""
    evidence = EventEvidence(display_text="test", source_type=source, severity="info")
    return EventDocument(
        id=event_id,
        source=source,
        service="test-svc",
        event=EventInput(reason="anomaly", evidence=evidence),
        conversation=[
            ConversationTurn(turn=1, actor="brain", action="triage"),
            ConversationTurn(turn=2, actor="user", action="message"),  # status defaults to SENT
        ],
    )


class TestToctouAllFourLlmCloseReasons:
    """T-16: the unevaluated-message recheck must fire identically for all 4
    LLM-driven terminal_reason values, not just "resolved"."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize("close_reason", [
        "resolved", "non_transient_confirmed", "self_resolved", "no_action_needed",
    ])
    async def test_toctou_aborts_for_each_llm_close_reason(self, close_reason):
        brain = _make_brain_for_toctou()
        event = _event_with_late_message("evt-toctou-1")
        brain.blackboard.get_event = AsyncMock(return_value=event)

        await brain._close_and_broadcast(
            "evt-toctou-1", "attempted close", close_reason=close_reason,
        )

        brain.blackboard.close_event.assert_not_awaited()


class TestToctouSystemDrivenBypass:
    """T-17: system-driven close_reason values (e.g. "duplicate", the real
    call path at brain.py ~958-961) bypass the recheck by design -- unaffected
    by the Step 6 frozenset widening."""

    @pytest.mark.asyncio
    async def test_duplicate_close_proceeds_despite_late_message(self):
        brain = _make_brain_for_toctou()
        event = _event_with_late_message("evt-toctou-2")
        brain.blackboard.get_event = AsyncMock(return_value=event)

        await brain._close_and_broadcast(
            "evt-toctou-2", "duplicate close", close_reason="duplicate",
        )

        brain.blackboard.close_event.assert_awaited_once()
