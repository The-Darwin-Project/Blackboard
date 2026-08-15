# tests/test_brain_fc_terminal_guard.py
# @ai-rules:
# 1. [Constraint]: Direct _process_with_llm tests with targeted stubs (matches test_stream_timeout.py).
# 2. [Pattern]: AsyncMock adapter with MockStream for controlled async iteration -- copied harness.
# 3. [Constraint]: _execute_function_call is mocked -- these tests verify emission/guard behavior only,
#    not tool execution side effects.
"""Regression tests for evt-cc105cc5: empty FC guard double-message bug.

Verifies the is_terminal split in _process_with_llm's FC-path emission:
- Non-terminal tools (e.g. classify_event): pre-FC text downgraded to brain.thoughts.
- Terminal tools (_CYCLE_ENDING_TOOLS, e.g. wait_for_user): pre-FC text stays brain.response.
- Regression: a non-terminal-FC iteration followed by a text-only iteration must
  produce exactly ONE brain.response (the original bug produced two).
- SILENT_PARK gate: narration-only text must not satisfy "respond before parking".
- RECALL continuation: when the memory reflex gate intercepts a non-terminal FC before
  it executes, the pre-reflex narration is still thoughts-only, and the eventual
  post-RECALL text-only answer is the sole brain.response for the cycle.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.agents.brain import Brain
from src.agents.llm.types import FunctionCall
from src.agents.tool_gates import GateContext, _pred_silent_park
from src.models import EventDocument, EventEvidence, EventInput


@dataclass
class _Chunk:
    """Minimal LLMChunk stand-in for tests."""
    text: Optional[str] = None
    function_call: Optional[FunctionCall] = None
    raw_parts: None = None
    grounding_metadata: None = None
    usage: None = None
    is_thought: bool = False
    done: bool = False


class MockStream:
    """Async iterable that yields a fixed list of chunks then stops."""

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


def _make_event(event_id: str = "evt-cc105cc5", source: str = "slack") -> EventDocument:
    evidence = EventEvidence(
        display_text="test", source_type=source, domain="complicated", severity="info",
    )
    return EventDocument(
        id=event_id, source=source, service="test-svc", brain_phase="dispatch",
        event=EventInput(reason="test", evidence=evidence),
        conversation=[],
    )


def _make_brain(stream_factory) -> Brain:
    """Create a Brain with minimal stubs for _process_with_llm FC-path tests."""
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
    return patch(
        "src.agents.tool_gates.build_gate_context",
        return_value=MagicMock(),
    )


def _turns_by_action(brain: Brain, action: str) -> list:
    turns = []
    for call in brain._append_and_broadcast.call_args_list:
        turn = call[0][1] if len(call[0]) > 1 else call.kwargs.get("turn")
        if turn and getattr(turn, "action", None) == action:
            turns.append(turn)
    return turns


class TestNonTerminalFCDowngradedToThoughts:
    """Non-terminal FC (e.g. classify_event): pre-FC text must become brain.thoughts, not brain.response."""

    @pytest.mark.asyncio
    async def test_narration_emitted_as_thoughts_not_response(self):
        chunks = [
            _Chunk(text="Let me classify this event."),
            _Chunk(function_call=FunctionCall(name="classify_event", args={"domain": "complicated"})),
        ]
        brain = _make_brain(stream_factory=lambda **kw: MockStream(chunks))
        event = _make_event()

        with _gate_patch(["classify_event"]), _gate_ctx_patch():
            result = await brain._process_with_llm("evt-cc105cc5", event, response_emitted=False)

        response_turns = _turns_by_action(brain, "response")
        thoughts_turns = _turns_by_action(brain, "thoughts")
        assert len(response_turns) == 0, "non-terminal FC text must not be sent as brain.response"
        assert len(thoughts_turns) == 1
        assert thoughts_turns[0].thoughts == "Let me classify this event."
        assert result is True  # _execute_function_call mock return value passed through

    @pytest.mark.asyncio
    async def test_response_emitted_for_not_updated(self):
        """Downgrading to thoughts must NOT mark the event as having emitted a response --
        otherwise the next iteration's real answer would itself get suppressed."""
        chunks = [
            _Chunk(text="Checking now."),
            _Chunk(function_call=FunctionCall(name="classify_event", args={})),
        ]
        brain = _make_brain(stream_factory=lambda **kw: MockStream(chunks))
        event = _make_event()

        with _gate_patch(["classify_event"]), _gate_ctx_patch():
            await brain._process_with_llm("evt-cc105cc5", event, response_emitted=False)

        assert "evt-cc105cc5" not in brain._response_emitted_for
        brain._emit_executive_pulse.assert_not_called()

    @pytest.mark.asyncio
    async def test_tool_still_executed(self):
        """Downgrading text emission must not skip actual tool execution."""
        chunks = [
            _Chunk(text="Checking now."),
            _Chunk(function_call=FunctionCall(name="classify_event", args={"domain": "complicated"})),
        ]
        brain = _make_brain(stream_factory=lambda **kw: MockStream(chunks))
        event = _make_event()

        with _gate_patch(["classify_event"]), _gate_ctx_patch():
            await brain._process_with_llm("evt-cc105cc5", event, response_emitted=False)

        brain._execute_function_call.assert_awaited_once()
        assert brain._execute_function_call.await_args.args[1] == "classify_event"


