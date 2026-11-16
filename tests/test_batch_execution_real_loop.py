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
        assert any(t.actor == "system" and t.action == "error" for t in turns)
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
        assert any(t.actor == "system" and t.action == "error" for t in turns)
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

        assert res2 is False
        assert event2.event.evidence.brain_domain == "casual"
        turns2 = _turns(brain2)
        assert len(turns2) == 3  # 1 thoughts turn + 2 classify_event turns; fetch_jira_issue halted by DOMAIN_CASUAL

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
    """M5: FC[0] `wait_for_user` re-admission after a response was already emitted
    (SILENT_PARK) is governed by `_pred_hard_strip_wait_user(gate_ctx)`."""

    @staticmethod
    def _readmission_brain(source: str, phase: str, with_user_turn: bool):
        gate_ctx = SimpleNamespace(
            event_source=source,
            brain_phase=phase,
            conversation=[{"actor": "user"}] if with_user_turn else [],
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

        assert result is False
        brain._execute_function_call.assert_not_awaited()


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

        assert result is False
        assert event.event.evidence.brain_domain == "casual"
        assert len(seen_flags) >= 2
        assert seen_flags[0]["event_domain"] == "complicated"
        assert seen_flags[-1]["event_domain"] == "casual", (
            "FC[1] gate re-eval must use refreshed evidence_overrides, not stale context_flags"
        )
        # fetch_jira_issue is disallowed under DOMAIN_CASUAL -> rejected, only classify_event's turns.
        assert not any("fetch_jira_issue" in (t.thoughts or "") for t in _turns(brain) if t.actor == "brain" and t.action == "tool_result")


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
