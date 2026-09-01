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


def _tool_names_from_last_generate_stream(brain: Brain) -> set[str]:
    tools = brain._adapter.generate_stream.call_args.kwargs["tools"]
    return {tool["name"] for tool in tools}


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


class TestIntermediateToolRailway:
    @pytest.mark.asyncio
    async def test_process_with_llm_passes_defer_event_in_intermediate_toolset(self):
        brain = _make_brain(stream_factory=lambda **kw: MockStream([]))
        event = _make_event(source="aligner")
        brain._extract_context_flags = AsyncMock(return_value={
            "is_intermediate": True,
            "brain_has_classified": True,
            "event_domain": "complicated",
        })

        await brain._process_with_llm("evt-cc105cc5", event, response_emitted=False)

        assert "defer_event" in _tool_names_from_last_generate_stream(brain)

    @pytest.mark.asyncio
    async def test_process_with_llm_intermediate_empty_toolset_fallback_includes_defer(self):
        brain = _make_brain(stream_factory=lambda **kw: MockStream([]))
        event = _make_event(source="aligner")
        brain._extract_context_flags = AsyncMock(return_value={
            "is_intermediate": True,
            "brain_has_classified": True,
            "event_domain": "complicated",
        })

        with _gate_patch([]), _gate_ctx_patch():
            await brain._process_with_llm("evt-cc105cc5", event, response_emitted=False)

        assert _tool_names_from_last_generate_stream(brain) == {"wait_for_agent", "defer_event"}

    @pytest.mark.asyncio
    async def test_process_with_llm_empty_toolset_fallback_respects_hard_strip_defer(self):
        """M4: the empty-toolset recovery fallback must honor HARD_STRIP_DEFER's
        jarvis/triage policy via the shared predicate, not unconditionally
        re-inject defer_event. Real build_gate_context runs here (not patched)
        so the jarvis-source policy is genuinely exercised."""
        brain = _make_brain(stream_factory=lambda **kw: MockStream([]))
        event = _make_event(source="jarvis")
        brain._extract_context_flags = AsyncMock(return_value={
            "is_intermediate": True,
            "brain_has_classified": True,
            "event_domain": "complicated",
        })

        with _gate_patch([]):
            await brain._process_with_llm("evt-cc105cc5", event, response_emitted=False)

        assert _tool_names_from_last_generate_stream(brain) == {"wait_for_agent"}

    @pytest.mark.asyncio
    async def test_intermediate_tool_leak_guard_uses_shared_constant(self):
        """M3: the post-gate leak-detector's allow-set must be the same
        INTERMEDIATE_TOOLS object tool_gates.py exports -- guards against the
        three call sites (here, _tools_intermediate, empty-toolset fallback)
        drifting apart via hand-duplicated literals."""
        from src.agents.tool_gates import INTERMEDIATE_TOOLS

        brain = _make_brain(stream_factory=lambda **kw: MockStream([]))
        event = _make_event(source="aligner")
        brain._extract_context_flags = AsyncMock(return_value={
            "is_intermediate": True,
            "brain_has_classified": True,
            "event_domain": "complicated",
        })
        leaked_tool = "select_agent"
        assert leaked_tool not in INTERMEDIATE_TOOLS

        with _gate_patch(list(INTERMEDIATE_TOOLS) + [leaked_tool]), _gate_ctx_patch():
            await brain._process_with_llm("evt-cc105cc5", event, response_emitted=False)

        assert _tool_names_from_last_generate_stream(brain) == set(INTERMEDIATE_TOOLS)


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