class TestTerminalFCStillEmitsResponse:
    """Terminal FC (_CYCLE_ENDING_TOOLS, e.g. wait_for_user): pre-FC text must stay brain.response."""

    @pytest.mark.asyncio
    async def test_terminal_text_emitted_as_response(self):
        chunks = [
            _Chunk(text="I'll pause here for your reply."),
            _Chunk(function_call=FunctionCall(name="wait_for_user", args={})),
        ]
        brain = _make_brain(stream_factory=lambda **kw: MockStream(chunks))
        event = _make_event()

        with _gate_patch(["wait_for_user"]), _gate_ctx_patch():
            await brain._process_with_llm("evt-cc105cc5", event, response_emitted=False)

        response_turns = _turns_by_action(brain, "response")
        thoughts_turns = _turns_by_action(brain, "thoughts")
        assert len(response_turns) == 1
        assert response_turns[0].thoughts == "I'll pause here for your reply."
        assert len(thoughts_turns) == 0

    @pytest.mark.asyncio
    async def test_response_emitted_for_updated_and_pulse_fired(self):
        chunks = [
            _Chunk(text="Closing this out."),
            _Chunk(function_call=FunctionCall(name="close_event", args={})),
        ]
        brain = _make_brain(stream_factory=lambda **kw: MockStream(chunks))
        event = _make_event()

        with _gate_patch(["close_event"]), _gate_ctx_patch():
            await brain._process_with_llm("evt-cc105cc5", event, response_emitted=False)

        assert "evt-cc105cc5" in brain._response_emitted_for
        brain._emit_executive_pulse.assert_awaited_once_with(
            "evt-cc105cc5", [("tool:brain_response", "tool")]
        )


class TestDoubleMessageRegression:
    """Reproduces the exact evt-cc105cc5 scenario: non-terminal FC iteration followed by a
    text-only iteration must yield exactly ONE brain.response across both iterations."""

    @pytest.mark.asyncio
    async def test_single_response_across_two_iterations(self):
        iter0_chunks = [
            _Chunk(text="Let me classify this."),
            _Chunk(function_call=FunctionCall(name="classify_event", args={})),
        ]
        iter1_chunks = [_Chunk(text="This is a COMPLICATED event. How can I help?")]
        streams = iter([MockStream(iter0_chunks), MockStream(iter1_chunks)])

        brain = _make_brain(stream_factory=lambda **kw: next(streams))
        event = _make_event(source="slack")

        with _gate_patch(["classify_event", "wait_for_user"]), _gate_ctx_patch():
            # Iteration 0: mirrors the outer loop in _process_event_inner.
            should_continue = await brain._process_with_llm(
                "evt-cc105cc5", event, iteration=0, response_emitted=False,
            )
            response_emitted = "evt-cc105cc5" in brain._response_emitted_for
            assert should_continue is True
            assert response_emitted is False, (
                "non-terminal FC narration must not flip response_emitted -- "
                "otherwise the real answer in the next iteration gets suppressed"
            )

            # Iteration 1: text-only, no FC -- this is where the original bug fired a 2nd message.
            await brain._process_with_llm(
                "evt-cc105cc5", event, iteration=1, response_emitted=response_emitted,
            )

        response_turns = _turns_by_action(brain, "response")
        assert len(response_turns) == 1, (
            f"expected exactly one brain.response across both iterations, got {len(response_turns)}"
        )
        assert response_turns[0].thoughts == "This is a COMPLICATED event. How can I help?"

        thoughts_turns = _turns_by_action(brain, "thoughts")
        assert len(thoughts_turns) == 1
        assert thoughts_turns[0].thoughts == "Let me classify this."

        # Auto-park still fires off the sole (terminal) text-only response for slack/chat sources.
        assert "evt-cc105cc5" in brain._waiting_for_user


