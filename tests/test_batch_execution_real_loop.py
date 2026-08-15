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


def _gate_ctx_patch(side_effect=None, return_value=None):
    kwargs = {"side_effect": side_effect} if side_effect is not None else {"return_value": return_value or MagicMock()}
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
    """Batch loop's authorization re-check must cover FC[0], not just FC[1+]."""

    @pytest.mark.asyncio
    async def test_fc0_rejected_by_gate_never_executes_and_writes_no_turn(self):
        """FC[0]'s tool is absent from active_tools -- batch must stop before any
        FC executes and real handlers (classify_event/select_agent) must never run."""
        fcs = [_fc("classify_event", {"domain": "clear"}), _fc("select_agent", {"agent_name": "developer"})]
        stream = MockStream([_Chunk(raw_parts=fcs)])
        brain = _make_brain(stream_factory=lambda **kw: stream)
        event = _make_event()

        with patch("src.agents.brain._THOUGHT_SIG_V2", True), \
                _gate_patch(["close_event"]), _gate_ctx_patch():
            result = await brain._process_with_llm("evt-test", event)

        assert result is False
        brain.blackboard.update_event_domain.assert_not_awaited()
        assert brain._append_and_broadcast.await_count == 0, (
            "gate-rejected FC[0] must not execute a handler or write any turn"
        )

    @pytest.mark.asyncio
    async def test_fc1_still_rejected_when_gate_narrows_after_fc0(self):
        """Sanity check: FC[1] rejection (pre-existing behavior) still works
        after the FC[0] fix -- FC[0] executes, FC[1] is rejected by the
        freshly re-evaluated gate and the batch stops there."""
        fcs = [_fc("classify_event", {"domain": "clear"}), _fc("select_agent", {"agent_name": "developer"})]
        stream = MockStream([_Chunk(raw_parts=fcs)])
        brain = _make_brain(stream_factory=lambda **kw: stream)
        event = _make_event()

        with patch("src.agents.brain._THOUGHT_SIG_V2", True), \
                _gate_patch(["classify_event", "select_agent"]), \
                _gate_ctx_patch(), \
                patch("src.agents.tool_gates.evaluate_gates") as mock_eval:
            # First call = outer active_tools (both allowed). Second call = FC[1] re-eval
            # (select_agent no longer allowed after classify_event ran).
            mock_eval.side_effect = [
                [{"name": "classify_event"}, {"name": "select_agent"}],
                [{"name": "classify_event"}],
            ]
            result = await brain._process_with_llm("evt-test", event)

        assert result is False
        brain.blackboard.update_event_domain.assert_awaited_once()
        turns = _turns(brain)
        assert len(turns) == 2, f"Only classify_event's 2 turns expected, got {len(turns)}"


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
        assert len(turns) == 1, f"Only select_agent's dup-turn expected, got {len(turns)}"
        assert "already actively working" in (turns[0].thoughts or "")

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
        must be caught, logged, produce a diagnostic tool_result turn, and halt the
        batch (FC[2] never runs), instead of bubbling to the generic caller."""
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
            mock_ctx.side_effect = [MagicMock(), RuntimeError("Redis connection reset")]
            result = await brain._process_with_llm("evt-test", event)

        assert result is False
        brain.blackboard.update_event_domain.assert_awaited_once(), "FC[0] (classify_event) must have executed"
        brain.blackboard.update_event_phase.assert_not_awaited(), "FC[2] (set_phase) must never run after the exception halts the batch"

        turns = _turns(brain)
        assert len(turns) == 3, f"classify_event's 2 turns + 1 diagnostic error turn expected, got {len(turns)}"
        error_turn = turns[-1]
        assert error_turn.action == "tool_result"
        assert "select_agent" in error_turn.thoughts
        assert "batch position 1" in error_turn.thoughts
        assert "Redis connection reset" in error_turn.thoughts
        assert "halted" in error_turn.thoughts.lower()


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
