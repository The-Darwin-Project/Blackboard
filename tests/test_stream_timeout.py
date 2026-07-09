# tests/test_stream_timeout.py
# @ai-rules:
# 1. [Constraint]: No Redis -- MagicMock blackboard only.
# 2. [Pattern]: Direct _process_with_llm tests with targeted stubs (matches test_task_lifecycle_ordering.py).
# 3. [Pattern]: AsyncMock adapter with MockStream for controlled async iteration.
# 4. [Gotcha]: LLM_STREAM_CHUNK_TIMEOUT_SEC=2 for fast tests. asyncio.sleep patched for retry/backoff speed.
# 5. [Invariant]: 3-level nesting: OUTER Exception > MIDDLE TimeoutError > INNER StopAsyncIteration.
# 6. [Pattern]: _ACLOSE_TIMEOUT patched to 0.1s in test_10 for fast cleanup hang tests.
"""Verify per-chunk stream timeout guard in _process_with_llm.

Tests cover:
- Core timeout detection (0 chunks, partial chunks, normal completion)
- Retry-once policy (independent timeout_retries counter)
- Generator cleanup (aclose called, bounded cleanup on hang)
- Reflex factory (fresh instances per retry)
"""
from __future__ import annotations

import asyncio
import os
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