class TestSilentParkGateInteraction:
    """SILENT_PARK gate must not treat narration (brain.thoughts) as a satisfying response."""

    @staticmethod
    def _turn(actor: str, action: str):
        t = MagicMock()
        t.actor = actor
        t.action = action
        return t

    @staticmethod
    def _ctx(conversation: list, source: str = "slack") -> GateContext:
        return GateContext(
            brain_phase="dispatch",
            event_source=source,
            context_flags={},
            conversation=conversation,
            is_defer_wake=False,
            iteration=0,
            has_kargo_context=False,
            has_github_context=False,
            unread_notes=0,
        )

    def test_narration_only_does_not_satisfy_gate(self):
        """After downgrading non-terminal FC text to brain.thoughts, the gate must still
        block wait_for_user until a real brain.response is generated."""
        conversation = [
            self._turn("user", "message"),
            self._turn("brain", "thoughts"),
        ]
        assert _pred_silent_park(self._ctx(conversation)) is True

    def test_real_response_satisfies_gate(self):
        conversation = [
            self._turn("user", "message"),
            self._turn("brain", "response"),
        ]
        assert _pred_silent_park(self._ctx(conversation)) is False

    def test_non_chat_source_never_blocks(self):
        conversation = [
            self._turn("user", "message"),
            self._turn("brain", "thoughts"),
        ]
        assert _pred_silent_park(self._ctx(conversation, source="headhunter")) is False


class TestRecallContinuation:
    """Memory reflex (RECALL) gate intercepts a non-terminal FC before it executes,
    re-invoking the LLM. The pre-reflex narration must still be downgraded to
    brain.thoughts, and the eventual post-RECALL text-only answer must be the sole
    brain.response across the whole cycle -- same invariant as the double-message
    regression, but exercised through the RECALL early-return path instead of a
    normal tool execution."""

    @pytest.mark.asyncio
    async def test_recall_continuation_single_response(self):
        iter0_chunks = [
            _Chunk(text="Let me check for similar issues first."),
            _Chunk(function_call=FunctionCall(name="classify_event", args={})),
        ]
        iter1_chunks = [_Chunk(text="Based on a past incident, this is a config drift issue.")]
        streams = iter([MockStream(iter0_chunks), MockStream(iter1_chunks)])

        brain = _make_brain(stream_factory=lambda **kw: next(streams))
        event = _make_event(source="slack")

        mock_searcher = MagicMock()
        mock_searcher.gather = AsyncMock(return_value=[{"payload": {"title": "past incident"}, "score": 0.91}])
        mock_searcher.fire = MagicMock()
        mock_chunker = MagicMock()
        mock_chunker.feed = MagicMock(return_value=None)
        mock_chunker.flush = MagicMock(return_value=None)
        brain._create_reflex_pair = MagicMock(return_value=(mock_chunker, mock_searcher))

        with _gate_patch(["classify_event", "wait_for_user"]), _gate_ctx_patch():
            # Iteration 0: non-terminal FC -- RECALL fires before the tool executes.
            should_continue = await brain._process_with_llm(
                "evt-cc105cc5", event, iteration=0, response_emitted=False,
            )
            response_emitted = "evt-cc105cc5" in brain._response_emitted_for
            assert should_continue is True, "RECALL block re-invokes the LLM -- loop must continue"
            assert response_emitted is False, (
                "non-terminal FC narration must not flip response_emitted even when "
                "the tool never actually executes (RECALL intercepted it)"
            )
            brain._execute_function_call.assert_not_awaited()
            assert "evt-cc105cc5" in brain._reflex_fired_for

            # Iteration 1: text-only answer produced after RECALL context injection.
            await brain._process_with_llm(
                "evt-cc105cc5", event, iteration=1, response_emitted=response_emitted,
            )

        response_turns = _turns_by_action(brain, "response")
        assert len(response_turns) == 1, (
            f"expected exactly one brain.response across the RECALL cycle, got {len(response_turns)}"
        )
        assert response_turns[0].thoughts == "Based on a past incident, this is a config drift issue."

        thoughts_turns = _turns_by_action(brain, "thoughts")
        assert len(thoughts_turns) == 1
        assert thoughts_turns[0].thoughts == "Let me check for similar issues first."

        # Auto-park still fires off the sole (terminal) text-only response for slack/chat sources.
        assert "evt-cc105cc5" in brain._waiting_for_user
