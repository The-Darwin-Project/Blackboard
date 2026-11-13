# tests/test_stream_timeout.py
# @ai-rules:
# 1. [Constraint]: No Redis -- MagicMock blackboard only.
# 2. [Pattern]: Direct _process_with_llm tests with targeted stubs (matches test_task_lifecycle_ordering.py).
# 3. [Pattern]: AsyncMock adapter with MockStream for controlled async iteration.
# 4. [Gotcha]: LLM_STREAM_CHUNK_TIMEOUT_SEC=2 for fast tests. asyncio.sleep patched for retry/backoff speed.
# 5. [Invariant]: 3-level nesting: OUTER Exception > MIDDLE TimeoutError > INNER StopAsyncIteration.
# 6. [Pattern]: _ACLOSE_TIMEOUT patched to 0.1s in test_10 for fast cleanup hang tests.
# 7. [Pattern]: TestRepetitionDetector (pure, no I/O), TestCollapseStreamHandling (collapse via _process_with_llm),
#    TestCasualClamp and TestTimeoutEnvValidation extend this file. Warn-once sets in gemini_client are reset via monkeypatch.
# 8. [Pattern]: TestAdaptiveTwoPhaseStreamTimeouts pins T-6/T-7/T-9 and CR-02/CR-03/CR-09/CR-10/CR-11/CR-12 (direct async
#    generator return from GeminiAdapter.generate_stream, quota pre-acquisition outside TTFB, post-done total-timeout safety,
#    external task.cancel() propagation, bounded WS brain_thinking broadcasts, and lazy src.agents.llm import boundary).
"""Verify per-chunk stream timeout guard in _process_with_llm.

Tests cover:
- Core timeout detection (0 chunks, partial chunks, normal completion)
- Retry-once policy (independent timeout_retries counter)
- Generator cleanup (aclose called, bounded cleanup on hang)
- Reflex factory (fresh instances per retry)
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.agents.brain import Brain
from src.models import EventDocument, EventEvidence, EventInput

_sleep_patch = patch("src.agents.brain.asyncio.sleep", new_callable=AsyncMock)


@dataclass
class _Chunk:
    """Minimal LLMChunk stand-in for tests."""
    text: Optional[str] = None
    function_call: None = None
    raw_parts: None = None
    grounding_metadata: None = None
    usage: None = None
    is_thought: bool = False
    done: bool = False


class MockStream:
    """Async iterable that yields chunks then optionally hangs."""

    def __init__(self, chunks: list, *, hang_after: int | None = None, aclose_hang: bool = False):
        self._chunks = chunks
        self._hang_after = hang_after
        self._yielded = 0
        self.aclose_called = False
        self._aclose_hang = aclose_hang

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self._hang_after is not None and self._yielded >= self._hang_after:
            await asyncio.Event().wait()
        if self._yielded >= len(self._chunks):
            raise StopAsyncIteration
        chunk = self._chunks[self._yielded]
        self._yielded += 1
        return chunk

    async def aclose(self):
        self.aclose_called = True
        if self._aclose_hang:
            await asyncio.Event().wait()


def _make_event(event_id: str = "evt-test", source: str = "headhunter") -> EventDocument:
    evidence = EventEvidence(
        display_text="test", source_type=source, domain="complicated", severity="info",
    )
    return EventDocument(
        id=event_id, source=source, service="test-svc", brain_phase="dispatch",
        event=EventInput(reason="test", evidence=evidence),
        conversation=[],
    )


def _make_brain(stream_factory=None) -> Brain:
    """Create a Brain with minimal stubs for _process_with_llm streaming tests."""
    bb = MagicMock()
    bb.get_event = AsyncMock(return_value=_make_event())
    bb.append_turn = AsyncMock(return_value=1)
    bb.mark_turn_status = AsyncMock()
    bb.stamp_event = AsyncMock()
    bb.redis = MagicMock()
    bb.redis.get = AsyncMock(return_value=None)

    brain = Brain(blackboard=bb, agents={})

    adapter = MagicMock()
    if stream_factory:
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


def _gate_patch():
    """Patch tool gate evaluation to return a minimal toolset."""
    return patch(
        "src.agents.tool_gates.evaluate_gates",
        return_value=[{"name": "close_event"}],
    )


def _gate_ctx_patch():
    return patch(
        "src.agents.tool_gates.build_gate_context",
        return_value=MagicMock(),
    )


def _get_error_turns(brain: Brain) -> list:
    """Extract error turns from _append_and_broadcast calls."""
    turns = []
    for call in brain._append_and_broadcast.call_args_list:
        turn = call[0][1] if len(call[0]) > 1 else call.kwargs.get("turn")
        if turn and getattr(turn, "action", None) == "error":
            turns.append(turn)
    return turns


class TestStreamTimeout:
    """Per-chunk stream timeout guard in _process_with_llm."""

    @pytest.fixture(autouse=True)
    def _set_timeout(self, monkeypatch):
        monkeypatch.setenv("LLM_STREAM_CHUNK_TIMEOUT_SEC", "2")

    # --- Core timeout ---

    @pytest.mark.asyncio
    async def test_1_hang_after_zero_chunks(self):
        """Stream hangs after 0 chunks — TimeoutError raised within timeout window."""
        stream = MockStream([], hang_after=0)
        brain = _make_brain(stream_factory=lambda **kw: stream)
        event = _make_event()

        with _gate_patch(), _gate_ctx_patch(), _sleep_patch:
            result = await brain._process_with_llm("evt-test", event)

        assert result is False
        error_turns = _get_error_turns(brain)
        assert len(error_turns) == 1
        assert "timed out" in error_turns[0].thoughts

    @pytest.mark.asyncio
    async def test_2_hang_after_partial_chunks(self):
        """Stream hangs after 3 chunks — partial state discarded, error turn fires."""
        chunks = [_Chunk(text="hello "), _Chunk(text="world "), _Chunk(text="!")]
        stream = MockStream(chunks, hang_after=3)
        brain = _make_brain(stream_factory=lambda **kw: stream)
        event = _make_event()

        with _gate_patch(), _gate_ctx_patch(), _sleep_patch:
            result = await brain._process_with_llm("evt-test", event)

        assert result is False
        error_turns = _get_error_turns(brain)
        assert len(error_turns) == 1
        assert "timed out" in error_turns[0].thoughts

    @pytest.mark.asyncio
    async def test_3_normal_completion(self):
        """Stream completes normally — no timeout, returns False (text-only path)."""
        chunks = [_Chunk(text="response text")]
        stream = MockStream(chunks)
        brain = _make_brain(stream_factory=lambda **kw: stream)
        event = _make_event()

        with _gate_patch(), _gate_ctx_patch():
            result = await brain._process_with_llm("evt-test", event)

        assert result is False
        error_turns = _get_error_turns(brain)
        assert len(error_turns) == 0

    # --- Retry-once ---

    @pytest.mark.asyncio
    async def test_4_first_timeout_second_succeeds(self):
        """First attempt times out, second succeeds — successful response."""
        stuck = MockStream([], hang_after=0)
        good = MockStream([_Chunk(text="ok")])
        call_count = 0

        def factory(**kw):
            nonlocal call_count
            call_count += 1
            return stuck if call_count == 1 else good

        brain = _make_brain(stream_factory=factory)
        event = _make_event()

        with _gate_patch(), _gate_ctx_patch(), _sleep_patch:
            result = await brain._process_with_llm("evt-test", event)

        assert result is False
        error_turns = _get_error_turns(brain)
        assert len(error_turns) == 0, f"No error turn expected on retry success, got: {error_turns}"
        assert call_count == 2, f"Expected 2 generate_stream calls (1 timeout + 1 success), got {call_count}"

    @pytest.mark.asyncio
    async def test_5_both_timeouts_clear_accumulators(self):
        """Both attempts time out with partial chunks — accumulators cleared, error turn fires."""
        call_count = 0

        def factory(**kw):
            nonlocal call_count
            call_count += 1
            return MockStream([_Chunk(text="partial")], hang_after=1)

        brain = _make_brain(stream_factory=factory)
        event = _make_event()

        with _gate_patch(), _gate_ctx_patch(), _sleep_patch:
            result = await brain._process_with_llm("evt-test", event)

        assert result is False
        error_turns = _get_error_turns(brain)
        assert len(error_turns) == 1
        assert "timed out" in error_turns[0].thoughts
        assert call_count == 2, f"Expected 2 generate_stream calls (both timed out), got {call_count}"

    @pytest.mark.asyncio
    async def test_6_transient_503_uses_existing_path(self):
        """First attempt raises 503 — uses existing _is_transient path, not timeout."""
        call_count = 0

        def factory(**kw):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise Exception("503 Service Unavailable")
            return MockStream([_Chunk(text="ok")])

        brain = _make_brain(stream_factory=factory)
        event = _make_event()

        with _gate_patch(), _gate_ctx_patch(), _sleep_patch:
            result = await brain._process_with_llm("evt-test", event)

        assert result is False
        error_turns = _get_error_turns(brain)
        assert len(error_turns) == 0
        assert call_count == 2, f"Expected 2 generate_stream calls (1 transient retry + 1 success), got {call_count}"

    @pytest.mark.asyncio
    async def test_7_503_then_timeout_independent_counters(self):
        """503 on attempt 0, timeout on attempt 1 — timeout_retries still has budget."""
        call_count = 0

        def factory(**kw):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise Exception("503 Service Unavailable")
            if call_count == 2:
                return MockStream([], hang_after=0)
            return MockStream([_Chunk(text="recovered")])

        brain = _make_brain(stream_factory=factory)
        event = _make_event()

        with _gate_patch(), _gate_ctx_patch(), _sleep_patch:
            result = await brain._process_with_llm("evt-test", event)

        assert result is False
        error_turns = _get_error_turns(brain)
        assert len(error_turns) == 0, "Timeout retry should succeed on third attempt"
        assert call_count == 3, f"Expected 3 generate_stream calls (503 + timeout + success), got {call_count}"

    @pytest.mark.asyncio
    async def test_8_all_transients_then_timeout_on_last(self):
        """503 on attempts 0-2, timeout on attempt 3 — falls to accumulator clear + break."""
        call_count = 0

        def factory(**kw):
            nonlocal call_count
            call_count += 1
            if call_count <= 3:
                raise Exception("503 Service Unavailable")
            return MockStream([], hang_after=0)

        brain = _make_brain(stream_factory=factory)
        event = _make_event()

        with _gate_patch(), _gate_ctx_patch(), _sleep_patch:
            result = await brain._process_with_llm("evt-test", event)

        assert result is False
        error_turns = _get_error_turns(brain)
        assert len(error_turns) == 1
        assert "timed out" in error_turns[0].thoughts
        assert call_count == 4, f"Expected 4 generate_stream calls (3x503 + 1 timeout), got {call_count}"

    # --- Generator cleanup ---

    @pytest.mark.asyncio
    async def test_9_aclose_called_on_timeout(self):
        """On timeout, aclose() is called on the generator."""
        stream = MockStream([], hang_after=0)
        second = MockStream([_Chunk(text="ok")])
        call_count = 0

        def factory(**kw):
            nonlocal call_count
            call_count += 1
            return stream if call_count == 1 else second

        brain = _make_brain(stream_factory=factory)
        event = _make_event()

        with _gate_patch(), _gate_ctx_patch(), _sleep_patch:
            await brain._process_with_llm("evt-test", event)

        assert stream.aclose_called, "aclose() must be called on timed-out stream"

    @pytest.mark.asyncio
    async def test_10_aclose_hang_bounded(self, monkeypatch):
        """aclose() itself hangs — bounded cleanup (0.1s patched), outer handler gets original TimeoutError."""
        monkeypatch.setattr("src.agents.brain._ACLOSE_TIMEOUT", 0.1)
        stream = MockStream([], hang_after=0, aclose_hang=True)
        second = MockStream([_Chunk(text="ok")])
        call_count = 0

        def factory(**kw):
            nonlocal call_count
            call_count += 1
            return stream if call_count == 1 else second

        brain = _make_brain(stream_factory=factory)
        event = _make_event()

        with _gate_patch(), _gate_ctx_patch(), _sleep_patch:
            result = await brain._process_with_llm("evt-test", event)

        assert result is False
        assert stream.aclose_called, "aclose() must have been attempted"

    @pytest.mark.asyncio
    async def test_11_no_aclose_on_normal_completion(self):
        """On normal completion, no aclose() call (generator exhausts naturally)."""
        stream = MockStream([_Chunk(text="hello")])
        brain = _make_brain(stream_factory=lambda **kw: stream)
        event = _make_event()

        with _gate_patch(), _gate_ctx_patch():
            await brain._process_with_llm("evt-test", event)

        assert not stream.aclose_called, "aclose() should NOT be called on normal stream exhaustion"

    @pytest.mark.asyncio
    async def test_11b_aclose_on_repetition_collapse_break(self):
        """Repetition-collapse abort leaves the stream unexhausted -- it must be closed (@ai-rules 12b)."""
        stream = MockStream([_Chunk(text="abcdefghi" * 300), _Chunk(text="never read")])
        brain = _make_brain(stream_factory=lambda **kw: stream)
        event = _make_event()

        with _gate_patch(), _gate_ctx_patch():
            await brain._process_with_llm("evt-test", event)

        assert stream._yielded == 1, "collapse must abort after the first chunk"
        assert stream.aclose_called, "aclose() must be called when the stream is abandoned mid-way"

    # --- Reflex factory ---

    @pytest.mark.asyncio
    async def test_12_reflex_pair_fresh_per_retry(self):
        """_create_reflex_pair produces fresh instances on each call."""
        brain = _make_brain()
        brain._memory_reflex_enabled = True

        pair1 = brain._create_reflex_pair("evt-a")
        pair2 = brain._create_reflex_pair("evt-a")

        if pair1[0] is not None and pair2[0] is not None:
            assert pair1[0] is not pair2[0], "SentenceChunker must be fresh per call"
            assert pair1[1] is not pair2[1], "ReflexSearcher must be fresh per call"
        else:
            assert pair1 == (None, None), "Without archivist, both calls return (None, None)"
            assert pair2 == (None, None)

    # --- Drain cancellation recovery (VMER-2099) ---

    @pytest.mark.asyncio
    async def test_chunk_timeout_during_drain_preserves_tool_call(self, monkeypatch):
        """T-5: Brain chunk timeout during drain recovers tool call and executes it."""
        from types import SimpleNamespace
        from src.agents.llm.gemini_client import GeminiAdapter

        monkeypatch.setenv("LLM_STREAM_CHUNK_TIMEOUT_SEC", "0.2")

        fc = SimpleNamespace(name="classify_event", args={"domain": "complicated"})
        chunk1 = SimpleNamespace(
            candidates=[
                SimpleNamespace(
                    content=SimpleNamespace(parts=[SimpleNamespace(text=None, thought=False, function_call=fc)]),
                    grounding_metadata=None,
                )
            ],
            text=None,
            function_calls=[fc],
            usage_metadata=None,
        )

        class HangingSDKStream:
            def __init__(self):
                self._yielded = 0
                self.aclose_called = False

            def __aiter__(self):
                return self

            async def __anext__(self):
                if self._yielded == 0:
                    self._yielded += 1
                    return chunk1
                # Hang on subsequent anext to trigger Brain chunk timeout during drain
                await asyncio.Event().wait()

            async def aclose(self):
                self.aclose_called = True

        sdk_stream = HangingSDKStream()

        adapter = GeminiAdapter.__new__(GeminiAdapter)
        adapter._model_name = "gemini-4-carbon"
        adapter._tracker = None
        adapter._estimate_tokens = lambda contents: 50
        adapter._convert_contents = lambda contents: contents
        adapter._build_config = MagicMock(return_value=None)
        adapter.set_search_enabled = MagicMock()

        mock_client = MagicMock()
        mock_client.aio.models.generate_content_stream = AsyncMock(return_value=sdk_stream)
        adapter._client = mock_client

        brain = _make_brain()
        brain._adapter = adapter
        brain._execute_function_call = AsyncMock(return_value=True)

        event = _make_event()

        with (
            patch("src.agents.tool_gates.evaluate_gates", return_value=[{"name": "classify_event"}]),
            _gate_ctx_patch(),
            _sleep_patch,
        ):
            result = await brain._process_with_llm("evt-test", event)

        assert result is True
        brain._execute_function_call.assert_awaited_once()
        call_args = brain._execute_function_call.call_args
        assert call_args[0][0] == "evt-test"
        assert call_args[0][1] == "classify_event"
        assert call_args[0][2] == {"domain": "complicated"}
        error_turns = _get_error_turns(brain)
        assert len(error_turns) == 0
        assert sdk_stream.aclose_called is True

    # --- Repetition collapse & CASUAL thinking level unit tests ---

    def test_repetition_collapse_micro_and_macro(self):
        """_detect_repetition_collapse catches micro tokens, macro paragraphs, and runaway text."""
        from src.agents.brain import Brain

        # Normal text (no collapse)
        normal = "Here is some architecture documentation. " * 10 + "Different topic here. " * 8
        assert Brain._detect_repetition_collapse(normal) is None

        # Short text <= 2000 chars ignored
        assert Brain._detect_repetition_collapse("abc" * 500) is None

        # Micro-repetition (short token repeated back-to-back at the tail)
        micro = "Intro text " * 120 + "abcdefghi" * 100
        assert Brain._detect_repetition_collapse(micro) is not None

        # Macro-repetition (paragraph sentence repeated back-to-back at the tail)
        macro_sentence = "Thinking Process: 1. User greeting needs conversational acknowledgement and prompt. "
        macro = "Header text\n" + macro_sentence * 30
        assert Brain._detect_repetition_collapse(macro) is not None

        # Runaway length limit
        runaway = "x" * 32001
        collapse = Brain._detect_repetition_collapse(runaway)
        assert collapse is not None and collapse.kind == "runaway" and collapse.token == ""

    def test_resolve_llm_params_casual_domain_clamps_thinking_low(self):
        """CASUAL domain clamps thinking_level to low regardless of phase defaults."""
        from src.agents.brain import Brain
        brain = _make_brain()
        # Restore real method over test mock
        brain._resolve_llm_params = Brain._resolve_llm_params.__get__(brain, Brain)

        # Non-casual domain preserves phase thinking level (high from always phase)
        thinking_comp, _, _ = brain._resolve_llm_params(["always"], domain="COMPLICATED")
        assert thinking_comp == "high"

        # CASUAL domain forces low thinking level
        thinking_casual, _, _ = brain._resolve_llm_params(["always"], domain="CASUAL")
        assert thinking_casual == "low"

        # Lowercase / stripped domain still works
        thinking_casual_lower, _, _ = brain._resolve_llm_params(["always"], domain=" casual ")
        assert thinking_casual_lower == "low"

    @pytest.mark.asyncio
    async def test_thought_repetition_collapse_aborts_stream(self):
        """Thought repetition collapse stops the stream and calls aclose."""
        repeating_thought = "Thinking about user greeting again and again. " * 60
        stream = MockStream([
            _Chunk(text=repeating_thought, is_thought=True),
            _Chunk(text="never read", is_thought=False),
        ])
        brain = _make_brain(stream_factory=lambda **kw: stream)
        event = _make_event()

        with _gate_patch(), _gate_ctx_patch():
            await brain._process_with_llm("evt-test", event)

        assert stream._yielded == 1, "thought collapse must abort after the first chunk"
        assert stream.aclose_called, "aclose() must be called when stream is abandoned due to thought collapse"


# ---------------------------------------------------------------------------
# Repetition detector (pure function)
# ---------------------------------------------------------------------------

def _varied(n: int) -> str:
    """Non-repeating filler text of exactly n chars."""
    return "".join(f"w{i} " for i in range(n))[:n]


_FALSE_POSITIVE_CORPUS = {
    "prose": " ".join(f"Sentence {i} explains topic {i * 7} and why it matters here." for i in range(80)),
    "bullets": "\n".join(f"- Item {i}: check service-{i} status and report" for i in range(120)),
    "numbered": "\n".join(f"{i}. Run step {i} then verify output {i * 3}" for i in range(1, 120)),
    "table": "| id | name | value |\n|----|------|-------|\n"
    + "\n".join(f"| {i} | node-{i} | {i * 11} |" for i in range(150)),
    "hr_dividers": "\n---\n".join(f"Section {i}: " + "details " * 5 + str(i) for i in range(60)),
    "indented_code": "\n".join(f"        value_{i} = compute({i}, {i + 1})" for i in range(100)) + "\n" + " " * 400,
    "yaml": "\n".join(f"  key_{i}: value_{i}\n    image: repo/app:{i}" for i in range(100)),
    "json": "{" + ",".join(f'"k{i}": {{"id": {i}, "ok": true}}' for i in range(120)) + "}",
    "log_lines": "\n".join(f"2026-11-11T10:{i % 60:02d}:00Z INFO worker-{i} processed batch {i}" for i in range(60)),
    "non_contiguous_hits": "".join(f"status ok node {i}; " for i in range(200)),
    "trailing_rules": _varied(2500) + "\n---\n" * 80,
    "trailing_table_sep": _varied(2500) + "\n|---|---|---|---|---|---|---|---|---|" * 12,
    "trailing_whitespace": _varied(2500) + " " * 400,
}


class TestRepetitionDetector:
    """Brain._detect_repetition_collapse: no false positives on structured text, reliable on real loops."""

    @pytest.mark.parametrize("name", sorted(_FALSE_POSITIVE_CORPUS))
    def test_structured_text_is_not_a_collapse(self, name):
        text = _FALSE_POSITIVE_CORPUS[name]
        assert len(text) > 2000, f"{name} corpus must exceed the scan threshold"
        assert Brain._detect_repetition_collapse(text) is None

    def test_scan_threshold_boundary(self):
        assert Brain._detect_repetition_collapse("x" * 2000) is None
        hit = Brain._detect_repetition_collapse("x" * 2001)
        assert hit is not None and hit.kind == "micro"

    def test_runaway_cap_boundary_and_kind(self):
        assert Brain._detect_repetition_collapse(_varied(32000)) is None
        hit = Brain._detect_repetition_collapse(_varied(32001))
        assert hit is not None and hit.kind == "runaway" and hit.token == ""
        assert Brain._detect_repetition_collapse(_varied(5000), max_chars=5000) is None
        assert Brain._detect_repetition_collapse(_varied(5001), max_chars=5000).kind == "runaway"

    @pytest.mark.parametrize("tail", ["x" * 2500, "spin " * 600, "testing " * 400, "qwerty zxcvb" * 8])
    def test_genuine_micro_loops_trigger(self, tail):
        text = _varied(2000) + tail if len(tail) < 2000 else tail
        hit = Brain._detect_repetition_collapse(text)
        assert hit is not None and hit.kind == "micro" and hit.token

    def test_micro_needs_eight_contiguous_repeats(self):
        assert Brain._detect_repetition_collapse(_varied(2500) + "qwerty zxcvb" * 7) is None
        assert Brain._detect_repetition_collapse(_varied(2500) + "qwerty zxcvb" * 8).kind == "micro"

    def test_micro_ignores_head_prefix_and_noncontiguous_hits(self):
        # Token present 6x in the 300-char tail but separated by changing content -> not a loop.
        tail = "".join(f"abcdefghi-{i} " for i in range(25))
        assert Brain._detect_repetition_collapse(_varied(2500) + tail) is None

    def test_macro_sentence_loop_triggers_and_is_macro(self):
        sentence = "Thinking Process: 1. User greeting needs conversational acknowledgement and prompt. "
        hit = Brain._detect_repetition_collapse("Header text\n" + sentence * 30)
        assert hit is not None and hit.kind == "macro"

    def test_macro_repeat_thresholds_by_phrase_length(self):
        short = "The deployment pipeline finished and the report was sent. "  # 58 chars -> needs 4x
        assert 38 <= len(short) < 80
        assert Brain._detect_repetition_collapse(_varied(2500) + short * 3) is None
        assert Brain._detect_repetition_collapse(_varied(2500) + short * 4).kind == "macro"
        long = "The deployment pipeline finished successfully and the full report was sent to the maintainers. "
        assert len(long) >= 80
        assert Brain._detect_repetition_collapse(_varied(2500) + long * 2) is None
        assert Brain._detect_repetition_collapse(_varied(2500) + long * 3).kind == "macro"

    def test_repeated_yaml_keys_with_changing_values_do_not_fire(self):
        text = _varied(2500) + "".join(f"name: svc\nimage: app:{i}\nreplicas: {i}\n" for i in range(40))
        assert Brain._detect_repetition_collapse(text) is None

    @pytest.mark.parametrize("token,expected", [
        ("   ", True), ("\n---\n", True), ("|---|---|", True), ("____", True), ("```", True), ("......", True),
        ("a---", False), ("abcd", False), ("|a|", False),
    ])
    def test_is_formatting_token(self, token, expected):
        assert Brain._is_formatting_token(token) is expected

    def test_truncate_collapsed_thoughts(self):
        short = "short thought"
        assert Brain._truncate_collapsed_thoughts(short) == short
        out = Brain._truncate_collapsed_thoughts("t" * 40000)
        assert len(out) < 2100 and out.startswith("t" * 2000) and "truncated" in out


class TestRunawayCapResolution:
    def test_defaults_and_token_scaling(self, monkeypatch):
        monkeypatch.delenv("LLM_STREAM_RUNAWAY_MAX_CHARS", raising=False)
        assert Brain._resolve_runaway_max_chars(None) == 32000
        assert Brain._resolve_runaway_max_chars(2048) == 32000
        assert Brain._resolve_runaway_max_chars(65000) == 260000
        assert Brain._resolve_runaway_max_chars("not-an-int") == 32000

    def test_env_override(self, monkeypatch):
        monkeypatch.setenv("LLM_STREAM_RUNAWAY_MAX_CHARS", "50000")
        assert Brain._resolve_runaway_max_chars(65000) == 50000

    @pytest.mark.parametrize("bad", ["abc", "nan", "1e5", "-5", "0", "2000", "99999999999"])
    def test_invalid_env_falls_back_with_warning(self, monkeypatch, caplog, bad):
        monkeypatch.setenv("LLM_STREAM_RUNAWAY_MAX_CHARS", bad)
        with caplog.at_level("WARNING", logger="src.agents.brain"):
            assert Brain._resolve_runaway_max_chars(2048) == 32000
        assert "LLM_STREAM_RUNAWAY_MAX_CHARS" in caplog.text

    def test_blank_env_is_default_without_warning(self, monkeypatch, caplog):
        monkeypatch.setenv("LLM_STREAM_RUNAWAY_MAX_CHARS", "  ")
        with caplog.at_level("WARNING", logger="src.agents.brain"):
            assert Brain._resolve_runaway_max_chars(2048) == 32000
        assert "LLM_STREAM_RUNAWAY_MAX_CHARS" not in caplog.text


# ---------------------------------------------------------------------------
# Collapse handling through _process_with_llm
# ---------------------------------------------------------------------------

def _turn_actions(brain: Brain) -> list[str]:
    actions = []
    for call in brain._append_and_broadcast.call_args_list:
        turn = call[0][1] if len(call[0]) > 1 else call.kwargs.get("turn")
        actions.append(getattr(turn, "action", None))
    return actions


class TestCollapseStreamHandling:
    @pytest.fixture(autouse=True)
    def _env(self, monkeypatch):
        monkeypatch.setenv("LLM_STREAM_CHUNK_TIMEOUT_SEC", "2")
        monkeypatch.delenv("LLM_STREAM_RUNAWAY_MAX_CHARS", raising=False)

    @pytest.mark.asyncio
    async def test_text_collapse_closes_stream_and_records_error(self):
        stream = MockStream([_Chunk(text="abcdefghi" * 300), _Chunk(text="never read")])
        brain = _make_brain(stream_factory=lambda **kw: stream)
        with _gate_patch(), _gate_ctx_patch():
            result = await brain._process_with_llm("evt-test", _make_event())

        assert result is False
        assert stream._yielded == 1 and stream.aclose_called
        errors = _get_error_turns(brain)
        assert len(errors) == 1, "collapse without output must record exactly one diagnostic error turn"
        assert "repetition loop" in errors[0].thoughts and "text" in errors[0].thoughts
        assert "response" not in _turn_actions(brain) and "thoughts" not in _turn_actions(brain)
        assert brain._adapter.generate_stream.call_count == 1, "collapse must not silently re-scan inside one call"

    @pytest.mark.asyncio
    async def test_thought_collapse_records_error_and_does_not_persist_thoughts(self):
        stream = MockStream([
            _Chunk(text="Thinking about the greeting again and again. " * 60, is_thought=True),
            _Chunk(text="never read"),
        ])
        brain = _make_brain(stream_factory=lambda **kw: stream)
        with _gate_patch(), _gate_ctx_patch():
            result = await brain._process_with_llm("evt-test", _make_event())

        assert result is False
        assert stream._yielded == 1 and stream.aclose_called
        errors = _get_error_turns(brain)
        assert len(errors) == 1 and "thought" in errors[0].thoughts
        assert "thoughts" not in _turn_actions(brain), "looping thoughts must not be persisted/replayed"
        assert "evt-test" not in brain._reasoning_by_event

    @pytest.mark.asyncio
    async def test_collapse_preserves_usage_and_function_call_on_same_chunk(self):
        usage = object()
        fc = MagicMock()
        fc.name = "close_event"
        fc.args = {"reason": "done"}
        looping = "Thinking about the greeting again and again. " * 800  # ~35k chars of looping thoughts
        stream = MockStream([
            _Chunk(text=looping, is_thought=True, usage=usage, function_call=fc),
            _Chunk(text="never read"),
        ])
        brain = _make_brain(stream_factory=lambda **kw: stream)
        seen = {}

        async def _fake_execute(event_id, name, args, **kw):
            seen["name"], seen["args"] = name, args
            seen["reasoning"] = brain._reasoning_by_event.get(event_id)
            return False

        brain._execute_function_call = AsyncMock(side_effect=_fake_execute)
        with _gate_patch(), _gate_ctx_patch(), patch("src.agents.llm.record_token_usage") as record:
            await brain._process_with_llm("evt-test", _make_event())

        assert stream._yielded == 1 and stream.aclose_called
        record.assert_called_once_with("brain", usage, "evt-test")
        assert seen["name"] == "close_event" and seen["args"] == {"reason": "done"}
        assert seen["reasoning"] is not None and len(seen["reasoning"]) < 2100, "looping thoughts must be truncated"
        assert _get_error_turns(brain) == [], "a valid function_call must not be discarded as an error"

    @pytest.mark.asyncio
    async def test_text_collapse_still_records_usage(self):
        usage = object()
        stream = MockStream([_Chunk(text="abcdefghi" * 300, usage=usage)])
        brain = _make_brain(stream_factory=lambda **kw: stream)
        with _gate_patch(), _gate_ctx_patch(), patch("src.agents.llm.record_token_usage") as record:
            await brain._process_with_llm("evt-test", _make_event())
        record.assert_called_once_with("brain", usage, "evt-test")

    @pytest.mark.asyncio
    async def test_runaway_text_is_reported_as_length_not_token(self, monkeypatch, caplog):
        monkeypatch.setenv("LLM_STREAM_RUNAWAY_MAX_CHARS", "3000")
        stream = MockStream([_Chunk(text=_varied(3500))])
        brain = _make_brain(stream_factory=lambda **kw: stream)
        with _gate_patch(), _gate_ctx_patch(), caplog.at_level("WARNING", logger="src.agents.brain"):
            await brain._process_with_llm("evt-test", _make_event())

        errors = _get_error_turns(brain)
        assert len(errors) == 1 and "runaway ceiling" in errors[0].thoughts
        assert "RUNAWAY_LENGTH_LIMIT" not in caplog.text and "token=" not in caplog.text
        assert "Runaway text output" in caplog.text

    @pytest.mark.asyncio
    async def test_high_token_budget_scales_runaway_ceiling(self):
        """40k chars of varied thinking is valid when max_output_tokens=20000 (cap = 80k chars)."""
        stream = MockStream([_Chunk(text=_varied(40000), is_thought=True), _Chunk(text="Final answer.")])
        brain = _make_brain(stream_factory=lambda **kw: stream)
        brain._resolve_llm_params = MagicMock(return_value=("high", 0.7, 20000))
        with _gate_patch(), _gate_ctx_patch():
            await brain._process_with_llm("evt-test", _make_event())

        assert _get_error_turns(brain) == []
        assert stream._yielded == 2 and not stream.aclose_called
        assert "response" in _turn_actions(brain)

    @pytest.mark.asyncio
    async def test_normal_markdown_stream_is_not_aborted(self):
        text = _FALSE_POSITIVE_CORPUS["bullets"] + "\n---\n" + _FALSE_POSITIVE_CORPUS["numbered"]
        stream = MockStream([_Chunk(text=text[i:i + 500]) for i in range(0, len(text), 500)])
        brain = _make_brain(stream_factory=lambda **kw: stream)
        with _gate_patch(), _gate_ctx_patch():
            await brain._process_with_llm("evt-test", _make_event())
        assert _get_error_turns(brain) == []
        assert stream._yielded == len(stream._chunks) and not stream.aclose_called


# ---------------------------------------------------------------------------
# CASUAL thinking clamp
# ---------------------------------------------------------------------------

class TestCasualClamp:
    @pytest.mark.parametrize("level,domain,expected", [
        ("high", "casual", "low"), ("high", "CASUAL", "low"), ("high", "  Casual ", "low"),
        ("medium", "casual", "low"), ("low", "casual", "low"),
        ("minimal", "casual", "minimal"), ("none", "casual", "none"),
        ("high", "complicated", "high"), ("high", None, "high"), ("high", "", "high"),
    ])
    def test_clamp_helper(self, level, domain, expected):
        assert Brain._clamp_casual_thinking(level, domain) == expected

    def test_clamp_helper_accepts_enum(self):
        import enum

        class Domain(enum.Enum):
            CASUAL = "CASUAL"
            COMPLICATED = "complicated"

        assert Brain._clamp_casual_thinking("high", Domain.CASUAL) == "low"
        assert Brain._clamp_casual_thinking("high", Domain.COMPLICATED) == "high"

    @pytest.mark.parametrize("domain", ["casual", "CASUAL", " Casual "])
    def test_resolve_with_loader_clamps_down_only(self, domain):
        brain = _make_brain()
        brain._resolve_llm_params = Brain._resolve_llm_params.__get__(brain, Brain)
        brain.max_output_tokens = 16384
        brain._skill_loader.get_phase_meta = MagicMock(return_value={"thinking_level": "high", "priority": 10})
        assert brain._resolve_llm_params(["dispatch"], domain=domain)[0] == "low"
        assert brain._resolve_llm_params(["dispatch"], domain="complicated")[0] == "high"
        assert brain._resolve_llm_params(["dispatch"])[0] == "high"
        brain._skill_loader.get_phase_meta = MagicMock(return_value={"thinking_level": "minimal", "priority": 10})
        assert brain._resolve_llm_params(["dispatch"], domain=domain)[0] == "minimal"

    @pytest.mark.parametrize("domain,expected", [("casual", "low"), ("CASUAL", "low"), ("complicated", "high")])
    def test_resolve_without_loader(self, domain, expected):
        brain = _make_brain()
        brain._resolve_llm_params = Brain._resolve_llm_params.__get__(brain, Brain)
        brain.max_output_tokens = 16384
        brain._skill_loader = None
        assert brain._resolve_llm_params(["dispatch"], domain=domain)[0] == expected

    @pytest.mark.asyncio
    @pytest.mark.parametrize("flags,expected", [
        ({"event_domain": "casual"}, "casual"),
        ({"event_domain": "complicated"}, "complicated"),
        ({}, None),
    ])
    async def test_process_with_llm_passes_context_flag_domain(self, flags, expected, monkeypatch):
        monkeypatch.setenv("LLM_STREAM_CHUNK_TIMEOUT_SEC", "2")
        stream = MockStream([_Chunk(text="hi")])
        brain = _make_brain(stream_factory=lambda **kw: stream)
        brain._extract_context_flags = AsyncMock(return_value=dict(flags))
        with _gate_patch(), _gate_ctx_patch():
            await brain._process_with_llm("evt-test", _make_event())
        assert brain._resolve_llm_params.call_args.kwargs["domain"] == expected


# ---------------------------------------------------------------------------
# Timeout env validation + ordering
# ---------------------------------------------------------------------------

class TestTimeoutEnvValidation:
    @pytest.fixture(autouse=True)
    def _fresh_warn_state(self, monkeypatch):
        from src.agents.llm import gemini_client
        monkeypatch.setattr(gemini_client, "_TIMEOUT_ENV_WARNED", set())
        monkeypatch.setattr(gemini_client, "_TIMEOUT_ORDER_WARNED", set())

    def test_parse_timeout_env_valid_and_unset(self, caplog):
        from src.agents.llm.gemini_client import parse_timeout_env
        with caplog.at_level("WARNING"):
            assert parse_timeout_env("X", None, 240.0) == 240.0
            assert parse_timeout_env("X", "", 240.0) == 240.0
            assert parse_timeout_env("X", "   ", 240.0) == 240.0
            assert parse_timeout_env("X", "12.5", 240.0) == 12.5
            assert parse_timeout_env("X", "3600", 240.0) == 3600.0
        assert caplog.text == ""

    @pytest.mark.parametrize("bad", ["abc", "nan", "NaN", "inf", "-inf", "0", "-5", "0.0", "3600.1", "1e9", "12s"])
    def test_parse_timeout_env_invalid_falls_back_and_warns_once(self, bad, caplog):
        from src.agents.llm.gemini_client import parse_timeout_env
        with caplog.at_level("WARNING"):
            assert parse_timeout_env("LLM_HTTP_TIMEOUT_SEC", bad, 240.0) == 240.0
            assert parse_timeout_env("LLM_HTTP_TIMEOUT_SEC", bad, 240.0) == 240.0
        assert caplog.text.count("Invalid LLM_HTTP_TIMEOUT_SEC") == 1

    def test_ordering_warnings(self, caplog):
        from src.agents.llm.gemini_client import warn_on_timeout_misordering as check
        with caplog.at_level("WARNING"):
            assert check(15.0, 180.0, 240.0) is False
        assert caplog.text == ""
        with caplog.at_level("WARNING"):
            assert check(200.0, 180.0, 240.0) is True
            assert "DRAIN_TIMEOUT_SEC" in caplog.text
        caplog.clear()
        with caplog.at_level("WARNING"):
            assert check(15.0, 240.0, 240.0) is True
            assert check(15.0, 300.0, 240.0) is True
        assert "CHUNK_TIMEOUT_SEC" in caplog.text and "HTTP_TIMEOUT_SEC" in caplog.text

    @pytest.mark.parametrize("env,expected_ms", [
        (None, 240000), ("90", 90000), ("12.5", 12500), ("nan", 240000), ("inf", 240000),
        ("-1", 240000), ("0", 240000), ("junk", 240000), ("", 240000),
    ])
    def test_adapter_http_timeout_ms(self, monkeypatch, env, expected_ms):
        from src.agents.llm.gemini_client import GeminiAdapter
        if env is None:
            monkeypatch.delenv("LLM_HTTP_TIMEOUT_SEC", raising=False)
        else:
            monkeypatch.setenv("LLM_HTTP_TIMEOUT_SEC", env)
        with patch("google.genai.Client") as client_cls:
            GeminiAdapter("proj", "global", "model")
        assert client_cls.call_args.kwargs["http_options"].timeout == expected_ms

    def test_adapter_warns_when_chunk_not_below_http(self, monkeypatch, caplog):
        from src.agents.llm.gemini_client import GeminiAdapter
        monkeypatch.setenv("LLM_HTTP_TIMEOUT_SEC", "100")
        monkeypatch.setenv("LLM_STREAM_CHUNK_TIMEOUT_SEC", "180")
        with patch("google.genai.Client"), caplog.at_level("WARNING"):
            GeminiAdapter("proj", "global", "model")
        assert "LLM_STREAM_CHUNK_TIMEOUT_SEC (180.0s) >= LLM_HTTP_TIMEOUT_SEC (100.0s)" in caplog.text

    def test_adapter_default_ordering_is_silent(self, monkeypatch, caplog):
        from src.agents.llm.gemini_client import GeminiAdapter
        for var in ("LLM_HTTP_TIMEOUT_SEC", "LLM_STREAM_CHUNK_TIMEOUT_SEC"):
            monkeypatch.delenv(var, raising=False)
        monkeypatch.setattr(GeminiAdapter, "DRAIN_TIMEOUT_S", 15.0)
        with patch("google.genai.Client"), caplog.at_level("WARNING"):
            GeminiAdapter("proj", "global", "model")
        assert "TIMEOUT_SEC" not in caplog.text

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "env,expected",
        [(None, 35.0), ("nan", 35.0), ("0", 35.0), ("-3", 35.0), ("7.5", 7.5), ("200", 200.0)],
    )
    async def test_brain_chunk_timeout_parsing(self, monkeypatch, env, expected):
        for var in (
            "LLM_STREAM_TTFB_TIMEOUT_SEC",
            "LLM_STREAM_INTER_CHUNK_TIMEOUT_SEC",
            "LLM_STREAM_TOTAL_TIMEOUT_SEC",
        ):
            monkeypatch.delenv(var, raising=False)
        if env is None:
            monkeypatch.delenv("LLM_STREAM_CHUNK_TIMEOUT_SEC", raising=False)
        else:
            monkeypatch.setenv("LLM_STREAM_CHUNK_TIMEOUT_SEC", env)
        stream = MockStream([_Chunk(text="hi")])
        brain = _make_brain(stream_factory=lambda **kw: stream)
        real_wait_for = asyncio.wait_for
        timeouts = []

        async def _spy(aw, timeout=None):
            timeouts.append(timeout)
            return await real_wait_for(aw, timeout=timeout)

        with _gate_patch(), _gate_ctx_patch(), patch("src.agents.brain.asyncio.wait_for", _spy):
            await brain._process_with_llm("evt-test", _make_event())
        assert timeouts[0] == expected


# ---------------------------------------------------------------------------
# QE boundary hardening: exact thresholds of the repetition guard, collapse metadata, clamp and timeout helpers
# ---------------------------------------------------------------------------

def _tok(n: int) -> str:
    """Aperiodic n-char token (no internal period, never formatting-only)."""
    import string
    return (string.ascii_letters + string.digits)[:n]


class TestRepetitionBoundaryHardening:
    """Pin every numeric bound of Brain._detect_repetition_collapse (micro 4-37 x8, macro 38-200 x4/<80 x3/>=80)."""

    def test_micro_min_token_length_is_four(self):
        hit = Brain._detect_repetition_collapse(_varied(2500) + "abcd" * 8)
        assert hit is not None and hit.kind == "micro" and hit.token == "abcd"
        # A 3-char unit is below the documented 4-char floor and must not fire after only 8 repeats.
        assert Brain._detect_repetition_collapse(_varied(2500) + "abc" * 8) is None

    def test_micro_max_token_length_is_37(self):
        tok = _tok(37)
        hit = Brain._detect_repetition_collapse(_varied(2500) + tok * 8)
        assert hit is not None and hit.kind == "micro" and hit.token == tok
        assert Brain._detect_repetition_collapse(_varied(2500) + tok * 7) is None

    def test_macro_min_phrase_length_is_38(self):
        phrase = _tok(38)
        assert Brain._detect_repetition_collapse(_varied(2500) + phrase * 3) is None
        hit = Brain._detect_repetition_collapse(_varied(2500) + phrase * 4)
        assert hit is not None and hit.kind == "macro" and hit.token == phrase

    def test_macro_repeat_threshold_flips_exactly_at_80_chars(self):
        p79, p80 = _varied(79), _varied(80)
        assert len(p79) == 79 and len(p80) == 80
        # 79 chars (< 80): 4x required
        assert Brain._detect_repetition_collapse(_varied(2500) + p79 * 3) is None
        assert Brain._detect_repetition_collapse(_varied(2500) + p79 * 4).kind == "macro"
        # 80 chars (>= 80): 3x required
        assert Brain._detect_repetition_collapse(_varied(2500) + p80 * 2) is None
        assert Brain._detect_repetition_collapse(_varied(2500) + p80 * 3).kind == "macro"

    def test_macro_max_phrase_length_is_200(self):
        p200, p201 = _varied(200), _varied(201)
        hit = Brain._detect_repetition_collapse(_varied(2500) + p200 * 3)
        assert hit is not None and hit.kind == "macro" and len(hit.token) == 200
        assert Brain._detect_repetition_collapse(_varied(2500) + p201 * 3) is None

    def test_micro_loop_that_ended_earlier_is_not_a_tail_loop(self):
        tok = "qwerty zxcvb"
        text = _varied(2500) + tok * 8 + " and then the answer moved on to other things " + tok
        assert Brain._detect_repetition_collapse(text) is None

    def test_macro_loop_that_ended_earlier_is_not_a_tail_loop(self):
        short = "The deployment pipeline finished and the report was sent. "
        text = _varied(2500) + short * 4 + "Meanwhile the situation changed completely today. " + short
        assert Brain._detect_repetition_collapse(text) is None

    @pytest.mark.parametrize("fmt", ["#", "─", "│", "`", ">", "*", "=", "~", "+", "_", "."])
    def test_trailing_formatting_runs_are_not_loops(self, fmt):
        assert Brain._detect_repetition_collapse(_varied(2500) + fmt * 400) is None
        assert Brain._is_formatting_token(fmt * 5) is True


class TestRunawayEnvBoundaries:
    def test_env_upper_bound_is_inclusive_ten_million(self, monkeypatch, caplog):
        monkeypatch.setenv("LLM_STREAM_RUNAWAY_MAX_CHARS", "10000000")
        assert Brain._resolve_runaway_max_chars(2048) == 10_000_000
        monkeypatch.setenv("LLM_STREAM_RUNAWAY_MAX_CHARS", "10000001")
        with caplog.at_level("WARNING", logger="src.agents.brain"):
            assert Brain._resolve_runaway_max_chars(2048) == 32000
        assert "LLM_STREAM_RUNAWAY_MAX_CHARS" in caplog.text

    def test_env_lower_bound_is_exclusive_2000(self, monkeypatch):
        monkeypatch.setenv("LLM_STREAM_RUNAWAY_MAX_CHARS", "2001")
        assert Brain._resolve_runaway_max_chars(2048) == 2001
        monkeypatch.setenv("LLM_STREAM_RUNAWAY_MAX_CHARS", "2000")
        assert Brain._resolve_runaway_max_chars(2048) == 32000

    def test_truncate_keeps_exactly_the_2000_char_head(self):
        exact = "H" * 2000
        assert Brain._truncate_collapsed_thoughts(exact) == exact
        out = Brain._truncate_collapsed_thoughts("H" * 2000 + "T" * 5000)
        assert out.startswith("H" * 2000 + "\n[...") and "T" not in out
        assert Brain._truncate_collapsed_thoughts("H" * 2000 + "T") .count("T") == 0


class TestCollapseMetadataAndWiring:
    @pytest.fixture(autouse=True)
    def _env(self, monkeypatch):
        monkeypatch.setenv("LLM_STREAM_CHUNK_TIMEOUT_SEC", "2")
        monkeypatch.delenv("LLM_STREAM_RUNAWAY_MAX_CHARS", raising=False)

    @staticmethod
    def _fc():
        fc = MagicMock()
        fc.name = "close_event"
        fc.args = {"reason": "done"}
        return fc

    @pytest.mark.asyncio
    async def test_collapse_chunk_preserves_raw_parts_and_grounding(self):
        raw = [{"functionCall": {"name": "close_event", "args": {"reason": "done"}}}]
        grounding = {"chunks": [{"title": "T", "uri": "https://example.com"}], "queries": ["q"]}
        stream = MockStream([
            _Chunk(text="Thinking about the greeting again and again. " * 60, is_thought=True,
                   function_call=self._fc(), raw_parts=raw, grounding_metadata=grounding),
        ])
        brain = _make_brain(stream_factory=lambda **kw: stream)
        brain._normalize_response_parts = MagicMock(return_value=None)
        brain._resolve_grounding_urls = AsyncMock(return_value=[{"title": "T", "uri": "https://example.com"}])
        brain._execute_function_call = AsyncMock(return_value=False)
        with _gate_patch(), _gate_ctx_patch():
            await brain._process_with_llm("evt-test", _make_event())
        brain._normalize_response_parts.assert_called_once_with(raw)
        brain._resolve_grounding_urls.assert_awaited_once_with(grounding["chunks"])

    @pytest.mark.asyncio
    async def test_text_collapse_with_function_call_does_not_persist_looping_text(self):
        looping = "abcdefghi" * 300
        stream = MockStream([_Chunk(text=looping, function_call=self._fc())])
        brain = _make_brain(stream_factory=lambda **kw: stream)
        brain._execute_function_call = AsyncMock(return_value=False)
        with _gate_patch(), _gate_ctx_patch():
            await brain._process_with_llm("evt-test", _make_event())
        for call in brain._append_and_broadcast.call_args_list:
            turn = call[0][1] if len(call[0]) > 1 else call.kwargs.get("turn")
            assert "abcdefghi" not in (getattr(turn, "thoughts", None) or "")

    @pytest.mark.asyncio
    async def test_thought_collapse_keeps_previously_streamed_text(self):
        stream = MockStream([
            _Chunk(text="Visible answer part one."),
            _Chunk(text="Thinking about the greeting again and again. " * 60, is_thought=True, function_call=self._fc()),
        ])
        brain = _make_brain(stream_factory=lambda **kw: stream)
        brain._execute_function_call = AsyncMock(return_value=False)
        with _gate_patch(), _gate_ctx_patch():
            await brain._process_with_llm("evt-test", _make_event())
        persisted = []
        for call in brain._append_and_broadcast.call_args_list:
            turn = call[0][1] if len(call[0]) > 1 else call.kwargs.get("turn")
            persisted.append(getattr(turn, "thoughts", None) or "")
        assert any("Visible answer part one." in t for t in persisted)

    @pytest.mark.asyncio
    @pytest.mark.parametrize("chunk", [
        _Chunk(text="abcdefghi" * 300),
        _Chunk(text="Thinking about the greeting again and again. " * 60, is_thought=True),
    ])
    async def test_collapse_clears_stale_reasoning_and_does_not_broadcast_looping_chunk(self, chunk):
        stream = MockStream([chunk])
        brain = _make_brain(stream_factory=lambda **kw: stream)
        brain._reasoning_by_event["evt-test"] = "stale reasoning from an earlier call"
        with _gate_patch(), _gate_ctx_patch():
            await brain._process_with_llm("evt-test", _make_event())
        assert "evt-test" not in brain._reasoning_by_event
        payloads = [c.args[0] for c in brain._broadcast.call_args_list]
        streamed = [p for p in payloads if p["type"] == "brain_thinking" and p.get("text")]
        assert streamed == [], "the collapsing chunk must not be streamed to the UI"
        assert [p["type"] for p in payloads].count("brain_thinking_done") == 1

    @pytest.mark.asyncio
    @pytest.mark.parametrize("flags,expected", [({"event_domain": "casual"}, "casual"), ({}, "")])
    async def test_reflex_pair_receives_event_domain(self, flags, expected):
        stream = MockStream([_Chunk(text="hi")])
        brain = _make_brain(stream_factory=lambda **kw: stream)
        brain._extract_context_flags = AsyncMock(return_value=dict(flags))
        brain._create_reflex_pair = MagicMock(return_value=(None, None))
        with _gate_patch(), _gate_ctx_patch():
            await brain._process_with_llm("evt-test", _make_event())
        assert brain._create_reflex_pair.call_args.kwargs["event_domain"] == expected


class TestClampAndTimeoutBoundaries:
    @pytest.fixture(autouse=True)
    def _fresh_warn_state(self, monkeypatch):
        from src.agents.llm import gemini_client
        monkeypatch.setattr(gemini_client, "_TIMEOUT_ENV_WARNED", set())
        monkeypatch.setattr(gemini_client, "_TIMEOUT_ORDER_WARNED", set())

    @pytest.mark.parametrize("level", ["MINIMAL", " minimal ", "None", "LOW", " Low "])
    def test_clamp_preserves_low_levels_verbatim_regardless_of_case_and_whitespace(self, level):
        assert Brain._clamp_casual_thinking(level, "casual") == level

    def test_parse_timeout_env_rejects_inf_even_with_unbounded_max(self):
        from src.agents.llm.gemini_client import parse_timeout_env
        assert parse_timeout_env("X", "inf", 5.0, max_value=float("inf")) == 5.0
        assert parse_timeout_env("X", "nan", 5.0, max_value=float("inf")) == 5.0

    def test_ordering_drain_equal_to_chunk_is_misordered(self, caplog):
        from src.agents.llm.gemini_client import warn_on_timeout_misordering as check
        with caplog.at_level("WARNING"):
            assert check(180.0, 180.0, 240.0) is True
        assert "LLM_STREAM_DRAIN_TIMEOUT_SEC" in caplog.text

    def test_ordering_warns_once_per_value_triple(self, caplog):
        from src.agents.llm.gemini_client import warn_on_timeout_misordering as check
        with caplog.at_level("WARNING"):
            assert check(200.0, 180.0, 240.0) is True
            assert check(200.0, 180.0, 240.0) is True
            assert check(15.0, 300.0, 240.0) is True
            assert check(15.0, 300.0, 240.0) is True
        assert caplog.text.count("LLM_STREAM_DRAIN_TIMEOUT_SEC") == 1
        assert caplog.text.count("LLM_HTTP_TIMEOUT_SEC") == 1

    def test_default_drain_timeout_is_15s_when_env_unset(self):
        import os
        import subprocess
        import sys
        from pathlib import Path
        env = {k: v for k, v in os.environ.items() if k != "LLM_STREAM_DRAIN_TIMEOUT_SEC"}
        root = Path(__file__).resolve().parent.parent
        out = subprocess.run(
            [sys.executable, "-c",
             "from src.agents.llm.gemini_client import GeminiAdapter as G; print(G.DRAIN_TIMEOUT_S)"],
            cwd=root, env=env, capture_output=True, text=True, timeout=120,
        )
        assert out.returncode == 0, out.stderr
        assert out.stdout.strip().splitlines()[-1] == "15.0"


# ---------------------------------------------------------------------------
# Gemini 4 Runtime Resilience: T-5, T-6, T-7, T-9
# ---------------------------------------------------------------------------


class TestGemini4ThinkingLevelNormalization:
    """T-5: Gemini 4 normalizes thinking_level in GeminiAdapter._build_config and omits thinking_budget,
    while preserving gemini-3.8-flash passthrough and Brain lowercase contracts.
    """

    @pytest.mark.parametrize(
        "raw_level,expected",
        [
            ("minimal", "LOW"),
            ("MINIMAL", "LOW"),
            (" minimal ", "LOW"),
            ("none", "LOW"),
            ("NONE", "LOW"),
            ("low", "LOW"),
            ("medium", "MEDIUM"),
            ("high", "HIGH"),
        ],
    )
    def test_t5_gemini4_normalizes_thinking_levels_and_omits_budget(self, raw_level: str, expected: str):
        from src.agents.llm.gemini_client import GeminiAdapter

        adapter = GeminiAdapter.__new__(GeminiAdapter)
        adapter._model_name = "gemini-4-carbon"
        cfg = adapter._build_config("sys", None, 1.0, 0.95, 65536, thinking_level=raw_level)

        assert cfg.thinking_config is not None
        assert cfg.thinking_config.thinking_level == expected
        assert cfg.thinking_config.thinking_budget is None
        assert "thinking_budget" not in cfg.thinking_config.model_dump(exclude_none=True)

    def test_t5_gemini4_empty_omits_thinking_level_and_unknown_warns_to_low(self, caplog):
        from src.agents.llm.gemini_client import GeminiAdapter

        adapter = GeminiAdapter.__new__(GeminiAdapter)
        adapter._model_name = "gemini-4-carbon"

        empty_cfg = adapter._build_config("sys", None, 1.0, 0.95, 65536, thinking_level="")
        assert empty_cfg.thinking_config is not None
        assert empty_cfg.thinking_config.thinking_level is None
        assert empty_cfg.thinking_config.thinking_budget is None

        with caplog.at_level("WARNING", logger="src.agents.llm.gemini_client"):
            unknown_cfg = adapter._build_config("sys", None, 1.0, 0.95, 65536, thinking_level="ultra")
        assert unknown_cfg.thinking_config.thinking_level == "LOW"
        assert unknown_cfg.thinking_config.thinking_budget is None
        assert any("ultra" in r.getMessage().lower() for r in caplog.records)

    def test_t5_non_gemini4_passes_minimal_through_and_brain_keeps_lowercase(self):
        from google.genai import types
        from src.agents.llm.gemini_client import GeminiAdapter

        adapter = GeminiAdapter.__new__(GeminiAdapter)
        adapter._model_name = "gemini-3.8-flash"

        with patch("google.genai.types.ThinkingConfig", wraps=types.ThinkingConfig) as tc_spy:
            cfg_lower = adapter._build_config("sys", None, 1.0, 0.95, 65536, thinking_level="minimal")
            assert tc_spy.call_args.kwargs.get("thinking_level") == "minimal"
            assert cfg_lower.thinking_config.thinking_level == "MINIMAL"

            cfg_upper = adapter._build_config("sys", None, 1.0, 0.95, 65536, thinking_level="MINIMAL")
            assert tc_spy.call_args.kwargs.get("thinking_level") == "MINIMAL"
            assert cfg_upper.thinking_config.thinking_level == "MINIMAL"

        assert Brain._clamp_casual_thinking("high", "casual") == "low"
        assert Brain._clamp_casual_thinking("minimal", "casual") == "minimal"

        brain = _make_brain()
        brain._resolve_llm_params = Brain._resolve_llm_params.__get__(brain, Brain)
        brain._skill_loader.get_phase_meta = MagicMock(return_value={"thinking_level": "minimal", "priority": 10})
        assert brain._resolve_llm_params(["dispatch"], domain="casual")[0] == "minimal"
        assert brain._resolve_llm_params(["dispatch"], domain="complicated")[0] == "minimal"


class TestAdaptiveTwoPhaseStreamTimeouts:
    """T-6, T-7, T-9: Two-phase adaptive TTFB + sliding inter-chunk + hard total stream timeouts."""

    @pytest.fixture(autouse=True)
    def _clean_timeout_env(self, monkeypatch):
        from src.agents.llm import gemini_client

        monkeypatch.setattr(gemini_client, "_TIMEOUT_ENV_WARNED", set())
        monkeypatch.setattr(gemini_client, "_TIMEOUT_ORDER_WARNED", set())
        for var in (
            "LLM_STREAM_CHUNK_TIMEOUT_SEC",
            "LLM_STREAM_TTFB_TIMEOUT_SEC",
            "LLM_STREAM_INTER_CHUNK_TIMEOUT_SEC",
            "LLM_STREAM_TOTAL_TIMEOUT_SEC",
        ):
            monkeypatch.delenv(var, raising=False)

    def test_t6_resolve_stream_timeouts_defaults_nan_and_overrides(self, monkeypatch, caplog):
        from src.agents.llm import resolve_stream_timeouts

        assert resolve_stream_timeouts() == (35.0, 30.0, 180.0)

        monkeypatch.setenv("LLM_STREAM_CHUNK_TIMEOUT_SEC", "nan")
        with caplog.at_level("WARNING", logger="src.agents.llm.gemini_client"):
            assert resolve_stream_timeouts() == (35.0, 30.0, 180.0)
        assert caplog.text.count("Invalid LLM_STREAM_CHUNK_TIMEOUT_SEC") == 1

        monkeypatch.setenv("LLM_STREAM_CHUNK_TIMEOUT_SEC", "200")
        assert resolve_stream_timeouts() == (200.0, 200.0, 200.0)

        monkeypatch.setenv("LLM_STREAM_TTFB_TIMEOUT_SEC", "12")
        monkeypatch.setenv("LLM_STREAM_INTER_CHUNK_TIMEOUT_SEC", "8")
        monkeypatch.setenv("LLM_STREAM_TOTAL_TIMEOUT_SEC", "90")
        assert resolve_stream_timeouts() == (12.0, 8.0, 90.0)

    def test_t6_timeout_hierarchy_exports_line_budget_and_brain_import_boundary(self):
        from pathlib import Path
        import src.agents.llm as llm_pkg
        from src.agents.llm import (
            LLMStreamInterChunkTimeoutError,
            LLMStreamTimeoutError,
            LLMStreamTotalTimeoutError,
            LLMStreamTTFBTimeoutError,
            resolve_stream_timeouts,
        )

        assert issubclass(LLMStreamTimeoutError, asyncio.TimeoutError)
        assert issubclass(LLMStreamTTFBTimeoutError, LLMStreamTimeoutError)
        assert issubclass(LLMStreamInterChunkTimeoutError, LLMStreamTimeoutError)
        assert issubclass(LLMStreamTotalTimeoutError, LLMStreamTimeoutError)
        assert callable(resolve_stream_timeouts)

        for sym in (
            "LLMStreamTimeoutError",
            "LLMStreamTTFBTimeoutError",
            "LLMStreamInterChunkTimeoutError",
            "LLMStreamTotalTimeoutError",
            "resolve_stream_timeouts",
        ):
            assert sym in llm_pkg.__all__, f"{sym} missing from src.agents.llm.__all__"

        repo_root = Path(__file__).resolve().parent.parent
        init_lines = (repo_root / "src" / "agents" / "llm" / "__init__.py").read_text().splitlines()
        assert len(init_lines) <= 100, f"src/agents/llm/__init__.py exceeds 100-line budget ({len(init_lines)} lines)"

        brain_src = (repo_root / "src" / "agents" / "brain.py").read_text()
        assert "from .llm.gemini_client import" not in brain_src

    @pytest.mark.asyncio
    async def test_t6_chunk0_ttfb_stall_raises_ttfb_timeout_retries_once_and_records_ttfb_turn(self, monkeypatch):
        import sys
        from src.agents.llm import LLMStreamTTFBTimeoutError

        monkeypatch.setenv("LLM_STREAM_TTFB_TIMEOUT_SEC", "0.03")
        monkeypatch.setenv("LLM_STREAM_INTER_CHUNK_TIMEOUT_SEC", "0.02")
        monkeypatch.setenv("LLM_STREAM_TOTAL_TIMEOUT_SEC", "0.50")

        active_excs = []

        class ExcCaptureStream(MockStream):
            async def aclose(self):
                active_excs.append(sys.exc_info()[1])
                await super().aclose()

        call_count = 0

        def _factory(**kw):
            nonlocal call_count
            call_count += 1
            return ExcCaptureStream([], hang_after=0)

        brain = _make_brain(stream_factory=_factory)
        with _gate_patch(), _gate_ctx_patch(), _sleep_patch:
            result = await asyncio.wait_for(brain._process_with_llm("evt-test", _make_event()), timeout=0.6)

        assert result is False
        assert call_count == 2
        assert len(active_excs) == 2
        assert all(isinstance(exc, LLMStreamTTFBTimeoutError) for exc in active_excs)
        errors = _get_error_turns(brain)
        assert len(errors) == 1
        assert "timed out" in errors[0].thoughts
        assert "ttfb" in errors[0].thoughts.lower()

    @pytest.mark.asyncio
    async def test_t6_chunk0_when_ttfb_equals_total_timeout_classifies_as_ttfb_and_retries(self, monkeypatch):
        import sys
        from src.agents.llm import LLMStreamTotalTimeoutError, LLMStreamTTFBTimeoutError

        # Legacy LLM_STREAM_CHUNK_TIMEOUT_SEC="200" sets ttfb_timeout == total_timeout == 200.0
        monkeypatch.setenv("LLM_STREAM_CHUNK_TIMEOUT_SEC", "200")

        active_excs = []

        class ExcCaptureStream(MockStream):
            async def aclose(self):
                active_excs.append(sys.exc_info()[1])
                await super().aclose()

        call_count = 0

        def _factory(**kw):
            nonlocal call_count
            call_count += 1
            return ExcCaptureStream([], hang_after=0)

        real_wait_for = asyncio.wait_for
        seen_budgets = []

        async def _fast_timeout_on_200(aw, timeout=None):
            seen_budgets.append(timeout)
            if timeout == 200.0:
                if hasattr(aw, "close"):
                    aw.close()
                raise asyncio.TimeoutError()
            return await real_wait_for(aw, timeout=timeout)

        # Simulate slight monotonic clock advance between stream_start and Chunk-0 check (S3-1)
        mono_tick = [1000.0]

        def _fake_monotonic():
            mono_tick[0] += 0.005
            return mono_tick[0]

        brain = _make_brain(stream_factory=_factory)
        with (
            _gate_patch(),
            _gate_ctx_patch(),
            _sleep_patch,
            patch("src.agents.brain.asyncio.wait_for", _fast_timeout_on_200),
            patch("src.agents.brain.time.monotonic", _fake_monotonic),
        ):
            result = await brain._process_with_llm("evt-test", _make_event())

        assert result is False
        assert seen_budgets[0] == 200.0
        assert call_count == 2, "Chunk-0 timeout with ttfb == total must classify as TTFB and retry once"
        assert len(active_excs) == 2
        assert all(
            isinstance(exc, LLMStreamTTFBTimeoutError) and not isinstance(exc, LLMStreamTotalTimeoutError)
            for exc in active_excs
        )
        errors = _get_error_turns(brain)
        assert len(errors) == 1
        assert "timed out" in errors[0].thoughts
        assert "ttfb" in errors[0].thoughts.lower()

    @pytest.mark.asyncio
    async def test_t7_inter_chunk_stall_after_thought_heartbeat_retries_and_closes_sdk_stream(self, monkeypatch):
        from google.genai import types
        from src.agents.llm import LLMStreamInterChunkTimeoutError
        from src.agents.llm.gemini_client import GeminiAdapter

        monkeypatch.setenv("LLM_STREAM_TTFB_TIMEOUT_SEC", "0.08")
        monkeypatch.setenv("LLM_STREAM_INTER_CHUNK_TIMEOUT_SEC", "0.03")
        monkeypatch.setenv("LLM_STREAM_TOTAL_TIMEOUT_SEC", "0.50")

        created_sdk_streams = []

        class SpySDKStream:
            def __init__(self):
                self._idx = 0
                self.aclose_called = False

            def __aiter__(self):
                return self

            async def __anext__(self):
                if self._idx == 0:
                    self._idx += 1
                    from types import SimpleNamespace

                    return SimpleNamespace(
                        candidates=[
                            SimpleNamespace(
                                content=SimpleNamespace(parts=[types.Part(thought=True, text="heartbeat")]),
                                grounding_metadata=None,
                            )
                        ],
                        text=None,
                        function_calls=[],
                        usage_metadata=None,
                    )
                await asyncio.Event().wait()

            async def aclose(self):
                self.aclose_called = True

        def _make_sdk_stream(**kw):
            s = SpySDKStream()
            created_sdk_streams.append(s)
            return s

        adapter = GeminiAdapter.__new__(GeminiAdapter)
        adapter._model_name = "gemini-4-carbon"
        adapter._tracker = None
        adapter._estimate_tokens = lambda contents: 50
        adapter._convert_contents = lambda contents: contents
        adapter._build_config = MagicMock(return_value=None)
        adapter.set_search_enabled = MagicMock()
        adapter._client = MagicMock()
        adapter._client.aio.models.generate_content_stream = AsyncMock(side_effect=_make_sdk_stream)

        import inspect

        raw_gen = adapter.generate_stream("sys", "probe")
        assert inspect.isasyncgen(raw_gen), "generate_stream must return _stream_chunks async generator directly"
        await raw_gen.aclose()
        created_sdk_streams.clear()

        brain = _make_brain()
        brain._adapter = adapter
        with (
            _gate_patch(),
            _gate_ctx_patch(),
            _sleep_patch,
            patch("src.agents.brain.LLMStreamInterChunkTimeoutError", wraps=LLMStreamInterChunkTimeoutError) as inter_err_spy,
        ):
            result = await asyncio.wait_for(brain._process_with_llm("evt-test", _make_event()), timeout=0.6)

        assert result is False
        assert len(created_sdk_streams) == 2, "Inter-chunk timeout must retry once"
        assert all(s.aclose_called for s in created_sdk_streams), "gen.aclose() must close _stream_chunks and SDK stream"
        assert inter_err_spy.call_count == 2
        errors = _get_error_turns(brain)
        assert len(errors) == 1
        assert "timed out" in errors[0].thoughts
        assert "inter-chunk" in errors[0].thoughts.lower()

    @pytest.mark.asyncio
    async def test_t9_slow_drip_exceeding_total_timeout_aborts_immediately_without_retry(self, monkeypatch):
        import sys
        from src.agents.llm import LLMStreamTotalTimeoutError

        monkeypatch.setenv("LLM_STREAM_TTFB_TIMEOUT_SEC", "0.08")
        monkeypatch.setenv("LLM_STREAM_INTER_CHUNK_TIMEOUT_SEC", "0.08")
        monkeypatch.setenv("LLM_STREAM_TOTAL_TIMEOUT_SEC", "0.05")

        class DripStream:
            def __init__(self):
                self.yielded = 0
                self.aclose_called = False
                self.active_exc = None

            def __aiter__(self):
                return self

            async def __anext__(self):
                await asyncio.sleep(0.02)
                self.yielded += 1
                return _Chunk(text=f"drip-{self.yielded} ", is_thought=True)

            async def aclose(self):
                self.aclose_called = True
                self.active_exc = sys.exc_info()[1]

        created = []

        def _factory(**kw):
            d = DripStream()
            created.append(d)
            return d

        # Keep real asyncio.sleep for DripStream's 0.02s ticks (no retry sleep occurs on total timeout)
        brain = _make_brain(stream_factory=_factory)
        with _gate_patch(), _gate_ctx_patch():
            result = await asyncio.wait_for(brain._process_with_llm("evt-test", _make_event()), timeout=0.6)

        assert result is False
        assert len(created) == 1, "LLMStreamTotalTimeoutError must abort immediately with ZERO retries"
        assert created[0].aclose_called is True
        assert isinstance(created[0].active_exc, LLMStreamTotalTimeoutError)
        errors = _get_error_turns(brain)
        assert len(errors) == 1
        assert "timed out" in errors[0].thoughts
        assert "total" in errors[0].thoughts.lower()
        assert "0.05" in errors[0].thoughts

    @pytest.mark.asyncio
    async def test_cr02_brain_quota_acquire_slower_than_ttfb_succeeds_without_false_ttfb_timeout(self, monkeypatch):
        from types import SimpleNamespace
        from google.genai import types
        from src.agents.llm.gemini_client import GeminiAdapter
        from src.agents.llm.quota_tracker import QuotaTracker

        monkeypatch.setenv("LLM_STREAM_TTFB_TIMEOUT_SEC", "0.03")
        monkeypatch.setenv("LLM_STREAM_INTER_CHUNK_TIMEOUT_SEC", "0.05")
        monkeypatch.setenv("LLM_STREAM_TOTAL_TIMEOUT_SEC", "0.50")

        tracker = QuotaTracker(tpm_limit=100_000)
        orig_acquire = tracker.acquire

        async def _slow_acquire(*args, **kwargs):
            await asyncio.sleep(0.06)  # 2x ttfb_timeout, must NOT count against Chunk-0 timer
            return await orig_acquire(*args, **kwargs)

        tracker.acquire = AsyncMock(side_effect=_slow_acquire)

        async def _fast_sdk_stream():
            yield SimpleNamespace(
                candidates=[SimpleNamespace(content=SimpleNamespace(parts=[types.Part(text="fast reply")]), grounding_metadata=None)],
                text="fast reply",
                function_calls=[],
                usage_metadata=SimpleNamespace(prompt_token_count=20, candidates_token_count=10, total_token_count=30),
            )

        adapter = GeminiAdapter.__new__(GeminiAdapter)
        adapter._model_name = "gemini-4-carbon"
        adapter._tracker = tracker
        adapter._estimate_tokens = lambda contents: 30
        adapter._convert_contents = lambda contents: contents
        adapter._build_config = MagicMock(return_value=None)
        adapter._client = MagicMock()
        adapter._client.aio.models.generate_content_stream = AsyncMock(side_effect=lambda **kw: _fast_sdk_stream())

        brain = _make_brain()
        brain._adapter = adapter
        with _gate_patch(), _gate_ctx_patch():
            result = await brain._process_with_llm("evt-cr02", _make_event("evt-cr02"))

        assert result is False
        assert _get_error_turns(brain) == []
        assert tracker.acquire.await_count == 1

    @pytest.mark.asyncio
    async def test_cr03_cr09_post_fc_drain_total_expiry_preserves_fc_and_external_cancel_propagates(self, monkeypatch):
        from types import SimpleNamespace
        from google.genai import types
        from src.agents.llm.gemini_client import GeminiAdapter

        # 1. CR-03: total_timeout expires during post-FC drain -> rescued done=True FC is preserved & executed!
        monkeypatch.setenv("LLM_STREAM_TTFB_TIMEOUT_SEC", "0.20")
        monkeypatch.setenv("LLM_STREAM_INTER_CHUNK_TIMEOUT_SEC", "0.20")
        monkeypatch.setenv("LLM_STREAM_TOTAL_TIMEOUT_SEC", "0.06")

        fc = types.FunctionCall(name="close_event", args={"reason": "done"})

        class ThoughtThenDrainHangStream:
            def __init__(self):
                self._idx = 0
                self.aclose_called = False

            def __aiter__(self):
                return self

            async def __anext__(self):
                if self._idx == 0:
                    self._idx += 1
                    return SimpleNamespace(
                        candidates=[SimpleNamespace(content=SimpleNamespace(parts=[types.Part(thought=True, text="t")]), grounding_metadata=None)],
                        text=None,
                        function_calls=[],
                        usage_metadata=None,
                    )
                if self._idx == 1:
                    self._idx += 1
                    return SimpleNamespace(
                        candidates=[SimpleNamespace(content=SimpleNamespace(parts=[types.Part(function_call=fc)]), grounding_metadata=None)],
                        text=None,
                        function_calls=[fc],
                        usage_metadata=None,
                    )
                await asyncio.Event().wait()

            async def aclose(self):
                self.aclose_called = True

        adapter = GeminiAdapter.__new__(GeminiAdapter)
        adapter._model_name = "gemini-4-carbon"
        adapter._tracker = None
        adapter._estimate_tokens = lambda contents: 20
        adapter._convert_contents = lambda contents: contents
        adapter._build_config = MagicMock(return_value=None)
        adapter._client = MagicMock()
        adapter._client.aio.models.generate_content_stream = AsyncMock(side_effect=lambda **kw: ThoughtThenDrainHangStream())

        brain = _make_brain()
        brain._adapter = adapter
        brain._execute_function_call = AsyncMock(return_value=True)
        with _gate_patch(), _gate_ctx_patch():
            res = await asyncio.wait_for(brain._process_with_llm("evt-cr03", _make_event("evt-cr03")), timeout=0.6)

        assert res is True
        brain._execute_function_call.assert_awaited_once()
        assert brain._execute_function_call.call_args.args[1] == "close_event"
        assert _get_error_turns(brain) == []

        # 2. CR-09: External task.cancel() during post-FC drain raises CancelledError without calling _execute_function_call
        monkeypatch.setenv("LLM_STREAM_TOTAL_TIMEOUT_SEC", "5.0")
        drain_waiting = asyncio.Event()

        class CancelableDrainStream:
            def __init__(self):
                self._idx = 0

            def __aiter__(self):
                return self

            async def __anext__(self):
                if self._idx == 0:
                    self._idx += 1
                    return SimpleNamespace(
                        candidates=[SimpleNamespace(content=SimpleNamespace(parts=[types.Part(function_call=fc)]), grounding_metadata=None)],
                        text=None,
                        function_calls=[fc],
                        usage_metadata=None,
                    )
                drain_waiting.set()
                await asyncio.Event().wait()

        adapter._client.aio.models.generate_content_stream = AsyncMock(side_effect=lambda **kw: CancelableDrainStream())
        brain2 = _make_brain()
        brain2._adapter = adapter
        brain2._execute_function_call = AsyncMock(return_value=True)

        with _gate_patch(), _gate_ctx_patch():
            task = asyncio.create_task(brain2._process_with_llm("evt-cr09", _make_event("evt-cr09")))
            await asyncio.wait_for(drain_waiting.wait(), timeout=0.5)
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task

        brain2._execute_function_call.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_cr03_sliding_window_positive_reset_and_chunk0_short_total_retries_as_ttfb(self, monkeypatch):
        from src.agents.llm import LLMStreamTTFBTimeoutError

        # 1. Positive sliding-window reset: 4 x 0.02s chunks succeed under ttfb=0.04s, inter=0.04s, total=0.40s
        monkeypatch.setenv("LLM_STREAM_TTFB_TIMEOUT_SEC", "0.05")
        monkeypatch.setenv("LLM_STREAM_INTER_CHUNK_TIMEOUT_SEC", "0.05")
        monkeypatch.setenv("LLM_STREAM_TOTAL_TIMEOUT_SEC", "0.40")

        class PacedStream:
            def __aiter__(self):
                async def _gen():
                    for i in range(4):
                        await asyncio.sleep(0.02)
                        yield _Chunk(text=f"part-{i} ", is_thought=(i < 3))
                    yield _Chunk(done=True)

                return _gen()

        brain = _make_brain(stream_factory=lambda **kw: PacedStream())
        with _gate_patch(), _gate_ctx_patch():
            res = await brain._process_with_llm("evt-paced", _make_event("evt-paced"))
        assert res is False
        assert _get_error_turns(brain) == []

        # 2. Chunk-0 timeout when total_timeout < ttfb_timeout still classifies as TTFB and retries once
        monkeypatch.setenv("LLM_STREAM_TTFB_TIMEOUT_SEC", "0.20")
        monkeypatch.setenv("LLM_STREAM_INTER_CHUNK_TIMEOUT_SEC", "0.20")
        monkeypatch.setenv("LLM_STREAM_TOTAL_TIMEOUT_SEC", "0.02")

        calls = 0

        def _hang0(**kw):
            nonlocal calls
            calls += 1
            return MockStream([], hang_after=0)

        brain_short = _make_brain(stream_factory=_hang0)
        with (
            _gate_patch(),
            _gate_ctx_patch(),
            _sleep_patch,
            patch("src.agents.brain.LLMStreamTTFBTimeoutError", wraps=LLMStreamTTFBTimeoutError) as ttfb_spy,
        ):
            await brain_short._process_with_llm("evt-short-total", _make_event("evt-short-total"))
        assert calls == 2
        assert ttfb_spy.call_count == 2

    @pytest.mark.asyncio
    async def test_cr10_ws_brain_thinking_bounds_payload_and_throttles_thought_chunks(self):
        vis_a = "".join(f"alpha{i}_" for i in range(3000))
        vis_b = "".join(f"bravo{i}_" for i in range(3000))
        chunks = [
            _Chunk(text="thought-1 ", is_thought=True),
            _Chunk(text="thought-2 ", is_thought=True),  # back-to-back (< 0.15s) -> throttled
            _Chunk(text=vis_a, is_thought=False),
            _Chunk(text=vis_b, is_thought=False),
            _Chunk(done=True),
        ]
        brain = _make_brain(stream_factory=lambda **kw: MockStream(chunks))
        brain._resolve_llm_params = MagicMock(return_value=("low", 0.7, 65536))
        with _gate_patch(), _gate_ctx_patch():
            await brain._process_with_llm("evt-ws", _make_event("evt-ws"))

        ws_msgs = [
            c.args[0]
            for c in brain._broadcast.call_args_list
            if c.args[0].get("type") == "brain_thinking"
        ]
        thought_msgs = [m for m in ws_msgs if m.get("is_thought") is True and m.get("text")]
        visible_msgs = [m for m in ws_msgs if m.get("is_thought") is False]
        assert len(thought_msgs) == 1, "Rapid consecutive thought chunks within 0.15s must be throttled"
        assert thought_msgs[0]["accumulated"] == "", "is_thought WS frame must not serialize accumulated CoT"
        assert len(visible_msgs) == 2
        assert len(visible_msgs[-1]["accumulated"]) == 32768
        assert "thought-1" not in visible_msgs[-1]["accumulated"]

    def test_cr11_lazy_llm_package_import_ast_boundary_and_misordering_labels(self, monkeypatch, caplog):
        import ast
        import subprocess
        import sys
        from pathlib import Path
        from src.agents.llm.gemini_client import GeminiAdapter

        repo_root = Path(__file__).resolve().parent.parent

        # 1. Fresh subprocess: importing src.agents.llm must NOT load src.agents.llm.gemini_client
        proc = subprocess.run(
            [
                sys.executable,
                "-c",
                "import sys, src.agents.llm; assert 'src.agents.llm.gemini_client' not in sys.modules",
            ],
            cwd=repo_root,
            capture_output=True,
            text=True,
            timeout=60,
        )
        assert proc.returncode == 0, proc.stderr

        # 2. AST check on src/agents/brain.py: zero imports from .llm.gemini_client or .llm.types,
        #    and zero function-local record_token_usage imports
        brain_ast = ast.parse((repo_root / "src" / "agents" / "brain.py").read_text())
        for node in ast.walk(brain_ast):
            if isinstance(node, ast.ImportFrom) and node.module:
                assert node.module not in ("llm.gemini_client", "llm.types", "src.agents.llm.gemini_client", "src.agents.llm.types")
                for alias in node.names:
                    assert alias.name != "record_token_usage", "record_token_usage must not be imported inside hot loop"

        # 3. Accurate timeout misordering labels when LLM_STREAM_CHUNK_TIMEOUT_SEC is unset
        monkeypatch.delenv("LLM_STREAM_CHUNK_TIMEOUT_SEC", raising=False)
        monkeypatch.setenv("LLM_STREAM_TTFB_TIMEOUT_SEC", "50")
        monkeypatch.setenv("LLM_STREAM_INTER_CHUNK_TIMEOUT_SEC", "30")
        monkeypatch.setenv("LLM_STREAM_TOTAL_TIMEOUT_SEC", "40")
        monkeypatch.setenv("LLM_HTTP_TIMEOUT_SEC", "35")
        caplog.clear()
        with patch("google.genai.Client"), caplog.at_level("WARNING", logger="src.agents.llm.gemini_client"):
            GeminiAdapter("proj", "global", "gemini-4-carbon")
        assert "LLM_STREAM_TOTAL_TIMEOUT_SEC (40.0s) >= LLM_HTTP_TIMEOUT_SEC (35.0s)" in caplog.text
        assert "LLM_STREAM_TOTAL_TIMEOUT_SEC (40.0s) < max(" in caplog.text


class TestStreamTimeoutTransientRetryParityAndDocs:
    """ATDD 4-Layer Executable Specification:
    Transient Retry Parity for 408/500/504/INTERNAL/DEADLINE_EXCEEDED,
    Structured Status Code Inspection, Non-Transient 400 Guards,
    Total Timeout Non-Retryability, and Deployment Docs Parity.
    """

    # -------------------------------------------------------------------------
    # Layer 3: Protocol Drivers & Fixtures
    # -------------------------------------------------------------------------
    @staticmethod
    def _invoke_is_transient(exc: Exception) -> bool:
        """Driver invoking Brain._is_transient without side effects."""
        return Brain._is_transient(exc)

    @staticmethod
    def _read_repo_text(relative_path: str) -> str:
        """Driver to read repository text file from repo root."""
        from pathlib import Path
        repo_root = Path(__file__).resolve().parent.parent
        return (repo_root / relative_path).read_text()

    # -------------------------------------------------------------------------
    # Layer 2: Domain-Specific Language (DSL) & Assertions
    # -------------------------------------------------------------------------
    @classmethod
    def assert_transient_classification(cls, exc: Exception, expected: bool = True) -> None:
        actual = cls._invoke_is_transient(exc)
        assert actual is expected, (
            f"Expected Brain._is_transient to return {expected} for {type(exc).__name__}: '{exc}', got {actual}"
        )

    @classmethod
    def assert_structured_status_code_classification(cls, exc: Exception, expected: bool) -> None:
        actual = cls._invoke_is_transient(exc)
        assert actual is expected, (
            f"Expected structured status code on {type(exc).__name__} (attrs={exc.__dict__}) "
            f"to classify as transient={expected}, got {actual}"
        )

    @classmethod
    def assert_no_numeric_substring_false_positive(cls, exc: Exception) -> None:
        actual = cls._invoke_is_transient(exc)
        assert actual is False, (
            f"False-positive transient match detected on non-transient error: '{exc}'. "
            f"Expected False, got {actual}"
        )

    @classmethod
    def assert_timeout_error_never_transient(cls, exc: Exception) -> None:
        actual = cls._invoke_is_transient(exc)
        assert actual is False, (
            f"Timeout error must NEVER be classified as transient (total timeouts are non-retryable): "
            f"'{exc}'. Expected False, got {actual}"
        )

    @classmethod
    async def run_process_with_llm_retry(
        cls, first_exc: Exception, *, expect_success: bool = True
    ) -> tuple[int, list, list[float]]:
        """DSL driving Brain._process_with_llm with transient first attempt and recovery."""
        call_count = 0
        recorded_sleeps: list[float] = []

        def factory(**kw):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise first_exc
            return MockStream([_Chunk(text="recovered")])

        async def _spy_sleep(delay: float):
            recorded_sleeps.append(delay)

        brain = _make_brain(stream_factory=factory)
        event = _make_event("evt-retry-parity")

        with (
            _gate_patch(),
            _gate_ctx_patch(),
            patch("src.agents.brain.asyncio.sleep", new_callable=AsyncMock, side_effect=_spy_sleep),
        ):
            result = await brain._process_with_llm("evt-retry-parity", event)

        error_turns = _get_error_turns(brain)
        return call_count, error_turns, recorded_sleeps

    @classmethod
    def assert_deployment_docs_stream_timeout_parity(cls) -> None:
        deployment_md = cls._read_repo_text("docs/deployment.md")
        helm_readme = cls._read_repo_text("helm/README.md")

        # Required env vars in docs/deployment.md
        for var in (
            "LLM_STREAM_TTFB_TIMEOUT_SEC",
            "LLM_STREAM_INTER_CHUNK_TIMEOUT_SEC",
            "LLM_STREAM_TOTAL_TIMEOUT_SEC",
            "LLM_STREAM_SDK_RETRY_ATTEMPTS",
        ):
            assert var in deployment_md, f"Variable {var} missing from docs/deployment.md"

        # Ordering invariant update in docs/deployment.md
        assert (
            "min(LLM_STREAM_TTFB_TIMEOUT_SEC (35s), LLM_STREAM_INTER_CHUNK_TIMEOUT_SEC (30s))" in deployment_md
            or "min(LLM_STREAM_TTFB_TIMEOUT_SEC" in deployment_md
        ), "Updated two-phase timeout ordering invariant missing from docs/deployment.md"

        # Required helm keys in helm/README.md
        for key in (
            "streamTtfbTimeoutSec",
            "streamInterChunkTimeoutSec",
            "streamTotalTimeoutSec",
            "streamSdkRetryAttempts",
        ):
            assert key in helm_readme, f"Key {key} missing from helm/README.md"

        # Hygiene checks
        for text, fname in [(deployment_md, "docs/deployment.md"), (helm_readme, "helm/README.md")]:
            assert "redhat.com" not in text, f"Internal redhat.com reference found in {fname}"
            assert "/Users/" not in text, f"Local workstation path found in {fname}"

    # -------------------------------------------------------------------------
    # Layer 1: Executable Scenarios (T-1, T-2, T-3, T-4, T-9)
    # -------------------------------------------------------------------------
    @pytest.mark.asyncio
    async def test_t1_transient_classification_and_process_with_llm_retry_loop(self):
        """T-1: Transient classification & Brain._process_with_llm retry loop for HTTP 408, 500, 504
        and gRPC INTERNAL, DEADLINE_EXCEEDED with base=5s backoff.
        """
        transient_errors = [
            Exception("408 Request Timeout"),
            Exception("500 Internal Server Error"),
            Exception("504 Gateway Timeout"),
            Exception("INTERNAL: internal error occurred"),
            Exception("DEADLINE_EXCEEDED: deadline exceeded"),
        ]

        for exc in transient_errors:
            self.assert_transient_classification(exc, expected=True)

        # Verify retry loop and base=5s backoff tier in _process_with_llm
        call_count, error_turns, sleeps = await self.run_process_with_llm_retry(
            Exception("500 Internal Server Error")
        )
        assert call_count == 2, f"Expected 2 attempts (1 failure + 1 retry), got {call_count}"
        assert len(error_turns) == 0, f"Expected 0 error turns on successful retry, got {error_turns}"
        assert len(sleeps) == 1, f"Expected 1 sleep call for backoff, got {len(sleeps)}"
        # base = 5.0 -> backoff = 5.0 * 2^0 + [0.5, 2.0] = [5.5, 7.0] (not rate-limit base 30s)
        assert 5.0 <= sleeps[0] <= 8.0, f"Expected non-rate-limit backoff (5.0s..8.0s), got {sleeps[0]}"

    def test_t2_structured_status_code_inspection(self):
        """T-2: Structured status code inspection (.code, .status_code, callable .code(), .status)
        for transient (408, 429, 500, 502, 503, 504, 529) vs client non-transient (400, 401, 403, 404).
        """
        class _AttrErr(Exception):
            def __init__(self, msg, **kwargs):
                super().__init__(msg)
                for k, v in kwargs.items():
                    setattr(self, k, v)

        class _CallableCodeErr(Exception):
            def __init__(self, msg, code_fn):
                super().__init__(msg)
                self.code = code_fn

        # Structured transient codes
        for code in (408, 429, 500, 502, 503, 504, 529):
            self.assert_structured_status_code_classification(_AttrErr("api error", code=code), True)
            self.assert_structured_status_code_classification(_AttrErr("api error", status_code=code), True)
            self.assert_structured_status_code_classification(_AttrErr("api error", status=code), True)
            self.assert_structured_status_code_classification(_CallableCodeErr("rpc error", lambda c=code: c), True)

        # Structured non-transient client codes
        for code in (400, 401, 403, 404):
            self.assert_structured_status_code_classification(_AttrErr("client error", code=code), False)
            self.assert_structured_status_code_classification(_AttrErr("client error", status_code=code), False)
            self.assert_structured_status_code_classification(_CallableCodeErr("rpc error", lambda c=code: c), False)

        # Graceful handling of callable that raises
        def _failing_code():
            raise RuntimeError("code uncallable")

        self.assert_structured_status_code_classification(
            _CallableCodeErr("503 service unavailable", _failing_code), True
        )

    def test_t3_non_transient_400_and_large_number_false_positive_guard(self):
        """T-3: Non-transient 400 INVALID_ARGUMENT or ValueError containing "65000", "5000", "1500",
        or evt-500a1b / evt-408xyz returns False (no false-positive substring match on 500/408).
        """
        non_transient_cases = [
            Exception("400 INVALID_ARGUMENT: max_output_tokens 65000 exceeds limit for evt-500a1b"),
            ValueError("Invalid port 5000 in config for evt-408xyz"),
            Exception("max_output_tokens 1500 is not allowed"),
            Exception("Event evt-500000 failed validation"),
            Exception("400 INVALID_ARGUMENT: request for 42900 tokens rejected"),
            Exception("400 INVALID_ARGUMENT: INTERNAL error in user payload"),
        ]
        for exc in non_transient_cases:
            self.assert_no_numeric_substring_false_positive(exc)

    def test_t4_direct_is_transient_total_timeout_returns_false(self):
        """T-4: Direct Brain._is_transient(LLMStreamTotalTimeoutError("... (500.0s) for evt-500abc"))
        returns False, and TimeoutError never classifies as transient.
        """
        from src.agents.llm import LLMStreamTotalTimeoutError

        self.assert_timeout_error_never_transient(
            LLMStreamTotalTimeoutError("LLM stream total timeout (500.0s) for evt-500abc")
        )
        self.assert_timeout_error_never_transient(
            asyncio.TimeoutError("Timeout after 500.0s for evt-500abc")
        )
        self.assert_timeout_error_never_transient(
            LLMStreamTotalTimeoutError("LLM stream total timeout (502.0s) for evt-502abc")
        )

    def test_t9_docs_and_helm_readme_stream_timeout_parity(self):
        """T-9: docs/deployment.md and helm/README.md contain all 4 new env vars and updated
        stream timeout ordering invariant.
        """
        self.assert_deployment_docs_stream_timeout_parity()

    @pytest.mark.asyncio
    async def test_cr01_rate_limit_structured_and_token_boundary(self):
        """T-10: Brain._is_rate_limit structured status code vs token-bounded '429' matching,
        and _process_with_llm backoff tier selection (base=5s vs base=30s).
        """
        from src.agents.llm import QuotaExhaustedError

        class _StructuredRateLimitErr(Exception):
            def __init__(self, msg: str, *, code=None, status_code=None):
                super().__init__(msg)
                if code is not None:
                    self.code = code
                if status_code is not None:
                    self.status_code = status_code

        # False-positive substrings ('evt-429abc', '42900', '0.429s') must NOT classify as rate-limit
        assert Brain._is_rate_limit(
            RuntimeError("500 Internal Server Error for evt-429abc (42900 tokens)")
        ) is False
        assert Brain._is_rate_limit(RuntimeError("took 0.429s")) is False

        # Structured 429 without literal "429" in str(e), QuotaExhaustedError, and bounded "HTTP 429" -> True
        assert Brain._is_rate_limit(
            _StructuredRateLimitErr("Rate limit exceeded", code=429)
        ) is True
        assert Brain._is_rate_limit(
            _StructuredRateLimitErr("Rate limit exceeded", status_code=429)
        ) is True
        assert Brain._is_rate_limit(QuotaExhaustedError("exhausted")) is True
        assert Brain._is_rate_limit(RuntimeError("HTTP 429 Too Many Requests")) is True

        # In Brain._process_with_llm: 500 error for evt-429abc uses non-rate-limit tier (5.0 <= delay <= 6.5)
        calls_non_rl, errors_non_rl, sleeps_non_rl = await self.run_process_with_llm_retry(
            RuntimeError("500 Internal Server Error for evt-429abc")
        )
        assert calls_non_rl == 2
        assert errors_non_rl == []
        assert len(sleeps_non_rl) == 1
        assert 5.0 <= sleeps_non_rl[0] <= 6.5, (
            f"Expected non-rate-limit backoff [5.0, 6.5] for evt-429abc 500 error, got {sleeps_non_rl[0]}"
        )

        # In Brain._process_with_llm: structured .code = 429 error uses rate-limit tier (30.0 <= delay <= 39.0)
        calls_rl, errors_rl, sleeps_rl = await self.run_process_with_llm_retry(
            _StructuredRateLimitErr("Rate limit reached", code=429)
        )
        assert calls_rl == 2
        assert errors_rl == []
        assert len(sleeps_rl) == 1
        assert 30.0 <= sleeps_rl[0] <= 39.0, (
            f"Expected rate-limit backoff [30.0, 39.0] for structured .code=429, got {sleeps_rl[0]}"
        )

    def test_cr02_cr03_float_4xx_and_529_boundaries(self):
        """T-11: Float durations (.500, .504, .429), unstructured 529, structured 4xx outside
        {400, 401, 403, 404}, unstructured 4xx mentioning transient tokens/codes, and broken .code getter.
        """
        class _StructuredClientErr(Exception):
            def __init__(self, msg: str, **kwargs):
                super().__init__(msg)
                for k, v in kwargs.items():
                    setattr(self, k, v)

        class _BrokenCodePropertyErr(Exception):
            @property
            def code(self):
                raise RuntimeError("broken getter")

        # 1. Float strings with .500 / .502 / .503 / .504 / .408 / .429 -> False
        for float_err in (
            RuntimeError("request failed after 0.500s"),
            RuntimeError("latency 1.502s"),
            RuntimeError("elapsed 2.503s"),
            RuntimeError("latency 1.504s"),
            RuntimeError("duration 0.408s"),
            RuntimeError("took 0.429s"),
        ):
            self.assert_transient_classification(float_err, expected=False)

        # 2. Unstructured HTTP 529 -> True
        self.assert_transient_classification(
            RuntimeError("HTTP 529 Site is overloaded"), expected=True
        )

        # 3. Structured 4xx exceptions outside {400, 401, 403, 404} -> False even if msg mentions 500 or INTERNAL
        for client_exc in (
            _StructuredClientErr("Unprocessable entity: field 500 invalid", code=422),
            _StructuredClientErr("Conflict: INTERNAL state mismatch 500", status_code=409),
            _StructuredClientErr("Payload too large: 500MB limit", status=413),
        ):
            self.assert_structured_status_code_classification(client_exc, expected=False)

        # 4. Unstructured 4xx client errors mentioning numbers or transient keywords -> False
        for unstruct_4xx in (
            RuntimeError("404 NOT_FOUND: user 500 does not exist"),
            RuntimeError("403 PERMISSION_DENIED: INTERNAL policy check failed"),
            RuntimeError("401 UNAUTHENTICATED: token 502 rejected"),
        ):
            self.assert_transient_classification(unstruct_4xx, expected=False)

        # 5. Exception whose .code property raises on access falls through cleanly without crashing
        self.assert_transient_classification(
            _BrokenCodePropertyErr("503 Service Unavailable"), expected=True
        )
        self.assert_transient_classification(
            _BrokenCodePropertyErr("Permanent client validation failure"), expected=False
        )



