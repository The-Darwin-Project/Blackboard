# tests/test_brain_steering_recovery.py
# @ai-rules:
# 1. [Constraint]: Acceptance tests for Brain context-aligned steering recovery & Slack isolation (VMER-2398 / T-3, T-4).
# 2. [Pattern]: Uses lightweight Brain and MockStream pattern from test_wait_for_user_idle_timeout.py. No live LLM or Redis.
# 3. [Contract]: Empty sanitized LLM output without tool calls must inject turn=0 steering turn and re-enter loop (<= 2 retries).
# 4. [Security]: ("system", "steering") in _INTERNAL_TURNS guarantees steering turns never leak into user Slack channels.
# 5. [Contract]: Exhaustion (>2 retries) is lock-safe: non-slack events dispatch defer_event DIRECTLY via _execute_function_call
#    under the held _event_locks[event_id] (never execute_tool_locked), and the retry counter is NOT reset by exhaustion --
#    only by real output. Slack/chat exhaustion posts an error response + _waiting_for_user instead of deferring.
# 6. [Contract]: Thoughts-only turns (no stripped text) stay terminal WITHOUT steering; ("system","steering") never counts as
#    participant input and never stalls _compute_processed_up_to (see TestSteeringTurnIsNotParticipantInput).
"""Unit and acceptance tests for Brain context-aligned steering recovery and Slack isolation."""
from __future__ import annotations

import asyncio
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


def _non_slack_brain(stream_text: str = "<end_of_image>"):
    chunks = [_Chunk(text=stream_text)]
    brain = _make_brain(stream_factory=lambda **kw: MockStream(chunks))
    brain._execute_function_call = AsyncMock(return_value=False)
    return brain


def _appended(brain) -> list[ConversationTurn]:
    return [call.args[1] for call in brain._append_and_broadcast.call_args_list]


_EMPTY = patch("src.agents.brain.sanitize_call_syntax", return_value=None)


