# tests/test_brain_steering_recovery.py
# @ai-rules:
# 1. [Constraint]: Acceptance tests for Brain context-aligned steering recovery & Slack isolation (VMER-2398 / T-3, T-4).
# 2. [Pattern]: Uses lightweight Brain and MockStream pattern from test_wait_for_user_idle_timeout.py. No live LLM or Redis.
# 3. [Contract]: Empty sanitized LLM output without tool calls must inject turn=0 steering turn and re-enter loop (<= 2 retries).
# 4. [Security]: ("system", "steering") in _INTERNAL_TURNS guarantees steering turns never leak into user Slack channels.
"""Unit and acceptance tests for Brain context-aligned steering recovery and Slack isolation."""
from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from typing import Any, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.agents.llm.types import FunctionCall
from src.models import (
    ConversationTurn,
    EventDocument,
    EventEvidence,
    EventInput,
    EventStatus,
)


@dataclass
class _Chunk:
    text: Optional[str] = None
    function_call: Optional[FunctionCall] = None
    raw_parts: Any = None
    grounding_metadata: Any = None
    usage: Any = None
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


def _make_event(
    event_id: str = "evt-steer-01",
    source: str = "slack",
    service: str = "test-svc",
    brain_phase: str = "dispatch",
    domain: str = "complicated",
) -> EventDocument:
    evidence = EventEvidence(
        display_text="Test prompt",
        source_type=source,
        domain=domain,
        severity="info",
    )
    return EventDocument(
        id=event_id,
        source=source,
        service=service,
        brain_phase=brain_phase,
        status=EventStatus.ACTIVE,
        event=EventInput(reason="test", evidence=evidence),
        conversation=[],
    )


def _make_brain(stream_factory):
    from src.agents.brain import Brain

    bb = MagicMock()
    bb.get_event = AsyncMock(return_value=_make_event())
    bb.get_active_events = AsyncMock(return_value=[])
    bb.get_recent_closed_for_service = AsyncMock(return_value=[])
    bb.append_turn = AsyncMock(return_value=1)
    bb.mark_turn_status = AsyncMock()
    bb.stamp_event = AsyncMock()
    bb.redis = MagicMock()
    bb.redis.get = AsyncMock(return_value=None)
    bb.redis.delete = AsyncMock(return_value=1)

    brain = Brain(blackboard=bb, agents={})
    brain._empty_output_retries = {}

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
    brain._emit_thinking_pulse = AsyncMock()
    brain._emit_executive_pulse = AsyncMock()
    brain._idle_timeout = MagicMock()
    brain._idle_timeout.schedule = MagicMock()

    return brain


class TestBrainSteeringRecovery:
    """T-3: Brain context-aligned steering recovery when LLM text scrubs to empty without tool calls."""

    @pytest.mark.asyncio
    async def test_empty_clean_text_suppresses_response_and_injects_steering_turn(self):
        """T-3: When clean text is empty without tool calls, Brain suppresses response turn, does not park, and injects turn=0 steering turn."""
        # Chunks produce text that cleans to None (only control tokens)
        chunks = [_Chunk(text="<end_of_image>")]
        brain = _make_brain(stream_factory=lambda **kw: MockStream(chunks))
        event = _make_event(event_id="evt-empty-01", brain_phase="dispatch", domain="complicated")

        with patch("src.agents.brain.sanitize_call_syntax", return_value=None):
            should_continue = await brain._process_with_llm("evt-empty-01", event, response_emitted=False)

        # Must re-enter processing loop immediately with steering guidance
        assert should_continue is True

        # Must NOT park event in _waiting_for_user
        assert "evt-empty-01" not in brain._waiting_for_user

        # Inspect appended turns: no "response" turn, exactly one "steering" turn
        appended_turns = [call.args[1] for call in brain._append_and_broadcast.call_args_list]
        response_turns = [t for t in appended_turns if t.action == "response"]
        assert len(response_turns) == 0, "Spurious public response turn was emitted"

        steering_turns = [t for t in appended_turns if t.action == "steering"]
        assert len(steering_turns) == 1, "Expected exactly one internal steering turn"

        steering_turn = steering_turns[0]
        assert steering_turn.actor == "system"
        assert steering_turn.action == "steering"
        assert steering_turn.turn == 0  # Atomic assignment in append_turn
        assert "dispatch" in steering_turn.thoughts
        assert "complicated" in steering_turn.thoughts
        assert "Eligible tools" in steering_turn.thoughts

        # Counter updated
        assert brain._empty_output_retries.get("evt-empty-01") == 1

    @pytest.mark.asyncio
    async def test_bounded_retries_caps_at_two_and_breaks_on_third(self):
        """T-3: Retry counter permits <= 2 retries; 3rd empty response pops counter and returns False."""
        chunks = [_Chunk(text="<end_of_image>")]
        brain = _make_brain(stream_factory=lambda **kw: MockStream(chunks))
        event = _make_event(event_id="evt-retry-01")

        with patch("src.agents.brain.sanitize_call_syntax", return_value=None):
            # Attempt 1 -> retry 1, should_continue = True
            res1 = await brain._process_with_llm("evt-retry-01", event, response_emitted=False)
            assert res1 is True
            assert brain._empty_output_retries.get("evt-retry-01") == 1

            # Attempt 2 -> retry 2, should_continue = True
            res2 = await brain._process_with_llm("evt-retry-01", event, response_emitted=False)
            assert res2 is True
            assert brain._empty_output_retries.get("evt-retry-01") == 2

            # Attempt 3 -> exceeded cap, pops counter, should_continue = False
            res3 = await brain._process_with_llm("evt-retry-01", event, response_emitted=False)
            assert res3 is False
            assert "evt-retry-01" not in brain._empty_output_retries

    @pytest.mark.asyncio
    async def test_counter_resets_on_clean_text_response(self):
        """T-3: Clean text turn resets _empty_output_retries counter."""
        chunks = [_Chunk(text="Proceeding with deployment plan.")]
        brain = _make_brain(stream_factory=lambda **kw: MockStream(chunks))
        event = _make_event(event_id="evt-reset-01")
        brain._empty_output_retries["evt-reset-01"] = 2

        with patch("src.agents.brain.sanitize_call_syntax", return_value="Proceeding with deployment plan."):
            res = await brain._process_with_llm("evt-reset-01", event, response_emitted=False)

        assert res is False
        assert "evt-reset-01" not in brain._empty_output_retries

    @pytest.mark.asyncio
    async def test_counter_resets_on_function_call(self):
        """T-3: Function call return path resets _empty_output_retries counter."""
        fc = FunctionCall(name="set_phase", args={"phase": "verify"})
        chunks = [_Chunk(function_call=fc)]
        brain = _make_brain(stream_factory=lambda **kw: MockStream(chunks))
        event = _make_event(event_id="evt-reset-fc")
        brain._empty_output_retries["evt-reset-fc"] = 2
        brain._execute_function_call = AsyncMock(return_value=True)

        await brain._process_with_llm("evt-reset-fc", event, response_emitted=False)

        assert "evt-reset-fc" not in brain._empty_output_retries


class TestSlackSteeringSuppression:
    """T-4: Slack channel isolation of internal steering turns."""

    def test_system_steering_in_internal_turns_set(self):
        """T-4: ("system", "steering") is in _INTERNAL_TURNS in src.channels.slack."""
        from src.channels.slack import _INTERNAL_TURNS

        assert ("system", "steering") in _INTERNAL_TURNS