class TestRuntimeGateDoesNotClobberSilentParkInvalidation:
    """Regression guard: when SILENT_PARK strips wait_for_user pre-call but
    _response_emitted_for confirms a brain.response was flushed, the invalidation
    must re-admit wait_for_user and let it execute.

    This exact regression was reintroduced twice (Aug 4 commit 2f297957, Aug 15
    commit b9a130c33) by blind restoration of a redundant gate check that
    recomputed valid_tool_names from active_tools without the invalidation.
    """

    @pytest.mark.asyncio
    async def test_wait_for_user_executes_when_invalidation_fires(self):
        """SILENT_PARK strips wait_for_user, but _response_emitted_for is set
        (text flush satisfied the gate premise). wait_for_user must execute."""
        chunks = [
            _Chunk(text="Here's my response to you."),
            _Chunk(function_call=FunctionCall(name="wait_for_user", args={"reason": "casual park"})),
        ]
        brain = _make_brain(stream_factory=lambda **kw: MockStream(chunks))
        event = _make_event(source="slack")

        tools_without_wait = ["classify_event", "select_agent", "consult_deep_memory"]

        with _gate_patch(tools_without_wait), _gate_ctx_patch():
            await brain._process_with_llm(
                "evt-cc105cc5", event, response_emitted=False,
            )

        brain._execute_function_call.assert_awaited_once()
        call_args = brain._execute_function_call.call_args[0]
        assert call_args[1] == "wait_for_user"

        tool_results = _turns_by_action(brain, "tool_result")
        assert len(tool_results) == 0, (
            f"wait_for_user was rejected despite invalidation: {[t.thoughts for t in tool_results]}"
        )

    @pytest.mark.asyncio
    async def test_stripped_tool_without_invalidation_still_rejected(self):
        """A gate-stripped tool that is NOT wait_for_user (or has no
        _response_emitted_for) must still be rejected normally."""
        chunks = [
            _Chunk(function_call=FunctionCall(name="close_event", args={"summary": "done"})),
        ]
        brain = _make_brain(stream_factory=lambda **kw: MockStream(chunks))
        event = _make_event(source="slack")

        tools_without_close = ["classify_event", "wait_for_user", "select_agent"]

        with _gate_patch(tools_without_close), _gate_ctx_patch():
            result = await brain._process_with_llm(
                "evt-cc105cc5", event, response_emitted=False,
            )

        assert result is True
        brain._execute_function_call.assert_not_awaited()
        tool_results = _turns_by_action(brain, "tool_result")
        assert len(tool_results) == 1
        assert "[GATE]" in tool_results[0].thoughts or "[UNKNOWN]" in tool_results[0].thoughts

    @pytest.mark.asyncio
    async def test_unknown_tool_still_rejected(self):
        """Spec T-2: a tool not in BRAIN_TOOL_SCHEMAS is rejected as [UNKNOWN]."""
        chunks = [
            _Chunk(function_call=FunctionCall(name="nonexistent_tool", args={})),
        ]
        brain = _make_brain(stream_factory=lambda **kw: MockStream(chunks))
        event = _make_event(source="slack")

        with _gate_patch(["classify_event", "wait_for_user"]), _gate_ctx_patch():
            result = await brain._process_with_llm(
                "evt-cc105cc5", event, response_emitted=False,
            )

        assert result is True
        brain._execute_function_call.assert_not_awaited()
        tool_results = _turns_by_action(brain, "tool_result")
        assert len(tool_results) == 1
        assert "[UNKNOWN]" in tool_results[0].thoughts

    @pytest.mark.asyncio
    async def test_wait_for_user_rejected_without_response_emitted(self):
        """Edge case: wait_for_user stripped AND no text flush (no _response_emitted_for).
        The invalidation must NOT fire — wait_for_user stays rejected."""
        chunks = [
            _Chunk(function_call=FunctionCall(name="wait_for_user", args={"reason": "park"})),
        ]
        brain = _make_brain(stream_factory=lambda **kw: MockStream(chunks))
        event = _make_event(source="slack")

        tools_without_wait = ["classify_event", "select_agent"]

        with _gate_patch(tools_without_wait), _gate_ctx_patch():
            result = await brain._process_with_llm(
                "evt-cc105cc5", event, response_emitted=False,
            )

        assert result is True
        brain._execute_function_call.assert_not_awaited()
        tool_results = _turns_by_action(brain, "tool_result")
        assert len(tool_results) == 1
        assert "[GATE]" in tool_results[0].thoughts


class TestClearWaitingResetsResponseEmittedAcrossCycles:
    """Regression guard: clear_waiting() must discard the event from
    _response_emitted_for, so a stale flag from a prior park cycle can't
    defeat the SILENT_PARK invalidation in a later cycle.

    Without this reset, the sequence is: cycle 1 flushes a response and parks
    (setting _response_emitted_for) -> user sends a new message, which calls
    clear_waiting() -> cycle 2 begins and the LLM's first action is
    wait_for_user with no new text flush. If the flag is still stale-True,
    the invalidation incorrectly re-admits wait_for_user using cycle 1's
    already-consumed response, and the brain silently re-parks without ever
    answering the new message.
    """

    @pytest.mark.asyncio
    async def test_stale_flag_does_not_survive_clear_waiting_into_next_cycle(self):
        event_id = "evt-cc105cc5"
        brain = _make_brain(stream_factory=lambda **kw: None)  # overridden per-call below
        event = _make_event(event_id=event_id, source="slack")

        tools_without_wait = ["classify_event", "select_agent", "consult_deep_memory"]

        # Cycle 1: text response flushed, then wait_for_user -- SILENT_PARK
        # invalidation re-admits it because a response was just emitted.
        cycle1_chunks = [
            _Chunk(text="Here's my response to you."),
            _Chunk(function_call=FunctionCall(name="wait_for_user", args={"reason": "casual park"})),
        ]
        brain._adapter.generate_stream = MagicMock(side_effect=lambda **kw: MockStream(cycle1_chunks))

        with _gate_patch(tools_without_wait), _gate_ctx_patch():
            await brain._process_with_llm(event_id, event, response_emitted=False)

        brain._execute_function_call.assert_awaited_once()
        assert event_id in brain._response_emitted_for, (
            "precondition: cycle 1's text flush must mark the event as having emitted a response"
        )

        # User replies -- the real system calls clear_waiting() on this transition
        # (main.py WS handler / queue.py REST endpoint), which must also reset
        # the per-cycle response-emitted flag.
        brain.clear_waiting(event_id)
        assert event_id not in brain._response_emitted_for, (
            "clear_waiting() must discard the event from _response_emitted_for "
            "so a stale flag from the prior cycle can't leak into the next one"
        )

        # Cycle 2: wait_for_user is the FIRST action, with no text flushed this
        # cycle. With the flag correctly cleared, invalidation must not fire --
        # wait_for_user stays rejected, forcing the brain to actually answer.
        brain._execute_function_call.reset_mock()
        brain._append_and_broadcast.reset_mock()
        cycle2_chunks = [
            _Chunk(function_call=FunctionCall(name="wait_for_user", args={"reason": "premature park"})),
        ]
        brain._adapter.generate_stream = MagicMock(side_effect=lambda **kw: MockStream(cycle2_chunks))

        with _gate_patch(tools_without_wait), _gate_ctx_patch():
            result = await brain._process_with_llm(event_id, event, response_emitted=False)

        assert result is True
        brain._execute_function_call.assert_not_awaited()
        tool_results = _turns_by_action(brain, "tool_result")
        assert len(tool_results) == 1, (
            "wait_for_user was incorrectly re-admitted using a stale "
            "_response_emitted_for flag from the prior park/resume cycle"
        )
        assert "[GATE]" in tool_results[0].thoughts