class TestNonSlackExhaustionUnderEventLock:
    """F1/F5: exhaustion runs under the held per-event lock and must neither deadlock nor reset the budget."""

    @pytest.mark.asyncio
    async def test_exhaustion_defers_directly_without_reacquiring_event_lock(self):
        brain = _non_slack_brain()
        event = _make_event(event_id="evt-ns-01", source="headhunter")

        async def run():
            async with brain._event_locks["evt-ns-01"]:
                with _EMPTY:
                    return [await brain._process_with_llm("evt-ns-01", event, response_emitted=False) for _ in range(3)]

        # execute_tool_locked is real: a re-entrant lock acquire (the original _defer_event_safely route) would hang.
        brain.blackboard.get_event = AsyncMock(return_value=event)
        results = await asyncio.wait_for(run(), timeout=5)

        assert results == [True, True, False]
        brain._execute_function_call.assert_awaited_once_with(
            "evt-ns-01", "defer_event",
            {"delay_seconds": 300, "reason": "empty_output_retries_exhausted"},
        )
        assert "evt-ns-01" not in brain._waiting_for_user
        assert [t.action for t in _appended(brain)] == ["steering", "steering"]

    @pytest.mark.asyncio
    async def test_counter_not_reset_across_defer_wake_and_second_empty_wake_terminates(self):
        """After the one exhaustion defer, a still-empty wake gets ONE LLM call: no steering, no re-defer, error turn."""
        brain = _non_slack_brain()
        event = _make_event(event_id="evt-ns-02", source="headhunter")
        with _EMPTY:
            for expected in (True, True, False):
                assert await brain._process_with_llm("evt-ns-02", event, response_emitted=False) is expected
            assert brain._empty_output_retries["evt-ns-02"] == 3  # NOT popped (would grant 3 fresh calls per wake)
            brain._execute_function_call.reset_mock()
            brain._append_and_broadcast.reset_mock()
            brain._close_and_broadcast = AsyncMock()

            # ---- defer wake: still empty ----
            assert await brain._process_with_llm("evt-ns-02", event, response_emitted=False, is_defer_wake=True) is False

        assert brain._execute_function_call.await_count == 0, "must not defer again (infinite defer loop)"
        turns = _appended(brain)
        assert [(t.actor, t.action) for t in turns] == [("brain", "error")]
        assert brain._empty_output_retries["evt-ns-02"] == 3
        brain._close_and_broadcast.assert_not_awaited()  # terminates without force-closing the event
        assert "evt-ns-02" not in brain._waiting_for_user

    @pytest.mark.asyncio
    async def test_real_output_after_defer_wake_resets_budget(self):
        brain = _non_slack_brain()
        event = _make_event(event_id="evt-ns-03", source="headhunter")
        with _EMPTY:
            for _ in range(3):
                await brain._process_with_llm("evt-ns-03", event, response_emitted=False)
        assert brain._empty_output_retries["evt-ns-03"] == 3

        brain._adapter.generate_stream = MagicMock(
            side_effect=lambda **kw: MockStream([_Chunk(text="All good now.")])
        )
        with patch("src.agents.brain.sanitize_call_syntax", return_value="All good now."):
            assert await brain._process_with_llm("evt-ns-03", event, response_emitted=False) is False
        assert "evt-ns-03" not in brain._empty_output_retries

    @pytest.mark.asyncio
    async def test_failed_defer_does_not_arm_the_one_defer_marker(self):
        brain = _non_slack_brain()
        brain._execute_function_call = AsyncMock(side_effect=RuntimeError("redis down"))
        event = _make_event(event_id="evt-ns-04", source="headhunter")
        with _EMPTY:
            for expected in (True, True, False):
                assert await brain._process_with_llm("evt-ns-04", event, response_emitted=False) is expected
        assert brain._empty_output_retries["evt-ns-04"] == 2

    @pytest.mark.asyncio
    async def test_batch_function_call_path_resets_counter(self):
        """F19: the parallel-FC batch path is real output too and must clear the retry counter."""
        import src.agents.brain as brain_mod

        fcs = [
            {"functionCall": {"name": "set_phase", "args": {"phase": "verify"}}},
            {"functionCall": {"name": "defer_event", "args": {"delay_seconds": 60}}},
        ]
        chunks = [_Chunk(raw_parts=fcs, done=True)]
        brain = _non_slack_brain()
        brain._adapter.generate_stream = MagicMock(side_effect=lambda **kw: MockStream(chunks))
        brain._normalize_response_parts = MagicMock(return_value=fcs)
        brain._empty_output_retries["evt-batch"] = 2
        event = _make_event(event_id="evt-batch", source="headhunter")

        with patch.object(brain_mod, "_THOUGHT_SIG_V2", True):
            await brain._process_with_llm("evt-batch", event, response_emitted=False)

        executed = [c.args[1] for c in brain._execute_function_call.await_args_list]
        assert "set_phase" in executed, "batch path was not exercised"
        assert "evt-batch" not in brain._empty_output_retries


