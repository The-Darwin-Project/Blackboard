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
    @pytest.mark.parametrize("env,expected", [(None, 180.0), ("nan", 180.0), ("0", 180.0), ("-3", 180.0), ("7.5", 7.5)])
    async def test_brain_chunk_timeout_parsing(self, monkeypatch, env, expected):
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
