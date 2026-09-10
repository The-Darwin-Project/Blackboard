# tests/test_wait_for_user_idle_timeout.py
# @ai-rules:
# 1. [Constraint]: Pure unit tests -- mock ToolContext/Brain internals, no real Redis or LLM.
# 2. [Pattern]: handlers_state tests follow test_handle_close_event.py's _mock_ctx() shape.
# 3. [Pattern]: Brain._process_with_llm test follows test_brain_fc_terminal_guard.py's
#    _make_brain()/MockStream harness, isolated to the pure text-only-no-FC branch.
# 4. [Pattern]: Brain._cleanup_stale_events test follows test_brain_close_paths.py's
#    MagicMock-blackboard harness (no real Redis).
"""Regression tests: wait_for_user must never get an idle-timeout backstop.

Covers all three places that used to schedule (or re-arm) the idle timeout for a
plain "waiting for user" park (status stays ACTIVE, no StalenessGuard[chat] coverage):

1. handlers_state.handle_wait_for_user -- must never call ctx.get_idle_timeout().schedule().
2. handlers_state.handle_classify_event -- must only re-arm the idle timeout when the
   event is WAITING_APPROVAL (request_user_approval's own backstop), never for a plain
   ACTIVE wait_for_user park.
3. Brain._process_with_llm's terminal text-only (no function call) branch -- must mark
   _waiting_for_user without scheduling an idle timeout.

Plus the positive counterpart of all of the above: a wait_for_user park doesn't just
avoid getting an idle timer -- it must actually stay open and resumable indefinitely.
Brain._cleanup_stale_events (the restart/crash-recovery cleanup, a completely separate
mechanism from the idle timeout) must exempt these parks too, no matter how long they've
been waiting, and a follow-up user turn must still process normally afterward.
"""
from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.agents.handlers_state import handle_classify_event, handle_wait_for_user
from src.agents.llm.types import FunctionCall
from src.models import (
    ConversationTurn,
    EventDocument,
    EventEvidence,
    EventInput,
    EventStatus,
)


# =============================================================================
# Helpers -- handlers_state (mocked ToolContext)
# =============================================================================


def _mock_ctx(event=None, is_waiting: bool = False):
    bb = AsyncMock()
    bb.get_event = AsyncMock(return_value=event)
    ctx = AsyncMock()
    ctx.get_blackboard = MagicMock(return_value=bb)
    ctx.append_and_broadcast = AsyncMock(return_value=1)
    ctx.next_turn_number = AsyncMock(return_value=1)
    ctx.broadcast = AsyncMock()
    ctx.mark_waiting_for_user = MagicMock()
    ctx.is_waiting_for_user = MagicMock(return_value=is_waiting)
    ctx.get_idle_timeout = MagicMock(return_value=MagicMock(schedule=MagicMock()))
    ctx.get_conversation_timeout = MagicMock(return_value=900)
    return ctx, bb


def _event(source: str = "chat", status: EventStatus = EventStatus.ACTIVE):
    return SimpleNamespace(source=source, status=status)


# =============================================================================
# 1. handle_wait_for_user never schedules an idle timeout
# =============================================================================


class TestWaitForUserNeverSchedulesIdleTimeout:
    @pytest.mark.asyncio
    async def test_chat_source_marks_waiting_but_does_not_schedule(self):
        event = _event(source="chat")
        ctx, _ = _mock_ctx(event)
        result = await handle_wait_for_user(ctx, "evt-1", {"summary": "waiting"}, None)
        assert result is False
        ctx.mark_waiting_for_user.assert_called_once_with("evt-1")
        ctx.get_idle_timeout.assert_not_called()

    @pytest.mark.asyncio
    async def test_slack_source_marks_waiting_but_does_not_schedule(self):
        event = _event(source="slack")
        ctx, _ = _mock_ctx(event)
        await handle_wait_for_user(ctx, "evt-1", {"summary": "waiting"}, None)
        ctx.mark_waiting_for_user.assert_called_once_with("evt-1")
        ctx.get_idle_timeout.assert_not_called()

    @pytest.mark.asyncio
    async def test_automated_source_rejected_before_any_wait_state(self):
        event = _event(source="headhunter")
        ctx, _ = _mock_ctx(event)
        result = await handle_wait_for_user(ctx, "evt-1", {}, None)
        assert result is False
        ctx.mark_waiting_for_user.assert_not_called()
        ctx.get_idle_timeout.assert_not_called()


# =============================================================================
# 2. handle_classify_event only re-arms for WAITING_APPROVAL
# =============================================================================