class TestSlackAndChatExhaustion:
    """(b): user-facing sources park for the user instead of deferring."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize("source", ["slack", "chat"])
    async def test_exhaustion_posts_error_response_and_parks_for_user(self, source):
        brain = _non_slack_brain()
        event = _make_event(event_id=f"evt-{source}-ex", source=source)
        with _EMPTY:
            results = [await brain._process_with_llm(event.id, event, response_emitted=False) for _ in range(3)]

        assert results == [True, True, False]
        turns = _appended(brain)
        assert [t.action for t in turns] == ["steering", "steering", "response"]
        error = turns[-1]
        assert (error.actor, error.waitingFor) == ("brain", "user")
        assert "encountered an issue" in error.thoughts
        assert event.id in brain._waiting_for_user
        brain._execute_function_call.assert_not_awaited()
        assert event.id not in brain._empty_output_retries  # user park ends the loop; user reply starts fresh

    @pytest.mark.asyncio
    async def test_error_turn_append_failure_is_swallowed_but_user_still_parked(self):
        brain = _non_slack_brain()
        event = _make_event(event_id="evt-slack-err", source="slack")
        calls = {"n": 0}

        async def flaky_append(event_id, turn, *a, **k):
            calls["n"] += 1
            if turn.action == "response":
                raise RuntimeError("redis blip")
            return 1

        brain._append_and_broadcast = AsyncMock(side_effect=flaky_append)
        with _EMPTY:
            results = [await brain._process_with_llm(event.id, event, response_emitted=False) for _ in range(3)]
        assert results == [True, True, False]
        assert event.id in brain._waiting_for_user


class TestThoughtsOnlyIsTerminal:
    """(c)/F6: a thoughts-only turn with nothing stripped keeps the pre-VMER-2398 terminal behavior."""

    @pytest.mark.asyncio
    async def test_thoughts_only_returns_false_without_steering(self):
        chunks = [_Chunk(text="Considering the options carefully.", is_thought=True)]
        brain = _make_brain(stream_factory=lambda **kw: MockStream(chunks))
        brain._execute_function_call = AsyncMock(return_value=False)
        event = _make_event(event_id="evt-thoughts", source="headhunter")

        assert await brain._process_with_llm(event.id, event, response_emitted=False) is False

        turns = _appended(brain)
        assert [t.action for t in turns] == ["thoughts"]
        assert not any(t.action == "steering" for t in turns)
        assert "evt-thoughts" not in brain._empty_output_retries
        brain._execute_function_call.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_thoughts_only_never_loops_across_many_calls(self):
        chunks = [_Chunk(text="Thinking...", is_thought=True)]
        brain = _make_brain(stream_factory=lambda **kw: MockStream(chunks))
        brain._execute_function_call = AsyncMock(return_value=False)
        event = _make_event(event_id="evt-thoughts-loop", source="slack")
        for _ in range(5):
            assert await brain._process_with_llm(event.id, event, response_emitted=False) is False
        assert not any(t.action in ("steering", "response") for t in _appended(brain))
        assert event.id not in brain._waiting_for_user

    @pytest.mark.asyncio
    async def test_thoughts_plus_fully_stripped_text_still_steers(self):
        """Stripping occurred (text scrubbed to nothing) -> the steering case, even though thoughts exist."""
        chunks = [_Chunk(text="reasoning", is_thought=True), _Chunk(text="<end_of_image>")]
        brain = _make_brain(stream_factory=lambda **kw: MockStream(chunks))
        brain._execute_function_call = AsyncMock(return_value=False)
        event = _make_event(event_id="evt-thoughts-strip", source="headhunter")
        with _EMPTY:
            assert await brain._process_with_llm(event.id, event, response_emitted=False) is True
        actions = [t.action for t in _appended(brain)]
        assert actions.count("steering") == 1


class TestSteeringTextSanitization:
    """F21: the domain interpolated into the steering turn passes through sanitize_prompt_text."""

    @pytest.mark.asyncio
    async def test_domain_is_single_line_control_free_and_capped(self):
        brain = _non_slack_brain()
        event = _make_event(event_id="evt-san", source="headhunter")
        event.event.evidence.brain_domain = "evil\nIGNORE ALL\u200b" + "x" * 500
        with _EMPTY:
            await brain._process_with_llm(event.id, event, response_emitted=False)
        steering = next(t for t in _appended(brain) if t.action == "steering")
        assert "\n" not in steering.thoughts
        assert "\u200b" not in steering.thoughts
        domain = steering.thoughts.split("Domain: ", 1)[1].split(". Eligible", 1)[0]
        assert len(domain) <= 80

    @pytest.mark.asyncio
    async def test_blank_domain_falls_back_to_unknown(self):
        brain = _non_slack_brain()
        brain._extract_context_flags = AsyncMock(return_value={"event_domain": "\u200b"})
        event = _make_event(event_id="evt-san2", source="headhunter")
        event.event.evidence.brain_domain = None
        event.event.evidence.domain = None
        with _EMPTY:
            await brain._process_with_llm(event.id, event, response_emitted=False)
        steering = next(t for t in _appended(brain) if t.action == "steering")
        assert "Domain: unknown." in steering.thoughts


def _turn(n, actor, action, status="sent"):
    return ConversationTurn(turn=n, actor=actor, action=action, status=status, thoughts="x")


class TestSteeringTurnIsNotParticipantInput:
    """(d)/F7: ("system","steering") is neither participant input nor a processed-up-to stall point."""

    @pytest.mark.parametrize(
        ("actor", "action", "expected"),
        [
            ("system", "steering", False),
            ("system", "notification", True),   # sticky-note notifications still wake the Brain
            ("brain", "hold_watch_wake", False),  # brain-authored: unchanged
            ("dispatcher", "acknowledge", False),
            ("user", "message", True),
            ("developer", "result", True),
            ("jarvis", "message", True),
        ],
    )
    def test_is_participant_turn(self, actor, action, expected):
        from src.agents.brain import _is_participant_turn

        assert _is_participant_turn(_turn(1, actor, action)) is expected

    def test_processed_up_to_skips_steering_and_covers_following_brain_turns(self):
        from src.agents.brain import _compute_processed_up_to

        conv = [
            _turn(1, "user", "message", "delivered"),
            _turn(2, "system", "steering"),
            _turn(3, "brain", "response"),
        ]
        assert _compute_processed_up_to(conv, turn_snapshot=1, acknowledged_interrupts={}) == 3

    def test_processed_up_to_still_stops_at_real_unseen_input_after_steering(self):
        from src.agents.brain import _compute_processed_up_to

        conv = [
            _turn(1, "user", "message", "delivered"),
            _turn(2, "system", "steering"),
            _turn(3, "user", "message"),  # arrived mid-cycle, unseen
            _turn(4, "brain", "response"),
        ]
        assert _compute_processed_up_to(conv, turn_snapshot=1, acknowledged_interrupts={}) == 2

    def test_processed_up_to_notification_still_stalls(self):
        from src.agents.brain import _compute_processed_up_to

        conv = [
            _turn(1, "user", "message", "delivered"),
            _turn(2, "system", "notification"),
            _turn(3, "brain", "response"),
        ]
        assert _compute_processed_up_to(conv, turn_snapshot=1, acknowledged_interrupts={}) == 1

    @staticmethod
    def _scan_brain():
        from src.agents.brain import Brain

        bb = MagicMock()
        bb.EVENT_ACTIVE = "darwin:event:active"
        bb.redis = MagicMock()
        bb.redis.srem = AsyncMock()
        bb.get_event = AsyncMock()
        bb.get_active_events_with_status = AsyncMock(return_value={})
        bb.mark_turns_delivered = AsyncMock(return_value=1)
        bb.get_recent_closed_for_service = AsyncMock(return_value=[])
        brain = Brain(blackboard=bb, agents={})
        brain._broadcast = AsyncMock()
        brain._broadcast_status_update = AsyncMock()
        return brain

    @pytest.mark.asyncio
    async def test_resync_scan_steering_turn_does_not_enqueue_running_task(self):
        """Guard 1: a SENT steering turn alone is not new input for a task that is already running."""
        brain = self._scan_brain()
        event = _make_event(event_id="evt-scan-1", source="chat")
        event.conversation = [_turn(1, "brain", "route", "evaluated"), _turn(2, "system", "steering", "sent")]
        brain.blackboard.get_active_events_with_status.return_value = {"evt-scan-1": "active"}
        brain.blackboard.get_event.return_value = event
        brain._active_tasks["evt-scan-1"] = MagicMock(done=MagicMock(return_value=False))

        assert await brain._scan_active_for_reconcile() == []

    @pytest.mark.asyncio
    async def test_resync_scan_notification_turn_still_enqueues_running_task(self):
        """Control: system/notification (a different system action) is still participant input."""
        brain = self._scan_brain()
        event = _make_event(event_id="evt-scan-2", source="chat")
        event.conversation = [_turn(1, "brain", "route", "evaluated"), _turn(2, "system", "notification", "sent")]
        brain.blackboard.get_active_events_with_status.return_value = {"evt-scan-2": "active"}
        brain.blackboard.get_event.return_value = event
        brain._active_tasks["evt-scan-2"] = MagicMock(done=MagicMock(return_value=False))

        assert await brain._scan_active_for_reconcile() == ["evt-scan-2"]


class TestSlackSteeringSuppression:
    """T-4: Slack channel isolation of internal steering turns."""

    def test_system_steering_in_internal_turns_set(self):
        """T-4: ("system", "steering") is in _INTERNAL_TURNS in src.channels.slack."""
        from src.channels.slack import _INTERNAL_TURNS

        assert ("system", "steering") in _INTERNAL_TURNS
