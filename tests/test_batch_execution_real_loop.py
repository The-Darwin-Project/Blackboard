# BlackBoard/tests/test_batch_execution_real_loop.py
# @ai-rules:
# 1. [Constraint]: These tests MUST drive the real `_process_with_llm` / `_execute_function_call` /
#    `evaluate_gates` / `build_gate_context` wiring -- no hand-rolled stand-ins for the batch
#    loop's control flow (that gap is exactly what this file exists to close; see PR #189
#    code_reviewer testing-HIGH finding).
# 2. [Pattern]: Brain construction + streaming-adapter mocking follows test_stream_timeout.py's
#    `_make_brain(stream_factory)` / `_Chunk` / `MockStream` conventions exactly.
# 3. [Pattern]: `evaluate_gates`/`build_gate_context` are patched at `src.agents.tool_gates.*`
#    (NOT `src.agents.brain.*`) because brain.py does a fresh `from .tool_gates import ...`
#    on every call (both the outer gate evaluation and the per-FC batch re-check).
# 4. [Gotcha]: `_normalize_response_parts` is mocked as identity (not None like
#    test_stream_timeout) so plain-dict `raw_parts` survive into `captured_parts` unchanged --
#    real SDK Part objects are not needed to exercise the batch-detection/execution code.
# 5. [Pattern]: FC handlers are real (HANDLER_REGISTRY is never mocked). Tool names are chosen
#    per-test for minimal blackboard mocking: classify_event/set_phase/defer_event are cheap;
#    select_agent is only used via its "already running" short-circuit (is_task_running=True)
#    to avoid needing to mock real agent dispatch.
"""Real execution-loop coverage for the parallel-FC batch path (PR #189 remediation).

Exercises the actual `_process_with_llm` batch loop end-to-end for:
(a) FC[0] gate rejection (security fix -- FC[0] now gets the same authorization
    check as FC[1+], previously bypassed entirely).
(b) both early-exit breaks (`not result`, `_is_event_closed`).
(c) the gate-re-eval exception path (reliability fix -- unhandled exception now
    caught, logged, and halts the batch with a diagnostic turn).
(e) the `defer_event` duplicate-defer no-op (reliability/idempotency fix).

Also covers the maintainability fix (restored is_terminal response/narration split
in the single-FC path) since it lives in the same method and was previously
described as "unchanged" while silently regressing.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.agents.brain import Brain
from src.agents.tool_gates import GateContext
from src.models import EventDocument, EventEvidence, EventInput, EventStatus


# ---------------------------------------------------------------------------
# Shared fixtures / helpers (mirrors tests/test_stream_timeout.py conventions)
# ---------------------------------------------------------------------------

@dataclass
class _Chunk:
    """Minimal LLMChunk stand-in for tests."""
    text: Optional[str] = None
    function_call: object = None
    raw_parts: Optional[list] = None
    grounding_metadata: Optional[dict] = None
    usage: object = None
    is_thought: bool = False
    done: bool = False


class MockStream:
    """Async iterable that yields chunks then stops."""

    def __init__(self, chunks: list):
        self._chunks = chunks
        self._yielded = 0
        self.aclose_called = False

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self._yielded >= len(self._chunks):
            raise StopAsyncIteration
        chunk = self._chunks[self._yielded]
        self._yielded += 1
        return chunk

    async def aclose(self):
        self.aclose_called = True


def _make_event(event_id: str = "evt-test", source: str = "headhunter", brain_phase: str = "dispatch") -> EventDocument:
    evidence = EventEvidence(
        display_text="test", source_type=source, domain="complicated", severity="info",
    )
    return EventDocument(
        id=event_id, source=source, service="test-svc", brain_phase=brain_phase,
        status=EventStatus.ACTIVE,
        event=EventInput(reason="test", evidence=evidence),
        conversation=[],
    )


def _make_brain(stream_factory=None) -> Brain:
    """Create a Brain with minimal stubs, but a REAL _tool_ctx/HANDLER_REGISTRY, so
    _execute_function_call dispatches to real handlers under a mocked blackboard."""
    bb = MagicMock()
    bb.get_event = AsyncMock(return_value=_make_event())
    bb.append_turn = AsyncMock(return_value=1)
    bb.mark_turn_status = AsyncMock()
    bb.stamp_event = AsyncMock()
    bb.redis = MagicMock()
    bb.redis.get = AsyncMock(return_value=None)
    # Handler-specific blackboard surface (classify_event, set_phase, defer_event, select_agent)
    bb.update_event_domain = AsyncMock()
    bb.update_event_severity = AsyncMock()
    bb.update_event_phase = AsyncMock()
    bb.defer_event_status = AsyncMock(return_value=True)
    bb.record_event = AsyncMock()
    bb.get_flow_metrics = AsyncMock(return_value={"queue_depth": 0, "active_events": []})
    bb.get_service = AsyncMock(return_value=None)
    bb.get_services = AsyncMock(return_value={})

    brain = Brain(blackboard=bb, agents={})

    adapter = MagicMock()
    if stream_factory:
        adapter.generate_stream = MagicMock(side_effect=stream_factory)
    adapter.set_search_enabled = MagicMock()
    brain._adapter = adapter

    brain._progressive_skills = True
    brain._skill_loader = MagicMock()
    brain._skill_loader.get_tool_skills = MagicMock(return_value=[])
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
    brain._normalize_response_parts = MagicMock(side_effect=lambda rp: rp)
    brain._emit_executive_pulse = AsyncMock()

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


def _gate_patch(tool_names: list[str]):
    """Patch the OUTER (and FC[0] batch) gate evaluation to a fixed toolset."""
    return patch(
        "src.agents.tool_gates.evaluate_gates",
        return_value=[{"name": n} for n in tool_names],
    )


def _default_gate_ctx(**overrides) -> GateContext:
    defaults = dict(
        brain_phase="dispatch",
        event_source="headhunter",
        context_flags={"brain_has_classified": True, "event_domain": "complicated"},
        conversation=[],
        is_defer_wake=False,
        iteration=0,
        has_kargo_context=False,
        has_github_context=False,
        unread_notes=0,
    )
    defaults.update(overrides)
    return GateContext(**defaults)


def _gate_ctx_patch(side_effect=None, return_value=None):
    kwargs = (
        {"side_effect": side_effect}
        if side_effect is not None
        else {"return_value": return_value if return_value is not None else _default_gate_ctx()}
    )
    return patch("src.agents.tool_gates.build_gate_context", **kwargs)


def _fc(name: str, args: dict | None = None) -> dict:
    return {"functionCall": {"name": name, "args": args or {}}}


def _turns(brain: Brain) -> list:
    """Extract every ConversationTurn passed to _append_and_broadcast, in call order."""
    out = []
    for call in brain._append_and_broadcast.call_args_list:
        turn = call.args[1] if len(call.args) > 1 else call.kwargs.get("turn")
        if turn is not None:
            out.append(turn)
    return out


# ---------------------------------------------------------------------------
# (a) FC[0] gate rejection -- security fix regression test
# ---------------------------------------------------------------------------

class TestFC0GateRejection:
    """Batch loop's authorization re-check must cover FC[0], not just FC[1+], and
    maintain 1:1 FR parity (Step 5) when halting on a gated FC."""

    @pytest.mark.asyncio
    async def test_fc0_rejected_by_gate_never_executes_and_writes_no_turn(self):
        """FC[0]'s tool is absent from active_tools -- real handlers (classify_event/select_agent)
        must never run; Step 5 emits paired [GATE] + [GATE] Skipped FR turns (turn=0) and
        returns True so the LLM can self-correct."""
        fcs = [_fc("classify_event", {"domain": "clear"}), _fc("select_agent", {"agent_name": "developer"})]
        stream = MockStream([_Chunk(raw_parts=fcs)])
        brain = _make_brain(stream_factory=lambda **kw: stream)
        event = _make_event()
        gated_ctx = _default_gate_ctx(
            context_flags={"is_intermediate": True, "brain_has_classified": True, "event_domain": "complicated"},
        )

        with patch("src.agents.brain._THOUGHT_SIG_V2", True), \
                _gate_patch(["close_event"]), _gate_ctx_patch(return_value=gated_ctx):
            result = await brain._process_with_llm("evt-test", event)

        assert result is True
        brain.blackboard.update_event_domain.assert_not_awaited()
        turns = _turns(brain)
        assert len(turns) == 2, f"Expected 2 paired FR turns (FC[0] rejected + FC[1] skipped), got {len(turns)}"
        assert turns[0].turn == 0
        assert turns[0].actor == "brain"
        assert turns[0].action == "tool_result"
        assert turns[0].waitingFor == "classify_event"
        assert turns[0].batch_size == 2
        assert turns[0].batch_index is None
        assert turns[0].response_parts == fcs
        assert (turns[0].thoughts or "").startswith("[GATE] ")
        assert "[GATE] [GATE]" not in (turns[0].thoughts or "")

        assert turns[1].turn == 0
        assert turns[1].actor == "brain"
        assert turns[1].action == "tool_result"
        assert turns[1].waitingFor == "select_agent"
        assert turns[1].batch_index == 1
        assert "[GATE] Skipped" in (turns[1].thoughts or "")
        assert "classify_event" in (turns[1].thoughts or "")

    @pytest.mark.asyncio
    async def test_fc1_still_rejected_when_gate_narrows_after_fc0(self):
        """Sanity check: FC[1] rejection executes FC[0], rejects FC[1] via freshly
        re-evaluated gate, emits a paired [GATE] tool_result turn (batch_index=1, turn=0),
        and returns True so the LLM can continue."""
        fcs = [_fc("classify_event", {"domain": "clear"}), _fc("select_agent", {"agent_name": "developer"})]
        stream = MockStream([_Chunk(raw_parts=fcs)])
        brain = _make_brain(stream_factory=lambda **kw: stream)
        event = _make_event()
        open_ctx = _default_gate_ctx()
        narrowed_ctx = _default_gate_ctx(
            context_flags={"is_intermediate": True, "brain_has_classified": True, "event_domain": "clear"},
        )

        with patch("src.agents.brain._THOUGHT_SIG_V2", True), \
                _gate_ctx_patch(side_effect=[open_ctx, narrowed_ctx]), \
                patch("src.agents.tool_gates.evaluate_gates") as mock_eval:
            # First call = outer active_tools (both allowed). Second call = FC[1] re-eval
            # (select_agent no longer allowed after classify_event ran).
            mock_eval.side_effect = [
                [{"name": "classify_event"}, {"name": "select_agent"}],
                [{"name": "classify_event"}],
            ]
            result = await brain._process_with_llm("evt-test", event)

        assert result is True
        brain.blackboard.update_event_domain.assert_awaited_once()
        turns = _turns(brain)
        assert len(turns) == 3, f"classify_event's 2 turns + FC[1] rejection turn expected, got {len(turns)}"
        rej = turns[-1]
        assert rej.turn == 0
        assert rej.actor == "brain"
        assert rej.action == "tool_result"
        assert rej.waitingFor == "select_agent"
        assert rej.batch_index == 1
        assert rej.response_parts is None
        assert (rej.thoughts or "").startswith("[GATE] ")
        assert "[GATE] [GATE]" not in (rej.thoughts or "")


# ---------------------------------------------------------------------------
# (b) Both early-exit breaks
# ---------------------------------------------------------------------------

class TestBatchEarlyExitBreaks:

    @pytest.mark.asyncio
    async def test_batch_stops_on_falsy_execute_result(self):
        """FC[0] (select_agent) returns False for real (task already running) --
        FC[1] (classify_event) must never execute."""
        fcs = [_fc("select_agent", {"agent_name": "developer", "task_instruction": "go"}),
               _fc("classify_event", {"domain": "clear"})]
        stream = MockStream([_Chunk(raw_parts=fcs)])
        brain = _make_brain(stream_factory=lambda **kw: stream)
        event = _make_event()
        brain._active_tasks["evt-test"] = MagicMock(done=MagicMock(return_value=False))

        with patch("src.agents.brain._THOUGHT_SIG_V2", True), \
                _gate_patch(["select_agent", "classify_event"]), _gate_ctx_patch():
            result = await brain._process_with_llm("evt-test", event)

        assert result is False
        brain.blackboard.update_event_domain.assert_not_awaited(), "FC[1] must not run after FC[0] returns False"
        turns = _turns(brain)
        assert len(turns) == 2, f"select_agent's dup-turn and 1 skipped turn expected, got {len(turns)}"
        assert "already actively working" in (turns[0].thoughts or "")
        assert "Skipped:" in (turns[1].thoughts or "")
        assert turns[1].waitingFor == "classify_event"

    @pytest.mark.asyncio
    async def test_batch_stops_when_event_closed_after_fc(self):
        """FC[0] (classify_event) succeeds; event is force-closed before FC[1] runs --
        the batch must stop via the _is_event_closed guard, not execute FC[1]."""
        fcs = [_fc("classify_event", {"domain": "clear"}), _fc("classify_event", {"domain": "complex"})]
        stream = MockStream([_Chunk(raw_parts=fcs)])
        brain = _make_brain(stream_factory=lambda **kw: stream)
        event = _make_event()
        # 1st call = pre-batch closed guard (line ~1711); 2nd call = post-FC[0] guard inside loop.
        brain._is_event_closed = AsyncMock(side_effect=[False, True])

        with patch("src.agents.brain._THOUGHT_SIG_V2", True), \
                _gate_patch(["classify_event"]), _gate_ctx_patch():
            result = await brain._process_with_llm("evt-test", event)

        assert result is False
        assert brain.blackboard.update_event_domain.await_count == 1, (
            "FC[0] should have run exactly once; FC[1] must not run once event is closed"
        )
        assert brain._is_event_closed.await_count == 2


# ---------------------------------------------------------------------------
# (c) Gate re-eval exception path -- reliability fix regression test
# ---------------------------------------------------------------------------

class TestGateReEvalExceptionPath:

    @pytest.mark.asyncio
    async def test_exception_during_fc1_gate_reeval_halts_batch_with_diagnostic_turn(self):
        """FC[0] succeeds; the FC[1] gate re-fetch/re-eval raises (e.g. Redis error) --
        must be caught, logged, produce a diagnostic tool_result turn for FC[1] AND a
        paired [GATE] Skipped FR turn for FC[2] (1:1 FR parity, turn=0), halt the batch
        (FC[2] never runs), and return True so the LLM can recover."""
        fcs = [
            _fc("classify_event", {"domain": "clear"}),
            _fc("select_agent", {"agent_name": "developer"}),
            _fc("set_phase", {"phase": "verify"}),
        ]
        stream = MockStream([_Chunk(raw_parts=fcs)])
        brain = _make_brain(stream_factory=lambda **kw: stream)
        event = _make_event()

        with patch("src.agents.brain._THOUGHT_SIG_V2", True), \
                _gate_patch(["classify_event", "select_agent", "set_phase"]), \
                patch("src.agents.tool_gates.build_gate_context") as mock_ctx:
            # 1st call = outer gate_ctx build (succeeds). 2nd call = FC[1] re-eval (raises).
            mock_ctx.side_effect = [_default_gate_ctx(), RuntimeError("Redis connection reset")]
            result = await brain._process_with_llm("evt-test", event)

        assert result is True
        brain.blackboard.update_event_domain.assert_awaited_once(), "FC[0] (classify_event) must have executed"
        brain.blackboard.update_event_phase.assert_not_awaited(), "FC[2] (set_phase) must never run after the exception halts the batch"

        turns = _turns(brain)
        assert len(turns) == 4, (
            f"classify_event's 2 turns + FC[1] error turn + FC[2] skipped turn expected, got {len(turns)}"
        )
        error_turn = turns[-2]
        assert error_turn.turn == 0
        assert error_turn.action == "tool_result"
        assert error_turn.waitingFor == "select_agent"
        assert error_turn.batch_index == 1
        assert "select_agent" in error_turn.thoughts
        assert "batch position 1" in error_turn.thoughts
        assert "Redis connection reset" in error_turn.thoughts
        assert "halted" in error_turn.thoughts.lower()

        skipped_turn = turns[-1]
        assert skipped_turn.turn == 0
        assert skipped_turn.actor == "brain"
        assert skipped_turn.action == "tool_result"
        assert skipped_turn.waitingFor == "set_phase"
        assert skipped_turn.batch_index == 2
        assert "[GATE] Skipped" in (skipped_turn.thoughts or "")
        assert "select_agent" in (skipped_turn.thoughts or "")


# ---------------------------------------------------------------------------
# (e) defer_event duplicate-defer no-op -- reliability/idempotency fix
# ---------------------------------------------------------------------------

class TestDeferEventDuplicateNoOp:

    @pytest.mark.asyncio
    async def test_defer_event_is_noop_when_event_already_deferred(self):
        """Real _execute_function_call -> real handle_defer_event: if the event is
        already EventStatus.DEFERRED, a re-issued defer_event call must no-op
        (not call defer_event_status again) and tell the LLM not to retry."""
        bb = MagicMock()
        deferred_event = _make_event()
        deferred_event.status = EventStatus.DEFERRED
        bb.get_event = AsyncMock(return_value=deferred_event)
        bb.defer_event_status = AsyncMock(return_value=True)
        bb.record_event = AsyncMock()

        brain = Brain(blackboard=bb, agents={})
        brain._append_and_broadcast = AsyncMock(return_value=1)
        brain._next_turn_number = AsyncMock(return_value=5)
        brain._broadcast = AsyncMock()

        result = await brain._execute_function_call(
            "evt-test", "defer_event", {"reason": "retry later", "delay_seconds": 60},
            response_parts=None,
        )

        assert result is False
        bb.defer_event_status.assert_not_awaited()
        brain._append_and_broadcast.assert_awaited_once()
        turn = brain._append_and_broadcast.call_args[0][1]
        assert turn.action == "tool_result"
        assert turn.waitingFor == "defer_event"
        assert "already deferred" in turn.thoughts.lower()

    @pytest.mark.asyncio
    async def test_defer_event_still_defers_when_not_already_deferred(self):
        """Sanity check: a fresh (non-duplicate) defer_event call still defers normally."""
        bb = MagicMock()
        active_event = _make_event()
        active_event.status = EventStatus.ACTIVE
        bb.get_event = AsyncMock(return_value=active_event)
        bb.defer_event_status = AsyncMock(return_value=True)
        bb.record_event = AsyncMock()

        brain = Brain(blackboard=bb, agents={})
        brain._append_and_broadcast = AsyncMock(return_value=1)
        brain._next_turn_number = AsyncMock(return_value=5)
        brain._broadcast = AsyncMock()

        result = await brain._execute_function_call(
            "evt-test", "defer_event", {"reason": "waiting on CI", "delay_seconds": 90},
            response_parts=None,
        )

        assert result is False
        bb.defer_event_status.assert_awaited_once()


# ---------------------------------------------------------------------------
# Bonus: maintainability fix -- restored is_terminal response/narration split
# (single-FC path, same method the batch loop lives in; the PR had silently
# removed this branch while claiming the path was "unchanged").
# ---------------------------------------------------------------------------

class TestSingleFCTerminalNarrationSplit:

    @pytest.mark.asyncio
    async def test_non_terminal_fc_flushes_accumulated_text_as_narration(self):
        """set_phase is NOT in _CYCLE_ENDING_TOOLS -- preceding accumulated_text
        must flush as a 'thoughts' (narration) turn, not a 'response' turn."""
        chunk = _Chunk(text="Let me check the current phase first.",
                       function_call=SimpleNamespace(name="set_phase", args={"phase": "verify"}))
        stream = MockStream([chunk])
        brain = _make_brain(stream_factory=lambda **kw: stream)
        event = _make_event()

        with _gate_patch(["set_phase"]), _gate_ctx_patch():
            await brain._process_with_llm("evt-test", event)

        turns = _turns(brain)
        assert turns, "expected at least the narration turn + set_phase's own turn"
        narration = turns[0]
        assert narration.action == "thoughts", f"non-terminal FC text flush should be narration, got {narration.action!r}"
        assert narration.thoughts == "Let me check the current phase first."
        assert "evt-test" not in brain._response_emitted_for, "narration flush must not mark response_emitted"

    @pytest.mark.asyncio
    async def test_terminal_fc_flushes_accumulated_text_as_response(self):
        """defer_event IS in _CYCLE_ENDING_TOOLS -- preceding accumulated_text
        is the final answer and must flush as a 'response' turn."""
        chunk = _Chunk(text="I'll defer this while CI runs.",
                       function_call=SimpleNamespace(name="defer_event", args={"reason": "CI running"}))
        stream = MockStream([chunk])
        brain = _make_brain(stream_factory=lambda **kw: stream)
        event = _make_event()

        with _gate_patch(["defer_event"]), _gate_ctx_patch():
            await brain._process_with_llm("evt-test", event)

        turns = _turns(brain)
        assert turns, "expected at least the response turn + defer_event's own turn"
        response = turns[0]
        assert response.action == "response", f"terminal FC text flush should be a response turn, got {response.action!r}"
        assert response.thoughts == "I'll defer this while CI runs."
        assert "evt-test" in brain._response_emitted_for

    @pytest.mark.asyncio
    async def test_single_fc_set_phase_close_flushes_accumulated_text_as_response(self):
        """T-5: set_phase(phase='close') on an admissible (clear) event flushes
        accumulated_text as 'response' and arms _response_emitted_for."""
        chunk = _Chunk(
            text="Closing out the thread — talk soon!",
            function_call=SimpleNamespace(name="set_phase", args={"phase": "close"}),
        )
        stream = MockStream([chunk])
        brain = _make_brain(stream_factory=lambda **kw: stream)
        event = _make_event(source="slack")
        event.event.evidence.domain = "clear"
        event.event.evidence.brain_domain = "clear"
        brain.blackboard.get_event = AsyncMock(return_value=event)

        with _gate_patch(["set_phase"]), _gate_ctx_patch():
            should_continue = await brain._process_with_llm("evt-test", event)

        assert should_continue is True
        turns = _turns(brain)
        assert turns, "expected at least the response turn + set_phase's own turn"
        response = turns[0]
        assert response.action == "response", (
            f"admissible set_phase(close) text flush should be a response turn, got {response.action!r}"
        )
        assert response.thoughts == "Closing out the thread — talk soon!"
        assert "evt-test" in brain._response_emitted_for


# ---------------------------------------------------------------------------
# evt-996e33ec Batch D2: RECALL gate never blocks a batch containing classify_event
# ---------------------------------------------------------------------------

class TestBatchReflexExempt:

    @pytest.mark.asyncio
    async def test_batch_with_exempt_fc_skips_reflex_gate(self):
        """D2-T3: [classify_event, set_phase] with lessons available -> RECALL must not
        return True for the batch; classify_event executes and the gate stays armed."""
        fcs = [_fc("classify_event", {"domain": "clear"}), _fc("set_phase", {"phase": "dispatch"})]
        stream = MockStream([_Chunk(raw_parts=fcs)])
        brain = _make_brain(stream_factory=lambda **kw: stream)
        event = _make_event()

        searcher = MagicMock()
        searcher.gather = AsyncMock(return_value=[{"payload": {"title": "past incident"}, "score": 0.91}])
        searcher.fire = MagicMock()
        chunker = MagicMock()
        chunker.feed = MagicMock(return_value=None)
        chunker.flush = MagicMock(return_value=None)
        brain._create_reflex_pair = MagicMock(return_value=(chunker, searcher))

        with patch("src.agents.brain._THOUGHT_SIG_V2", True), \
                _gate_patch(["classify_event", "set_phase"]), _gate_ctx_patch():
            await brain._process_with_llm("evt-test", event)

        brain.blackboard.update_event_domain.assert_awaited_once()
        assert "evt-test" not in brain._reflex_fired_for
        assert "evt-test" not in brain._recall_lessons
        searcher.gather.assert_not_awaited()

    @staticmethod
    def _reflex_brain(fcs):
        stream = MockStream([_Chunk(raw_parts=fcs)])
        brain = _make_brain(stream_factory=lambda **kw: stream)
        searcher = MagicMock()
        searcher.gather = AsyncMock(return_value=[{"payload": {"title": "past incident"}, "score": 0.91}])
        searcher.fire = MagicMock()
        chunker = MagicMock()
        chunker.feed = MagicMock(return_value=None)
        chunker.flush = MagicMock(return_value=None)
        brain._create_reflex_pair = MagicMock(return_value=(chunker, searcher))
        return brain, searcher

    @pytest.mark.asyncio
    async def test_batch_with_exempt_fc_in_non_first_position_skips_reflex_gate(self):
        """D2-T4: the exemption is batch-wide -- [set_phase, classify_event] (exempt FC NOT
        first) must not arm/trigger the RECALL gate either."""
        fcs = [_fc("set_phase", {"phase": "dispatch"}), _fc("classify_event", {"domain": "clear"})]
        brain, searcher = self._reflex_brain(fcs)

        with patch("src.agents.brain._THOUGHT_SIG_V2", True), \
                _gate_patch(["set_phase", "classify_event"]), _gate_ctx_patch():
            await brain._process_with_llm("evt-test", _make_event())

        brain.blackboard.update_event_domain.assert_awaited_once()
        assert "evt-test" not in brain._reflex_fired_for
        assert "evt-test" not in brain._recall_lessons
        searcher.gather.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_batch_without_exempt_fc_still_hits_reflex_gate(self):
        """D2-T5 (negative control): a batch with NO exempt FC and lessons available is
        blocked by RECALL (returns True, lessons stored, nothing executed). Proves the
        exempt tests above are not passing because the gate is simply inert."""
        fcs = [_fc("set_phase", {"phase": "dispatch"}), _fc("set_phase", {"phase": "triage"})]
        brain, searcher = self._reflex_brain(fcs)

        with patch("src.agents.brain._THOUGHT_SIG_V2", True), \
                _gate_patch(["set_phase"]), _gate_ctx_patch():
            should_continue = await brain._process_with_llm("evt-test", _make_event())

        assert should_continue is True
        searcher.gather.assert_awaited_once()
        assert "evt-test" in brain._reflex_fired_for
        assert brain._recall_lessons["evt-test"][0]["payload"]["title"] == "past incident"
        brain.blackboard.update_event_domain.assert_not_awaited()


# ---------------------------------------------------------------------------
# VMER-2391 (T-10 & T-12): Parallel FC batch close-phase flush & continuation
# ---------------------------------------------------------------------------

def _wire_mutable_event(brain: Brain, event: EventDocument) -> None:
    """Wire bb.get_event, update_event_domain, update_event_phase,
    _extract_context_flags, and brain._append_and_broadcast to mutate and
    reflect the live EventDocument in place."""
    brain.blackboard.get_event = AsyncMock(side_effect=lambda _eid: event)

    async def _set_domain(_eid: str, domain: str):
        event.event.evidence.domain = domain
        event.event.evidence.brain_domain = domain

    async def _set_phase(_eid: str, phase: str):
        event.brain_phase = phase

    async def _append_turn(_eid: str, turn, _event=None):
        turn.turn = len(event.conversation) + 1
        event.conversation.append(turn)
        return turn.turn

    async def _extract_flags(_ev, **_kwargs):
        ev_evidence = _ev.event.evidence
        return {
            "event_domain": ev_evidence.brain_domain or ev_evidence.domain,
            "domain_confidence": ev_evidence.domain_confidence,
            "brain_has_classified": ev_evidence.brain_domain is not None,
        }

    brain.blackboard.update_event_domain = AsyncMock(side_effect=_set_domain)
    brain.blackboard.update_event_phase = AsyncMock(side_effect=_set_phase)
    brain._append_and_broadcast = AsyncMock(side_effect=_append_turn)
    brain._extract_context_flags = AsyncMock(side_effect=_extract_flags)


class TestBatchClosePhaseFlush:
    """T-10 & T-12: Parallel batch close-phase response flush, order-aware verify guard,
    wait_for_user fast-match retention, and global continuation for completed batches."""

    @pytest.mark.asyncio
    async def test_batch_classify_clear_and_set_phase_close_flushes_response_and_continues(self):
        """T-10: [classify_event('clear'), set_phase('close')] + text with dynamic bb.get_event
        flushes pre-batch text as action='response', arms _response_emitted_for, and returns True."""
        fcs = [
            _fc("classify_event", {"domain": "clear"}),
            _fc("set_phase", {"phase": "close"}),
        ]
        stream = MockStream([_Chunk(text="Will do — talk soon!", raw_parts=fcs)])
        brain = _make_brain(stream_factory=lambda **kw: stream)
        event = _make_event(source="slack", brain_phase="triage")
        event.event.evidence.domain = "casual"
        event.event.evidence.brain_domain = "casual"
        _wire_mutable_event(brain, event)

        with patch("src.agents.brain._THOUGHT_SIG_V2", True):
            should_continue = await brain._process_with_llm("evt-test", event)

        turns = _turns(brain)
        assert turns[0].action == "response"
        assert turns[0].thoughts == "Will do — talk soon!"
        assert "evt-test" in brain._response_emitted_for
        assert event.event.evidence.brain_domain == "clear"
        assert event.brain_phase == "close"
        assert should_continue is True

    @pytest.mark.asyncio
    async def test_batch_classify_complicated_and_set_phase_close_keeps_thoughts(self):
        """T-10: downward/unverified [classify_event('complicated'), set_phase('close')] + text
        keeps pre-batch text as action='thoughts', does not arm _response_emitted_for,
        and handle_set_phase rejects the close transition."""
        fcs = [
            _fc("classify_event", {"domain": "complicated"}),
            _fc("set_phase", {"phase": "close"}),
        ]
        stream = MockStream([_Chunk(text="Premature close text.", raw_parts=fcs)])
        brain = _make_brain(stream_factory=lambda **kw: stream)
        event = _make_event(source="slack", brain_phase="triage")
        event.event.evidence.domain = "clear"
        event.event.evidence.brain_domain = "clear"
        _wire_mutable_event(brain, event)

        with patch("src.agents.brain._THOUGHT_SIG_V2", True):
            await brain._process_with_llm("evt-test", event)

        turns = _turns(brain)
        assert turns[0].action == "thoughts"
        assert turns[0].thoughts == "Premature close text."
        assert "evt-test" not in brain._response_emitted_for
        assert any(
            t.actor == "brain" and t.action == "tool_result" and t.waitingFor == "set_phase"
            and "Cannot transition to 'close'" in (t.thoughts or "")
            for t in turns
        )
        assert event.brain_phase != "close"

    @pytest.mark.asyncio
    async def test_batch_wrong_order_set_phase_close_then_classify_clear_complicated_safe(self):
        """T-10: wrong-order [set_phase('close'), classify_event('clear')] on unverified
        complicated flushes text as 'thoughts', rejects set_phase, classifies to 'clear',
        and does not arm _response_emitted_for."""
        fcs = [
            _fc("set_phase", {"phase": "close"}),
            _fc("classify_event", {"domain": "clear"}),
        ]
        stream = MockStream([_Chunk(text="Wrong order text.", raw_parts=fcs)])
        brain = _make_brain(stream_factory=lambda **kw: stream)
        event = _make_event(source="slack", brain_phase="dispatch")
        event.event.evidence.domain = "complicated"
        event.event.evidence.brain_domain = "complicated"
        _wire_mutable_event(brain, event)

        with patch("src.agents.brain._THOUGHT_SIG_V2", True):
            should_continue = await brain._process_with_llm("evt-test", event)

        assert should_continue is True
        turns = _turns(brain)
        assert turns[0].action == "thoughts"
        assert turns[0].thoughts == "Wrong order text."
        assert "evt-test" not in brain._response_emitted_for
        assert any(
            t.actor == "brain" and t.action == "tool_result" and t.waitingFor == "set_phase"
            and "Cannot transition to 'close'" in (t.thoughts or "")
            for t in turns
        )
        assert event.event.evidence.brain_domain == "clear"
        assert event.brain_phase == "dispatch"

    @pytest.mark.asyncio
    async def test_batch_classify_and_wait_for_user_retains_response_flush(self):
        """T-10: [classify_event('clear'), wait_for_user] for chat/slack flushes pre-batch
        text as action='response' (satisfying SILENT_PARK for FC[1]) and returns False."""
        from src.models import ConversationTurn

        fcs = [
            _fc("classify_event", {"domain": "clear"}),
            _fc("wait_for_user", {"summary": "waiting for user reply"}),
        ]
        stream = MockStream([_Chunk(text="Hello! How can I help?", raw_parts=fcs)])
        brain = _make_brain(stream_factory=lambda **kw: stream)
        event = _make_event(source="slack", brain_phase="triage")
        event.conversation = [
            ConversationTurn(turn=1, actor="user", action="message", thoughts="Morning!"),
        ]
        _wire_mutable_event(brain, event)

        with patch("src.agents.brain._THOUGHT_SIG_V2", True):
            should_continue = await brain._process_with_llm("evt-test", event)

        assert should_continue is False
        turns = _turns(brain)
        assert turns[0].action == "response"
        assert turns[0].thoughts == "Hello! How can I help?"
        assert "evt-test" in brain._response_emitted_for
        assert any(t.action == "wait" and t.waitingFor == "user" for t in turns)

    @pytest.mark.asyncio
    async def test_batch_preparatory_non_close_returns_true_to_continue(self):
        """T-12: [classify_event('clear'), set_phase('dispatch')] completing without break
        returns True (confirming L2703 global continuation for preparatory batches)."""
        fcs = [
            _fc("classify_event", {"domain": "clear"}),
            _fc("set_phase", {"phase": "dispatch"}),
        ]
        stream = MockStream([_Chunk(text="Classifying and moving to dispatch.", raw_parts=fcs)])
        brain = _make_brain(stream_factory=lambda **kw: stream)
        event = _make_event(source="slack", brain_phase="triage")
        _wire_mutable_event(brain, event)

        with patch("src.agents.brain._THOUGHT_SIG_V2", True):
            should_continue = await brain._process_with_llm("evt-test", event)

        assert should_continue is True
        turns = _turns(brain)
        assert turns[0].action == "thoughts"
        assert "evt-test" not in brain._response_emitted_for
        assert event.event.evidence.brain_domain == "clear"
        assert event.brain_phase == "dispatch"

    @pytest.mark.asyncio
    async def test_batch_3fc_casual_to_clear_set_phase_close_and_close_event_succeeds(self):
        """CF-1: starting from domain='casual', brain_domain='casual' on a slack event,
        a 3-FC batch [classify_event('clear'), set_phase('close'), close_event] flushes
        pre-batch text as action='response', updates domain to 'clear' and phase to 'close',
        and executes close_event (FC[2]) without DOMAIN_CASUAL rejecting it."""
        fcs = [
            _fc("classify_event", {"domain": "clear"}),
            _fc("set_phase", {"phase": "close"}),
            _fc("close_event", {"summary": "done"}),
        ]
        stream = MockStream([_Chunk(text="Glad that helped — closing out!", raw_parts=fcs)])
        brain = _make_brain(stream_factory=lambda **kw: stream)
        event = _make_event(source="slack", brain_phase="triage")
        event.event.evidence.domain = "casual"
        event.event.evidence.brain_domain = "casual"
        _wire_mutable_event(brain, event)
        brain.blackboard.close_event = AsyncMock(return_value=True)
        brain._close_and_broadcast = AsyncMock()

        with patch("src.agents.brain._THOUGHT_SIG_V2", True):
            should_continue = await brain._process_with_llm("evt-test", event)

        assert should_continue is False
        turns = _turns(brain)
        assert turns[0].action == "response"
        assert turns[0].thoughts == "Glad that helped — closing out!"
        assert "evt-test" in brain._response_emitted_for
        assert event.event.evidence.brain_domain == "clear"
        assert event.brain_phase == "close"
        brain._close_and_broadcast.assert_awaited_once_with("evt-test", "done", close_reason=None)

    @pytest.mark.asyncio
    async def test_batch_reclassify_to_casual_gates_subsequent_fc(self):
        """CF-1 & CF-2: starting from domain='complicated', brain_domain='complicated' on a slack
        event, batch [classify_event('casual'), set_phase('close')] with text keeps pre-batch text
        as action='thoughts' and does not arm _response_emitted_for; and a subsequent non-casual FC
        (e.g. fetch_jira_issue) in a casual reclassification batch is rejected by refreshed DOMAIN_CASUAL."""
        fcs = [
            _fc("classify_event", {"domain": "casual"}),
            _fc("set_phase", {"phase": "close"}),
        ]
        stream = MockStream([_Chunk(text="Switching to casual.", raw_parts=fcs)])
        brain = _make_brain(stream_factory=lambda **kw: stream)
        event = _make_event(source="slack", brain_phase="dispatch")
        event.event.evidence.domain = "complicated"
        event.event.evidence.brain_domain = "complicated"
        _wire_mutable_event(brain, event)

        with patch("src.agents.brain._THOUGHT_SIG_V2", True):
            await brain._process_with_llm("evt-test", event)

        turns = _turns(brain)
        assert turns[0].action == "thoughts"
        assert turns[0].thoughts == "Switching to casual."
        assert "evt-test" not in brain._response_emitted_for
        assert event.event.evidence.brain_domain == "casual"

        # Also verify FC[1] gate rejection when FC[0] reclassifies to casual and FC[1] is a tool
        # disallowed by DOMAIN_CASUAL (e.g. fetch_jira_issue).
        fcs_gated = [
            _fc("classify_event", {"domain": "casual"}),
            _fc("fetch_jira_issue", {"issue_key": "VMER-1"}),
        ]
        stream2 = MockStream([_Chunk(text="Checking Jira.", raw_parts=fcs_gated)])
        brain2 = _make_brain(stream_factory=lambda **kw: stream2)
        event2 = _make_event(source="slack", brain_phase="triage")
        event2.event.evidence.domain = "complicated"
        event2.event.evidence.brain_domain = "complicated"
        _wire_mutable_event(brain2, event2)

        with patch("src.agents.brain._THOUGHT_SIG_V2", True):
            res2 = await brain2._process_with_llm("evt-test", event2)

        assert res2 is True
        assert event2.event.evidence.brain_domain == "casual"
        turns2 = _turns(brain2)
        assert len(turns2) == 4  # 1 thoughts + 2 classify_event + 1 [GATE] rejection for fetch_jira_issue
        assert turns2[-1].actor == "brain"
        assert turns2[-1].action == "tool_result"
        assert turns2[-1].waitingFor == "fetch_jira_issue"
        assert turns2[-1].batch_index == 1
        assert (turns2[-1].thoughts or "").startswith("[GATE] ")

    def test_batch_intra_batch_ordering_and_default_domain_guards(self):
        """CF-2 & CF-3: _batch_is_terminal_for_flush returns False for default complicated
        domain, non-close phase transitions after verify, non-user casual rejection, and
        set_phase('close') followed by set_phase('dispatch')."""
        from src.agents.brain import _batch_is_terminal_for_flush
        from src.models import ConversationTurn

        active = {"classify_event", "set_phase"}

        # 1) [classify_event({}), set_phase('close')] on a clear event (omitted domain -> complicated)
        clear_event = _make_event(source="slack", brain_phase="dispatch")
        clear_event.event.evidence.domain = "clear"
        clear_event.event.evidence.brain_domain = "clear"
        assert _batch_is_terminal_for_flush(
            [_fc("classify_event", {}), _fc("set_phase", {"phase": "close"})],
            clear_event,
            active,
        ) is False

        # 2) [set_phase('dispatch'), set_phase('close')] on a verified complicated event
        verified_event = _make_event(source="slack", brain_phase="verify")
        verified_event.event.evidence.domain = "complicated"
        verified_event.event.evidence.brain_domain = "complicated"
        verified_event.conversation = [
            ConversationTurn(
                turn=1, actor="brain", action="phase",
                thoughts="Phase: VERIFY", waitingFor="set_phase",
            ),
        ]
        assert _batch_is_terminal_for_flush(
            [_fc("set_phase", {"phase": "dispatch"}), _fc("set_phase", {"phase": "close"})],
            verified_event,
            active,
        ) is False

        # 3) [classify_event('casual'), set_phase('close')] on a verified complicated aligner event
        verified_aligner = _make_event(source="aligner", brain_phase="verify")
        verified_aligner.event.evidence.domain = "complicated"
        verified_aligner.event.evidence.brain_domain = "complicated"
        verified_aligner.conversation = [
            ConversationTurn(
                turn=1, actor="brain", action="phase",
                thoughts="Phase: VERIFY", waitingFor="set_phase",
            ),
        ]
        assert _batch_is_terminal_for_flush(
            [_fc("classify_event", {"domain": "casual"}), _fc("set_phase", {"phase": "close"})],
            verified_aligner,
            active,
        ) is False

        # 4) [set_phase('close'), set_phase('dispatch')] on a clear event
        assert _batch_is_terminal_for_flush(
            [_fc("set_phase", {"phase": "close"}), _fc("set_phase", {"phase": "dispatch"})],
            clear_event,
            active,
        ) is False


class TestBatchFC0WaitForUserReadmission:
    """M5 & Step 5: FC[0] `wait_for_user` re-admission after a response was already emitted
    (SILENT_PARK) is governed by `is_wait_for_user_admissible_after_response(gate_ctx)`."""

    @staticmethod
    def _readmission_brain(source: str, phase: str, with_user_turn: bool):
        gate_ctx = _default_gate_ctx(
            event_source=source,
            brain_phase=phase,
            conversation=[{"actor": "user", "action": "message"}] if with_user_turn else [],
        )
        fcs = [_fc("wait_for_user", {"summary": "waiting"}), _fc("classify_event", {"domain": "clear"})]
        stream = MockStream([_Chunk(raw_parts=fcs)])
        brain = _make_brain(stream_factory=lambda **kw: stream)
        brain._response_emitted_for = {"evt-test"}
        # Falsy result halts the batch right after FC[0]; we only observe admission.
        brain._execute_function_call = AsyncMock(return_value=False)
        return brain, _make_event(source=source, brain_phase=phase), gate_ctx

    @pytest.mark.asyncio
    @pytest.mark.parametrize("source", ["slack", "chat"])
    async def test_fc0_wait_for_user_readmitted_on_user_facing_source_after_response(self, source):
        brain, event, gate_ctx = self._readmission_brain(source, "triage", with_user_turn=True)

        with patch("src.agents.brain._THOUGHT_SIG_V2", True), \
                _gate_patch(["classify_event"]), _gate_ctx_patch(return_value=gate_ctx):
            await brain._process_with_llm("evt-test", event)

        brain._execute_function_call.assert_awaited_once()
        assert brain._execute_function_call.await_args.args[1] == "wait_for_user"

    @pytest.mark.asyncio
    @pytest.mark.parametrize("source", ["headhunter", "aligner"])
    async def test_fc0_wait_for_user_not_readmitted_on_non_user_source_after_response(self, source):
        brain, event, gate_ctx = self._readmission_brain(source, "triage", with_user_turn=False)

        with patch("src.agents.brain._THOUGHT_SIG_V2", True), \
                _gate_patch(["classify_event"]), _gate_ctx_patch(return_value=gate_ctx):
            result = await brain._process_with_llm("evt-test", event)

        assert result is True
        brain._execute_function_call.assert_not_awaited()
        turns = _turns(brain)
        assert len(turns) == 2
        assert turns[0].turn == 0
        assert turns[0].waitingFor == "wait_for_user"
        assert turns[0].batch_size == 2
        assert (turns[0].thoughts or "").startswith("[GATE] ")
        assert turns[1].turn == 0
        assert turns[1].waitingFor == "classify_event"
        assert turns[1].batch_index == 1
        assert "[GATE] Skipped" in (turns[1].thoughts or "")


class TestBatchGateReEvalUsesLiveEvidence:
    """M6: the FC[1+] gate re-evaluation must take domain flags from live EventEvidence
    (`evidence_overrides`), not from the stale pre-batch `context_flags`."""

    @pytest.mark.asyncio
    async def test_fc1_gate_sees_post_classify_domain_despite_stale_context_flags(self):
        fcs = [
            _fc("classify_event", {"domain": "casual"}),
            _fc("fetch_jira_issue", {"issue_key": "VMER-1"}),
        ]
        stream = MockStream([_Chunk(text="Checking Jira.", raw_parts=fcs)])
        brain = _make_brain(stream_factory=lambda **kw: stream)
        event = _make_event(source="slack", brain_phase="triage")
        event.event.evidence.domain = "complicated"
        event.event.evidence.brain_domain = "complicated"
        _wire_mutable_event(brain, event)
        # Pin flags to the stale pre-batch domain; only live evidence can supply "casual".
        brain._extract_context_flags = AsyncMock(
            return_value={"event_domain": "complicated", "brain_has_classified": True}
        )

        from src.agents.tool_gates import build_gate_context as real_build

        seen_flags: list[dict] = []

        def _spy(**kwargs):
            seen_flags.append(dict(kwargs["context_flags"]))
            return real_build(**kwargs)

        with patch("src.agents.brain._THOUGHT_SIG_V2", True), \
                patch("src.agents.tool_gates.build_gate_context", side_effect=_spy):
            result = await brain._process_with_llm("evt-test", event)

        assert result is True
        assert event.event.evidence.brain_domain == "casual"
        assert len(seen_flags) >= 2
        assert seen_flags[0]["event_domain"] == "complicated"
        assert seen_flags[-1]["event_domain"] == "casual", (
            "FC[1] gate re-eval must use refreshed evidence_overrides, not stale context_flags"
        )
        # fetch_jira_issue is disallowed under DOMAIN_CASUAL -> rejected with paired [GATE] FR turn
        rejected_turns = [
            t for t in _turns(brain)
            if t.actor == "brain" and t.action == "tool_result" and t.waitingFor == "fetch_jira_issue"
        ]
        assert len(rejected_turns) == 1
        assert rejected_turns[0].batch_index == 1
        assert (rejected_turns[0].thoughts or "").startswith("[GATE] ")
        assert "[GATE] [GATE]" not in (rejected_turns[0].thoughts or "")
        assert "CASUAL" in (rejected_turns[0].thoughts or "")


class TestBatchGateReEvalClassifiedFlag:
    """brain_has_classified at FC[1+] must come from live evidence (brain_domain set by FC[0] classify_event)."""

    @pytest.mark.asyncio
    async def test_fc1_gate_sees_classified_after_fc0_classify_despite_stale_flag(self):
        fcs = [
            _fc("classify_event", {"domain": "complicated"}),
            _fc("fetch_jira_issue", {"issue_key": "VMER-1"}),
        ]
        stream = MockStream([_Chunk(text="Checking Jira.", raw_parts=fcs)])
        brain = _make_brain(stream_factory=lambda **kw: stream)
        event = _make_event(source="slack", brain_phase="triage")
        event.event.evidence.domain = None
        event.event.evidence.brain_domain = None
        _wire_mutable_event(brain, event)
        brain._extract_context_flags = AsyncMock(
            return_value={"event_domain": "complicated", "brain_has_classified": False}
        )

        async def _exec(_eid, name, _args, **_kw):
            if name == "classify_event":
                event.event.evidence.domain = "complicated"
                event.event.evidence.brain_domain = "complicated"
            return True

        brain._execute_function_call = AsyncMock(side_effect=_exec)

        from src.agents.tool_gates import build_gate_context as real_build

        seen_flags: list[dict] = []

        def _spy(**kwargs):
            seen_flags.append(dict(kwargs["context_flags"]))
            return real_build(**kwargs)

        with patch("src.agents.brain._THOUGHT_SIG_V2", True), \
                patch("src.agents.tool_gates.build_gate_context", side_effect=_spy):
            await brain._process_with_llm("evt-test", event)

        assert seen_flags[0]["brain_has_classified"] is False
        assert seen_flags[-1]["brain_has_classified"] is True
        assert [c.args[1] for c in brain._execute_function_call.await_args_list] == [
            "classify_event", "fetch_jira_issue",
        ]


# ---------------------------------------------------------------------------
# VMER-2450 Step 5 ATDD (T-14, T-15, T-16, T-17): Batch 1:1 FR parity,
# single [GATE] prefix, skipped-turn batch_index preservation, return value
# semantics, SILENT_PARK full-gate guard, and set_phase rejection replay
# ---------------------------------------------------------------------------

def _fc_sig(name: str, args: dict | None = None, sig: str | None = None) -> dict:
    part: dict = {"functionCall": {"name": name, "args": args or {}}}
    if sig is not None:
        part["thought_signature"] = sig
    return part


class TestATDDT14T15BatchGateAndExceptionParity:
    """Layer 1-4 ATDD specs for T-14 & T-15 (Step 5 batch FR parity)."""

    @pytest.mark.asyncio
    async def test_t14_2fc_batch_allowed_then_gated_single_prefix_fr_parity_and_replay(self):
        """T-14: Given [lookup_service (allowed), close_event (gated)] under BRAIN_THOUGHT_SIG_V2=true
        When executed
        Then FC[0] executes, FC[1] writes single-prefixed '[GATE] ' tool_result (turn=0,
        batch_index=1, waitingFor='close_event'), returns True, and native replay pairs 2 FCs with 2 FRs."""
        from tests.test_build_contents_structure import _make_brain_mock

        fcs = [
            _fc_sig("lookup_service", {"service": "test-svc"}, sig="sig-t14"),
            _fc_sig("close_event", {"summary": "premature"}),
        ]
        stream = MockStream([_Chunk(raw_parts=fcs)])
        brain = _make_brain(stream_factory=lambda **kw: stream)
        event = _make_event(source="headhunter", brain_phase="dispatch")
        event.event.evidence.brain_domain = "complicated"
        brain.blackboard.get_event = AsyncMock(return_value=event)
        brain._extract_context_flags = AsyncMock(
            return_value={"brain_has_classified": True, "event_domain": "complicated"}
        )

        # Capture raw turn.turn before persisting to event.conversation for replay verification
        initial_turns: list[int] = []

        async def _capture_and_store(_eid, turn, _ev=None):
            initial_turns.append(turn.turn)
            turn.turn = len(event.conversation) + 1
            event.conversation.append(turn)
            return turn.turn

        brain._append_and_broadcast = AsyncMock(side_effect=_capture_and_store)

        with patch("src.agents.brain._THOUGHT_SIG_V2", True):
            result = await brain._process_with_llm("evt-test", event)

        assert result is True
        brain.blackboard.get_service.assert_awaited_once()
        assert len(event.conversation) == 2
        fc0_turn, fc1_turn = event.conversation
        assert fc0_turn.waitingFor == "lookup_service"
        assert fc0_turn.batch_size == 2
        assert fc0_turn.response_parts == fcs

        assert initial_turns[1] == 0, "FC[1] gate rejection turn must be constructed with turn=0"
        assert fc1_turn.actor == "brain"
        assert fc1_turn.action == "tool_result"
        assert fc1_turn.waitingFor == "close_event"
        assert fc1_turn.batch_index == 1
        assert fc1_turn.response_parts is None
        assert (fc1_turn.thoughts or "").startswith("[GATE] ")
        assert "[GATE] [GATE]" not in (fc1_turn.thoughts or "")

        # Verify native FC/FR replay parity + verbatim thought_signature
        with patch("src.agents.brain._THOUGHT_SIG_V2", True):
            contents = await Brain._build_contents(_make_brain_mock(), event)
        fc_parts = [p for m in contents if m["role"] == "model" for p in m["parts"] if "functionCall" in p]
        fr_parts = [p for m in contents if m["role"] == "user" for p in m["parts"] if "functionResponse" in p]
        assert len(fc_parts) == 2
        assert len(fr_parts) == 2
        assert fc_parts[0].get("thought_signature") == "sig-t14"
        assert [p["functionResponse"]["name"] for p in fr_parts] == ["lookup_service", "close_event"]

    @pytest.mark.asyncio
    async def test_t14_unknown_tool_in_batch_writes_unknown_prefix_tool_result(self):
        """Unknown tool name in batch writes [UNKNOWN] tool_result (turn=0, batch_index=1) and returns True."""
        fcs = [
            _fc_sig("lookup_service", {"service": "test-svc"}, sig="sig-unk"),
            _fc_sig("nonexistent_tool", {}),
        ]
        stream = MockStream([_Chunk(raw_parts=fcs)])
        brain = _make_brain(stream_factory=lambda **kw: stream)
        event = _make_event(source="headhunter", brain_phase="dispatch")
        event.event.evidence.brain_domain = "complicated"
        brain.blackboard.get_event = AsyncMock(return_value=event)
        brain._extract_context_flags = AsyncMock(
            return_value={"brain_has_classified": True, "event_domain": "complicated"}
        )

        with patch("src.agents.brain._THOUGHT_SIG_V2", True):
            result = await brain._process_with_llm("evt-test", event)

        assert result is True
        turns = _turns(brain)
        assert len(turns) == 2
        unk = turns[1]
        assert unk.turn == 0
        assert unk.actor == "brain"
        assert unk.action == "tool_result"
        assert unk.waitingFor == "nonexistent_tool"
        assert unk.batch_index == 1
        assert "[UNKNOWN]" in (unk.thoughts or "")

    @pytest.mark.asyncio
    async def test_t15_3fc_batch_fc0_gated_writes_paired_gate_and_skipped_turns(self):
        """T-15 (gate rejection at i=0): 3-FC batch [close_event (gated), lookup_service, select_agent]
        writes FC[0] [GATE] turn (batch_size=3, response_parts) plus FC[1] (batch_index=1) and
        FC[2] (batch_index=2) [GATE] Skipped turns with turn=0 and un-clobbered batch_index."""
        from tests.test_build_contents_structure import _make_brain_mock

        fcs = [
            _fc_sig("close_event", {"summary": "nope"}, sig="sig-t15-0"),
            _fc_sig("lookup_service", {"service": "test-svc"}),
            _fc_sig("select_agent", {"agent_name": "developer"}),
        ]
        stream = MockStream([_Chunk(raw_parts=fcs)])
        brain = _make_brain(stream_factory=lambda **kw: stream)
        event = _make_event(source="headhunter", brain_phase="dispatch")
        event.event.evidence.brain_domain = "complicated"
        brain.blackboard.get_event = AsyncMock(return_value=event)
        brain._extract_context_flags = AsyncMock(
            return_value={"brain_has_classified": True, "event_domain": "complicated"}
        )

        initial_turns: list[int] = []

        async def _capture_and_store(_eid, turn, _ev=None):
            initial_turns.append(turn.turn)
            turn.turn = len(event.conversation) + 1
            event.conversation.append(turn)
            return turn.turn

        brain._append_and_broadcast = AsyncMock(side_effect=_capture_and_store)

        with patch("src.agents.brain._THOUGHT_SIG_V2", True):
            result = await brain._process_with_llm("evt-test", event)

        assert result is True
        brain.blackboard.get_service.assert_not_awaited()
        assert initial_turns == [0, 0, 0]
        assert len(event.conversation) == 3

        t0, t1, t2 = event.conversation
        assert t0.actor == "brain" and t0.action == "tool_result" and t0.waitingFor == "close_event"
        assert t0.batch_size == 3 and t0.batch_index is None
        assert t0.response_parts == fcs
        assert (t0.thoughts or "").startswith("[GATE] ")
        assert "[GATE] [GATE]" not in (t0.thoughts or "")

        assert t1.actor == "brain" and t1.action == "tool_result" and t1.waitingFor == "lookup_service"
        assert t1.batch_index == 1 and t1.batch_size is None
        assert "[GATE] Skipped" in (t1.thoughts or "") and "close_event" in (t1.thoughts or "")

        assert t2.actor == "brain" and t2.action == "tool_result" and t2.waitingFor == "select_agent"
        assert t2.batch_index == 2 and t2.batch_size is None
        assert "[GATE] Skipped" in (t2.thoughts or "") and "close_event" in (t2.thoughts or "")

        with patch("src.agents.brain._THOUGHT_SIG_V2", True):
            contents = await Brain._build_contents(_make_brain_mock(), event)
        fc_parts = [p for m in contents if m["role"] == "model" for p in m["parts"] if "functionCall" in p]
        fr_parts = [p for m in contents if m["role"] == "user" for p in m["parts"] if "functionResponse" in p]
        assert len(fc_parts) == 3
        assert len(fr_parts) == 3
        assert fc_parts[0].get("thought_signature") == "sig-t15-0"
        assert [p["functionResponse"]["name"] for p in fr_parts] == [
            "close_event", "lookup_service", "select_agent",
        ]

    @pytest.mark.asyncio
    async def test_t15_3fc_batch_exception_at_fc1_writes_error_and_skipped_turn(self):
        """T-15 (re-eval exception at i=1): FC[0] runs, FC[1] raises during gate re-eval ->
        FC[1] writes tool_result (turn=0, batch_index=1) AND FC[2] writes [GATE] Skipped
        (turn=0, batch_index=2, waitingFor='close_event'); returns True."""
        fcs = [
            _fc_sig("lookup_service", {"service": "test-svc"}, sig="sig-exc"),
            _fc_sig("select_agent", {"agent_name": "developer"}),
            _fc_sig("close_event", {"summary": "skipped"}),
        ]
        stream = MockStream([_Chunk(raw_parts=fcs)])
        brain = _make_brain(stream_factory=lambda **kw: stream)
        event = _make_event()

        with patch("src.agents.brain._THOUGHT_SIG_V2", True), \
                _gate_patch(["lookup_service", "select_agent", "close_event"]), \
                patch("src.agents.tool_gates.build_gate_context") as mock_ctx:
            mock_ctx.side_effect = [_default_gate_ctx(), RuntimeError("transient redis drop")]
            result = await brain._process_with_llm("evt-test", event)

        assert result is True
        turns = _turns(brain)
        assert len(turns) == 3
        assert turns[0].waitingFor == "lookup_service" and turns[0].batch_size == 3
        assert turns[1].turn == 0 and turns[1].waitingFor == "select_agent" and turns[1].batch_index == 1
        assert "transient redis drop" in (turns[1].thoughts or "")
        assert turns[2].turn == 0 and turns[2].waitingFor == "close_event" and turns[2].batch_index == 2
        assert "[GATE] Skipped" in (turns[2].thoughts or "") and "select_agent" in (turns[2].thoughts or "")

    @pytest.mark.asyncio
    async def test_t15_halt_returns_false_if_event_closed_before_fc1_rejection(self):
        """Return value contract: if FC[0] ran and event is closed by the time FC[1] is rejected,
        halt_reinvoke must NOT force True -- returns False."""
        fcs = [
            _fc_sig("lookup_service", {"service": "test-svc"}, sig="sig-closed"),
            _fc_sig("close_event", {"summary": "gated"}),
        ]
        stream = MockStream([_Chunk(raw_parts=fcs)])
        brain = _make_brain(stream_factory=lambda **kw: stream)
        event = _make_event(source="headhunter", brain_phase="dispatch")
        event.event.evidence.brain_domain = "complicated"
        brain.blackboard.get_event = AsyncMock(return_value=event)
        brain._extract_context_flags = AsyncMock(
            return_value={"brain_has_classified": True, "event_domain": "complicated"}
        )
        # Pre-batch closed check=False, post-FC[0] closed check=False, halt_reinvoke closed check=True
        brain._is_event_closed = AsyncMock(side_effect=[False, False, True])

        with patch("src.agents.brain._THOUGHT_SIG_V2", True):
            result = await brain._process_with_llm("evt-test", event)

        assert result is False
        turns = _turns(brain)
        assert len(turns) == 2
        assert turns[1].waitingFor == "close_event" and turns[1].batch_index == 1


class TestATDDT16BatchFlushAndReadmission:
    """T-16 (Step 5): _batch_is_terminal_for_flush (L657) & batch FC[0] re-admission (L2790)."""

    def test_t16_batch_is_terminal_for_flush_backward_compat_and_gate_checks(self):
        """3-arg call (gate_ctx=None) stays backward-compatible while gating non-active
        _CYCLE_ENDING_TOOLS; 4-arg call with gate_ctx enforces is_wait_for_user_admissible_after_response."""
        from src.agents.brain import _batch_is_terminal_for_flush
        from src.models import ConversationTurn

        event = _make_event(source="slack", brain_phase="triage")
        event.event.evidence.brain_domain = "complicated"
        event.conversation = [
            ConversationTurn(turn=1, actor="user", action="message", thoughts="hi"),
        ]

        # 3-arg backward compat: gated close_event/defer_event NOT in active_tool_names -> False
        assert _batch_is_terminal_for_flush([_fc("close_event", {})], event, {"classify_event"}) is False
        assert _batch_is_terminal_for_flush([_fc("defer_event", {})], event, {"classify_event"}) is False
        # Active close_event -> True
        assert _batch_is_terminal_for_flush([_fc("close_event", {})], event, {"close_event"}) is True

        # 4-arg call: INTERMEDIATE blocks wait_for_user -> False
        interm_ctx = _default_gate_ctx(
            event_source="slack",
            brain_phase="dispatch",
            context_flags={"is_intermediate": True, "brain_has_classified": True, "event_domain": "complicated"},
            conversation=event.conversation,
        )
        assert _batch_is_terminal_for_flush(
            [_fc("wait_for_user", {})], event, {"wait_for_agent"}, gate_ctx=interm_ctx,
        ) is False

        # 4-arg call: DOMAIN_CHAOTIC blocks wait_for_user -> False
        chaotic_ctx = _default_gate_ctx(
            event_source="slack",
            brain_phase="dispatch",
            context_flags={"is_intermediate": False, "brain_has_classified": True, "event_domain": "chaotic"},
            conversation=event.conversation,
        )
        assert _batch_is_terminal_for_flush(
            [_fc("wait_for_user", {})], event, {"select_agent"}, gate_ctx=chaotic_ctx,
        ) is False

        # 4-arg call: ONLY SILENT_PARK firing -> True (flushing response satisfies SILENT_PARK)
        silent_park_only_ctx = _default_gate_ctx(
            event_source="slack",
            brain_phase="dispatch",
            context_flags={"is_intermediate": False, "brain_has_classified": True, "event_domain": "complicated"},
            conversation=event.conversation,
        )
        assert _batch_is_terminal_for_flush(
            [_fc("wait_for_user", {})], event, {"classify_event"}, gate_ctx=silent_park_only_ctx,
        ) is True

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "flags",
        [
            {"is_intermediate": True, "brain_has_classified": True, "event_domain": "complicated"},
            {"is_intermediate": False, "brain_has_classified": True, "event_domain": "chaotic"},
        ],
        ids=["intermediate", "domain_chaotic"],
    )
    async def test_t16_batch_wait_for_user_blocked_by_intermediate_or_chaotic_suppresses_flush_and_readmission(
        self, flags,
    ):
        """Even on slack source with narration + _response_emitted_for, INTERMEDIATE and DOMAIN_CHAOTIC
        must prevent both pre-batch response flush and FC[0] wait_for_user re-admission."""
        from src.models import ConversationTurn

        fcs = [_fc_sig("wait_for_user", {"summary": "park"}, sig="sig-t16"), _fc_sig("lookup_service", {})]
        stream = MockStream([_Chunk(text="Should NOT be flushed as brain.response.", raw_parts=fcs)])
        brain = _make_brain(stream_factory=lambda **kw: stream)
        event = _make_event(source="slack", brain_phase="dispatch")
        event.event.evidence.brain_domain = flags["event_domain"]
        event.conversation = [
            ConversationTurn(turn=1, actor="user", action="message", thoughts="status?"),
        ]
        brain.blackboard.get_event = AsyncMock(return_value=event)
        brain._extract_context_flags = AsyncMock(return_value=flags)
        brain._execute_function_call = AsyncMock(return_value=False)

        with patch("src.agents.brain._THOUGHT_SIG_V2", True):
            result = await brain._process_with_llm("evt-test", event)

        brain._execute_function_call.assert_not_awaited()
        assert result is True
        turns = _turns(brain)
        assert not any(t.action == "response" for t in turns), "Must not emit brain.response when wait_for_user is gated"
        assert "evt-test" not in brain._response_emitted_for
        assert turns[0].action == "thoughts"
        tool_results = [t for t in turns if t.action == "tool_result"]
        assert len(tool_results) == 2
        assert tool_results[0].waitingFor == "wait_for_user" and tool_results[0].batch_size == 2
        assert tool_results[1].waitingFor == "lookup_service" and tool_results[1].batch_index == 1

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "flags",
        [
            {"is_intermediate": True, "brain_has_classified": True, "event_domain": "complicated"},
            {"is_intermediate": False, "brain_has_classified": True, "event_domain": "chaotic"},
        ],
        ids=["intermediate_pre_emitted", "domain_chaotic_pre_emitted"],
    )
    async def test_t16_batch_fc0_readmission_blocked_even_when_response_already_emitted(self, flags):
        """Directly exercises L2790: even when _response_emitted_for already contains event_id
        on a slack event, INTERMEDIATE or DOMAIN_CHAOTIC blocks FC[0] wait_for_user re-admission."""
        from src.models import ConversationTurn

        fcs = [_fc_sig("wait_for_user", {"summary": "park"}, sig="sig-t16-re"), _fc_sig("lookup_service", {})]
        stream = MockStream([_Chunk(raw_parts=fcs)])
        brain = _make_brain(stream_factory=lambda **kw: stream)
        brain._response_emitted_for = {"evt-test"}
        event = _make_event(source="slack", brain_phase="dispatch")
        event.event.evidence.brain_domain = flags["event_domain"]
        event.conversation = [
            ConversationTurn(turn=1, actor="user", action="message", thoughts="status?"),
        ]
        brain.blackboard.get_event = AsyncMock(return_value=event)
        brain._extract_context_flags = AsyncMock(return_value=flags)
        brain._execute_function_call = AsyncMock(return_value=False)

        with patch("src.agents.brain._THOUGHT_SIG_V2", True):
            result = await brain._process_with_llm("evt-test", event)

        brain._execute_function_call.assert_not_awaited()
        assert result is True
        tool_results = [t for t in _turns(brain) if t.action == "tool_result"]
        assert len(tool_results) == 2
        assert tool_results[0].waitingFor == "wait_for_user" and tool_results[0].batch_size == 2
        assert tool_results[1].waitingFor == "lookup_service" and tool_results[1].batch_index == 1


class TestATDDT17BatchSetPhaseRejection:
    """T-17 (Step 5): handle_set_phase('close') rejected as FC[0] in a real batch preserves
    turn=0, actor='brain', action='tool_result', waitingFor='set_phase', response_parts, and native replay."""

    @pytest.mark.asyncio
    async def test_t17_set_phase_close_rejected_as_fc0_in_batch_preserves_native_fc_fr_replay(self):
        from tests.test_build_contents_structure import _make_brain_mock

        fcs = [
            _fc_sig("set_phase", {"phase": "close", "reasoning": "premature"}, sig="sig-t17"),
            _fc_sig("lookup_service", {"service": "test-svc"}),
        ]
        stream = MockStream([_Chunk(raw_parts=fcs)])
        brain = _make_brain(stream_factory=lambda **kw: stream)
        event = _make_event(source="slack", brain_phase="dispatch")
        event.event.evidence.brain_domain = "complicated"
        _wire_mutable_event(brain, event)

        initial_turns: list[int] = []
        orig_append = brain._append_and_broadcast.side_effect

        async def _spy_append(_eid, turn, _ev=None):
            initial_turns.append(turn.turn)
            return await orig_append(_eid, turn, _ev)

        brain._append_and_broadcast = AsyncMock(side_effect=_spy_append)

        with patch("src.agents.brain._THOUGHT_SIG_V2", True):
            result = await brain._process_with_llm("evt-test", event)

        assert result is True
        assert len(event.conversation) == 2
        fc0_turn, fc1_turn = event.conversation
        assert initial_turns[0] == 0
        assert fc0_turn.actor == "brain"
        assert fc0_turn.action == "tool_result"
        assert fc0_turn.waitingFor == "set_phase"
        assert "Cannot transition to 'close'" in (fc0_turn.thoughts or "")
        assert fc0_turn.response_parts == fcs
        assert fc0_turn.batch_size == 2
        assert fc1_turn.waitingFor == "lookup_service"
        assert fc1_turn.batch_index == 1

        # Native FC/FR replay preserves thought_signature and both FRs
        with patch("src.agents.brain._THOUGHT_SIG_V2", True):
            contents = await Brain._build_contents(_make_brain_mock(), event)
        fc_parts = [p for m in contents if m["role"] == "model" for p in m["parts"] if "functionCall" in p]
        fr_parts = [p for m in contents if m["role"] == "user" for p in m["parts"] if "functionResponse" in p]
        assert len(fc_parts) == 2
        assert len(fr_parts) == 2
        assert fc_parts[0].get("thought_signature") == "sig-t17"
        assert [p["functionResponse"]["name"] for p in fr_parts] == ["set_phase", "lookup_service"]



class TestC7CritC4F4BatchAppendTurnsAndAbort:
    @pytest.mark.asyncio
    async def test_c7_crit_c4_f4_batch_append_turns_and_abort(self):
        """[C7-CRIT + C4-F4] BlackboardState.append_turns() monotonically assigns turns
        in fakeredis and returns [] if missing. Batch-FC aborts cleanly if _append_turns_and_broadcast fails."""
        from src.state.blackboard import BlackboardState
        from fakeredis.aioredis import FakeRedis
        from src.models import ConversationTurn, EventDocument
        import time
        from unittest.mock import AsyncMock

        redis = FakeRedis()
        state = BlackboardState(redis)

        res = await state.append_turns("nonexistent", [
            ConversationTurn(turn=0, actor="brain", action="response", thoughts="t1"),
            ConversationTurn(turn=0, actor="brain", action="response", thoughts="t2")
        ])
        assert res == []

        from src.models import Literal
        event_id = await state.create_event(
            source="chat",
            service="test_svc",
            reason="Test event",
            evidence="none"
        )
        res = await state.append_turns(event_id, [
            ConversationTurn(turn=0, actor="brain", action="response", thoughts="t1"),
            ConversationTurn(turn=0, actor="brain", action="response", thoughts="t2")
        ])
        assert len(res) == 2
        assert res[0] == 1
        assert res[1] == 2

        fcs = [_fc("select_agent", {"agent_name": "developer", "task_instruction": "go"}),
               _fc("classify_event", {"domain": "clear"})]
        stream = MockStream([_Chunk(raw_parts=fcs)])
        brain = _make_brain(stream_factory=lambda **kw: stream)
        event = _make_event()

        brain._append_turns_and_broadcast = AsyncMock(return_value=False)

        with patch("src.agents.brain._THOUGHT_SIG_V2", True), _gate_patch(["select_agent", "classify_event"]), _gate_ctx_patch():
            result = await brain._process_with_llm(event_id, event)

        assert result is False
        
        # Now test with exception
        brain._append_turns_and_broadcast = AsyncMock(side_effect=Exception("Redis dead"))
        stream2 = MockStream([_Chunk(raw_parts=fcs)])
        brain2 = _make_brain(stream_factory=lambda **kw: stream2)
        brain2._append_turns_and_broadcast = AsyncMock(side_effect=Exception("Redis dead"))
        
        with patch("src.agents.brain._THOUGHT_SIG_V2", True), _gate_patch(["select_agent", "classify_event"]), _gate_ctx_patch():
            result2 = await brain2._process_with_llm(event_id, event)
            
        assert result2 is False