class TestClassifyEventRearmGatedOnApprovalStatus:
    @pytest.mark.asyncio
    async def test_active_wait_for_user_park_is_not_rearmed(self):
        """A plain wait_for_user park (status stays ACTIVE) must not get an idle timer."""
        event = _event(source="chat", status=EventStatus.ACTIVE)
        ctx, _ = _mock_ctx(event, is_waiting=True)
        await handle_classify_event(
            ctx, "evt-1", {"domain": "complicated", "reasoning": "test"}, None,
        )
        ctx.get_idle_timeout.assert_not_called()

    @pytest.mark.asyncio
    async def test_waiting_approval_park_is_rearmed(self):
        """request_user_approval's own backstop is unaffected by this change."""
        event = _event(source="chat", status=EventStatus.WAITING_APPROVAL)
        ctx, _ = _mock_ctx(event, is_waiting=True)
        await handle_classify_event(
            ctx, "evt-1", {"domain": "complicated", "reasoning": "test"}, None,
        )
        ctx.get_idle_timeout.return_value.schedule.assert_called_once_with(
            "evt-1", warning_sec=900,
        )

    @pytest.mark.asyncio
    async def test_not_waiting_never_checks_status(self):
        ctx, _ = _mock_ctx(None, is_waiting=False)
        await handle_classify_event(
            ctx, "evt-1", {"domain": "complicated", "reasoning": "test"}, None,
        )
        ctx.get_blackboard.return_value.get_event.assert_not_called()
        ctx.get_idle_timeout.assert_not_called()


# =============================================================================
# Helpers -- Brain._process_with_llm (mocked stream, matches test_brain_fc_terminal_guard.py)
# =============================================================================


@dataclass
class _Chunk:
    text: Optional[str] = None
    function_call: Optional[FunctionCall] = None
    raw_parts: None = None
    grounding_metadata: None = None
    usage: None = None
    is_thought: bool = False
    done: bool = False


class MockStream:
    def __init__(self, chunks: list):
        self._chunks = chunks
        self._yielded = 0

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self._yielded >= len(self._chunks):
            raise StopAsyncIteration
        chunk = self._chunks[self._yielded]
        self._yielded += 1
        return chunk

    async def aclose(self):
        pass


def _make_event(event_id: str = "evt-text-only", source: str = "slack") -> EventDocument:
    evidence = EventEvidence(
        display_text="test", source_type=source, domain="complicated", severity="info",
    )
    return EventDocument(
        id=event_id, source=source, service="test-svc", brain_phase="dispatch",
        event=EventInput(reason="test", evidence=evidence),
        conversation=[],
    )


def _make_brain(stream_factory):
    from src.agents.brain import Brain

    bb = MagicMock()
    bb.get_event = AsyncMock(return_value=_make_event())
    bb.append_turn = AsyncMock(return_value=1)
    bb.mark_turn_status = AsyncMock()
    bb.stamp_event = AsyncMock()
    bb.redis = MagicMock()
    bb.redis.get = AsyncMock(return_value=None)

    brain = Brain(blackboard=bb, agents={})

    adapter = MagicMock()
    adapter.generate_stream = MagicMock(side_effect=stream_factory)
    adapter.set_search_enabled = MagicMock()
    brain._adapter = adapter

    brain._progressive_skills = True
    brain._skill_loader = MagicMock()
    brain._skills_version = "test"
    brain._skills_reload_lock = asyncio.Lock()

    brain._extract_context_flags = AsyncMock(return_value={"event_domain": "complicated"})
    brain._match_phases = MagicMock(return_value=["dispatch"])
    brain._build_system_prompt = AsyncMock(return_value="system prompt")
    brain._resolve_llm_params = MagicMock(return_value=("none", 0.7, 2048))
    brain._build_contents = AsyncMock(return_value=[
        {"role": "user", "parts": [{"text": "test"}]},
    ])
    brain._resolve_terminal_prompt = MagicMock(return_value=None)

    brain._broadcast = AsyncMock()
    brain._append_and_broadcast = AsyncMock(return_value=1)
    brain._next_turn_number = AsyncMock(return_value=1)
    brain._is_event_closed = AsyncMock(return_value=False)
    brain._normalize_response_parts = MagicMock(return_value=None)
    brain._emit_executive_pulse = AsyncMock()
    brain._execute_function_call = AsyncMock(return_value=True)

    brain._search_enabled = False
    brain._memory_reflex_enabled = False
    brain._reflex_fired_for = set()
    brain._reasoning_by_event = {}
    brain._response_emitted_for = set()
    brain._waiting_for_jarvis = {}
    brain._jarvis_wait_count = {}
    brain._last_processed = {}
    brain._waiting_for_user = {}
    brain._idle_timeout = MagicMock()
    brain._idle_timeout.schedule = MagicMock()
    brain._recall_lessons = {}

    return brain


def _gate_patch(tool_names):
    return patch(
        "src.agents.tool_gates.evaluate_gates",
        return_value=[{"name": n} for n in tool_names],
    )


def _gate_ctx_patch():
    return patch("src.agents.tool_gates.build_gate_context", return_value=MagicMock())


# =============================================================================
# 3. Terminal text-only (no function call) branch never schedules an idle timeout
# =============================================================================


class TestTerminalTextOnlyNeverSchedulesIdleTimeout:
    @pytest.mark.asyncio
    async def test_chat_slack_text_only_marks_waiting_without_scheduling(self):
        chunks = [_Chunk(text="Here's the answer, let me know if you need more.")]
        brain = _make_brain(stream_factory=lambda **kw: MockStream(chunks))
        event = _make_event(source="slack")

        with _gate_patch([]), _gate_ctx_patch():
            await brain._process_with_llm("evt-text-only", event, response_emitted=False)

        assert "evt-text-only" in brain._waiting_for_user
        brain._idle_timeout.schedule.assert_not_called()


# =============================================================================
# 4. Positive coverage: wait_for_user parks stay open and resumable indefinitely
# =============================================================================


def _parked_event(event_id: str = "evt-parked", parked_seconds_ago: float = 0.0) -> EventDocument:
    """An ACTIVE event whose last turn is a wait_for_user park, as produced by
    handle_wait_for_user (and by Brain._escalate_to_human, which shares the same
    action="wait"/waitingFor="user" turn shape)."""
    return EventDocument(
        id=event_id,
        source="chat",
        status=EventStatus.ACTIVE,
        service="test-svc",
        event=EventInput(
            reason="test",
            evidence=EventEvidence(display_text="test", source_type="chat", severity="info"),
        ),
        conversation=[
            ConversationTurn(turn=0, actor="user", action="message", thoughts="can you check this?"),
            ConversationTurn(
                turn=1, actor="brain", action="wait", thoughts="On it, one sec.",
                waitingFor="user", timestamp=time.time() - parked_seconds_ago,
            ),
        ],
    )


class TestWaitForUserParkSurvivesRestartAndResumes:
    @pytest.mark.asyncio
    async def test_stale_cleanup_never_closes_a_wait_for_user_park_no_matter_the_age(self):
        """_cleanup_stale_events runs on every Brain restart. A wait_for_user park
        must survive it regardless of how long it's been parked -- there's no
        time-based check in the exemption, so this proves "indefinitely", not just
        "until the next restart"."""
        from src.agents.brain import Brain

        # Simulate a park that's been sitting for 30 days -- long past what the
        # old idle-timeout backstop (~15-25 min) would have tolerated.
        event = _parked_event(parked_seconds_ago=30 * 24 * 3600)

        bb = MagicMock()
        bb.EVENT_ACTIVE = "darwin:event:active"
        bb.EVENT_QUEUE = "darwin:queue"
        bb.redis = MagicMock()
        bb.redis.srem = AsyncMock()
        bb.redis.lpush = AsyncMock()
        bb.get_active_events = AsyncMock(return_value=["evt-parked"])
        bb.mark_turns_evaluated = AsyncMock()
        bb.get_event = AsyncMock(return_value=event)
        bb.close_event = AsyncMock()

        brain = Brain(blackboard=bb, agents={})
        brain._broadcast = AsyncMock()

        await brain._cleanup_stale_events()

        bb.close_event.assert_not_awaited()
        assert event.status == EventStatus.ACTIVE

    @pytest.mark.asyncio
    async def test_follow_up_user_turn_processes_correctly_after_surviving_restart(self):
        """The park isn't just left un-closed -- it's genuinely resumable: a real
        follow-up turn (the user replying) still classifies and re-invokes the LLM
        normally, exactly as it would if the event had never been parked."""
        event = _parked_event(parked_seconds_ago=30 * 24 * 3600)
        ctx, bb = _mock_ctx(event, is_waiting=True)

        result = await handle_classify_event(
            ctx, "evt-parked",
            {"domain": "complicated", "reasoning": "user followed up"},
            None,
        )

        # Re-invokes the LLM to act on the follow-up, same as any live event.
        assert result is True
        assert ctx.append_and_broadcast.await_count == 2
        # Still ACTIVE (not WAITING_APPROVAL), so the re-arm branch is a no-op --
        # confirms resumption doesn't accidentally reintroduce an idle timer.
        ctx.get_idle_timeout.assert_not_called()
