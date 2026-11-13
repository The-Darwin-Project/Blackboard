# BlackBoard/tests/test_quota_shedding.py
# @ai-rules:
# 1. [Constraint]: Pure unit and integration tests for two-tier quota shedding in _process_with_llm.
# 2. [Pattern]: Follows Dave Farley's 4-layer ATDD model (T-7, T-8, CR-01..CR-06).
# 3. [Boundary]: Mock adapter stream and asyncio.sleep — no network calls, zero sleep delay.
# 4. [Policy]: LOCAL QuotaExhaustedError/RequestExceedsBurstError + Tier-1 shrink => zero-sleep retry (the tracker already
#    paced local capacity). UPSTREAM 429/resource_exhausted => bounded 2**attempt backoff (30/60/120s + jitter), always.
"""Executable specifications for two-tier dynamic token shedding in Brain._process_with_llm (T-7, T-8).

Dave Farley 4-Layer ATDD Model:
  Layer 1 (Domain Intent): Given QuotaExhaustedError / RequestExceedsBurstError
    When retry loop executes
    Then Tier 1 immediate decay shed executed on attempt 0 (no 30s sleep)
    and Tier 2 progressive tail halving executed on attempt 1 with backoff sleep.
  Layer 2 (DSL): Conversation and brain fixture synthesis with heavy historical evidence.
  Layer 3 (Protocol Driver): Direct invocation of Brain._process_with_llm with mocked LLM stream.
  Layer 4 (SUT): src.agents.brain.Brain._process_with_llm.
"""
from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.agents.brain import BRAIN_PREFILL_MODEL, BRAIN_PREFILL_USER, Brain
from src.agents.context_parts import estimate_tokens
from src.agents.llm.quota_tracker import QuotaExhaustedError, RequestExceedsBurstError
from src.models import (
    ConversationTurn,
    EventDocument,
    EventEvidence,
    EventInput,
    EventStatus,
)


# ---------------------------------------------------------------------------
# Layer 2: DSL Helpers
# ---------------------------------------------------------------------------

def _make_shedding_event(event_id: str = "evt-shed-test") -> EventDocument:
    """Build an event with 15 conversation turns including multi-KB historical tool evidence.

    Turns 10, 12, 14 carry ~25,000 chars each so post-Tier-1 the recent turns still
    contain >25k tokens, forcing real tail_budget pruning in Tier 2.
    """
    turns: list[ConversationTurn] = []
    for i in range(1, 15):
        if i % 2 == 1:
            turns.append(
                ConversationTurn(
                    turn=i,
                    actor="user",
                    action="message",
                    thoughts=f"User step {i}",
                )
            )
        else:
            fc_part = {"functionCall": {"name": "run_bash", "args": {"cmd": f"step {i}"}}}
            chars = 25000 if i >= 10 else 15000
            turns.append(
                ConversationTurn(
                    turn=i,
                    actor="brain",
                    action="tool_result",
                    waitingFor="run_bash",
                    evidence="POD_LOG_DUMP_" + ("A" * chars),
                    response_parts=[fc_part],
                )
            )

    evidence = EventEvidence(
        display_text="Shedding test",
        source_type="chat",
        domain="complicated",
        severity="info",
    )
    return EventDocument(
        id=event_id,
        source="chat",
        service="payments",
        status=EventStatus("active"),
        brain_phase="dispatch",
        event=EventInput(reason="test", evidence=evidence, timeDate="2026-01-01T00:00:00Z"),
        conversation=turns,
    )


def _make_chunk(
    text: str = "response",
    is_thought: bool = False,
    function_call=None,
    raw_parts=None,
    grounding_metadata=None,
    usage=None,
    done: bool = False,
) -> SimpleNamespace:
    return SimpleNamespace(
        text=text,
        is_thought=is_thought,
        function_call=function_call,
        raw_parts=raw_parts or [],
        grounding_metadata=grounding_metadata,
        usage=usage,
        done=done,
    )


async def _async_stream_from_chunks(chunks: list[SimpleNamespace]):
    for c in chunks:
        yield c


def _assert_wire_invariants(contents: list[dict], event_id: str = "evt-shed-test"):
    """Verify Gemini alternating wire invariants and deterministic briefing injection."""
    assert len(contents) >= 3, f"Expected >= 3 messages, got {len(contents)}"
    assert contents[0]["role"] == "user"
    assert contents[0]["parts"][0].get("text") == BRAIN_PREFILL_USER
    assert contents[1]["role"] == "model"
    assert contents[1]["parts"][0].get("text") == BRAIN_PREFILL_MODEL
    assert contents[2]["role"] == "user"

    c2_text = contents[2]["parts"][0].get("text", "")
    assert f"Event ID: {event_id}" in c2_text, f"Missing Event ID in message 2 text: {c2_text[:200]}"
    assert "### Deterministic Operational Briefing" in c2_text, (
        f"Missing '### Deterministic Operational Briefing' in message 2: {c2_text[:200]}"
    )

    for i in range(len(contents) - 1):
        assert contents[i]["role"] != contents[i + 1]["role"], (
            f"Consecutive identical roles at index {i} and {i+1}: {contents[i]['role']} == {contents[i+1]['role']}"
        )

    fc_count = 0
    fr_count = 0
    for msg in contents:
        for p in msg.get("parts", []):
            if "functionCall" in p:
                fc_count += 1
            if "functionResponse" in p:
                fr_count += 1
    assert fc_count == fr_count, f"FC/FR count parity broken: fc={fc_count}, fr={fr_count}"


def _make_brain_for_shedding(stream_side_effect) -> tuple[Brain, MagicMock]:
    """Create a Brain with minimal stubs for _process_with_llm shedding tests."""
    bb = MagicMock()
    bb.get_event = AsyncMock()
    bb.get_service = AsyncMock(return_value=None)
    bb.get_active_events = AsyncMock(return_value=[])
    bb.get_recent_closed_for_service = AsyncMock(return_value=[])
    bb.get_journal = AsyncMock(return_value=[])
    bb.append_turn = AsyncMock(return_value=1)
    bb.mark_turn_status = AsyncMock()
    bb.stamp_event = AsyncMock()
    bb.redis = MagicMock()
    bb.redis.incr = AsyncMock()
    bb.redis.get = AsyncMock(return_value=None)

    brain = Brain(blackboard=bb, agents={})
    brain._get_journal_cached = AsyncMock(return_value=[])

    adapter = MagicMock()
    adapter.generate_stream = MagicMock(side_effect=stream_side_effect)
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
    brain._resolve_terminal_prompt = MagicMock(return_value=None)

    brain._broadcast = AsyncMock()
    brain._append_and_broadcast = AsyncMock(return_value=1)
    brain._next_turn_number = AsyncMock(return_value=15)
    brain._is_event_closed = AsyncMock(return_value=False)
    brain._normalize_response_parts = MagicMock(
        return_value=[{"functionCall": {"name": "select_agent", "args": {"agent": "developer"}}}]
    )
    brain._emit_executive_pulse = AsyncMock()
    brain._emit_thinking_pulse = AsyncMock()
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

    return brain, bb


# ---------------------------------------------------------------------------
# Layer 1 & 3: Executable Specifications (T-7, T-8, CR-01..CR-06)
# ---------------------------------------------------------------------------

class TestTwoTierQuotaShedding:
    """Acceptance and integration specifications for two-tier dynamic token shedding."""

    @pytest.mark.asyncio
    async def test_t7_tier1_shed_on_quota_exhausted_immediate_retry_no_sleep(self, monkeypatch):
        """T-7: Given _process_with_llm() receives QuotaExhaustedError on attempt 0,
        When retry executes,
        Then prompt is shed via Tier 1 (decaying older evidence to XML tags, turn_distance > 2)
        and re-acquires immediately without 30s sleep, reducing prompt tokens by >= 30%,
        and wire invariants strictly hold.
        """
        monkeypatch.setenv("BRAIN_THOUGHT_SIG_V2", "true")
        with patch("src.agents.brain._THOUGHT_SIG_V2", True):
            event = _make_shedding_event()

            fc = SimpleNamespace(name="select_agent", args={"agent": "developer"})
            success_stream = _async_stream_from_chunks([
                _make_chunk(
                    function_call=fc,
                    raw_parts=[{"functionCall": {"name": "select_agent", "args": {"agent": "developer"}}}],
                )
            ])

            stream_calls = [
                QuotaExhaustedError("Quota exhausted: 429 RESOURCE_EXHAUSTED"),
                success_stream,
            ]

            def _stream_factory(*args, **kwargs):
                if stream_calls:
                    res = stream_calls.pop(0)
                    if isinstance(res, Exception):
                        raise res
                    return res
                return _async_stream_from_chunks([])

            brain, bb = _make_brain_for_shedding(_stream_factory)

            with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
                result = await brain._process_with_llm("evt-shed-test", event)

            assert result is True
            assert brain._adapter.generate_stream.call_count == 2

            attempt_0_contents = brain._adapter.generate_stream.call_args_list[0].kwargs.get("contents")
            attempt_1_contents = brain._adapter.generate_stream.call_args_list[1].kwargs.get("contents")

            assert attempt_0_contents is not None
            assert attempt_1_contents is not None

            # Assert wire invariants on both attempts
            _assert_wire_invariants(attempt_0_contents)
            _assert_wire_invariants(attempt_1_contents)

            tokens_0 = estimate_tokens(attempt_0_contents)
            tokens_1 = estimate_tokens(attempt_1_contents)

            # Tier 1 token reduction requirement: >= 30% reduction from raw historical prompt
            assert tokens_1 <= int(tokens_0 * 0.70), (
                f"Tier 1 shedding failed to reduce prompt by >= 30%: tokens_0={tokens_0}, tokens_1={tokens_1}"
            )

            # Tier 1 immediate retry requirement: NO sleep awaited on attempt 0
            mock_sleep.assert_not_awaited()

            # Telemetry counter increment verification
            bb.redis.incr.assert_any_call("darwin:flow:quota_shed_tier1_total")

    @pytest.mark.asyncio
    async def test_t8_tier2_shed_on_consecutive_quota_exhausted_halves_tail_budget_with_backoff(self, monkeypatch):
        """T-8: Given _process_with_llm() still receives QuotaExhaustedError on attempt 1,
        When retry executes,
        Then prompt is shed via Tier 2 (halving tail_budget from 40k to 20k) before exponential backoff sleep,
        and wire invariants hold on all attempts.
        """
        monkeypatch.setenv("BRAIN_THOUGHT_SIG_V2", "true")
        with patch("src.agents.brain._THOUGHT_SIG_V2", True):
            event = _make_shedding_event()

            fc = SimpleNamespace(name="select_agent", args={"agent": "developer"})
            success_stream = _async_stream_from_chunks([
                _make_chunk(
                    function_call=fc,
                    raw_parts=[{"functionCall": {"name": "select_agent", "args": {"agent": "developer"}}}],
                )
            ])

            stream_calls = [
                QuotaExhaustedError("Quota exhausted attempt 0"),
                QuotaExhaustedError("Quota exhausted attempt 1"),
                success_stream,
            ]

            def _stream_factory(*args, **kwargs):
                if stream_calls:
                    res = stream_calls.pop(0)
                    if isinstance(res, Exception):
                        raise res
                    return res
                return _async_stream_from_chunks([])

            brain, bb = _make_brain_for_shedding(_stream_factory)

            with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
                result = await brain._process_with_llm("evt-shed-test", event)

            assert result is True
            assert brain._adapter.generate_stream.call_count == 3

            attempt_1_contents = brain._adapter.generate_stream.call_args_list[1].kwargs.get("contents")
            attempt_2_contents = brain._adapter.generate_stream.call_args_list[2].kwargs.get("contents")
            assert attempt_1_contents is not None
            assert attempt_2_contents is not None

            _assert_wire_invariants(attempt_1_contents)
            _assert_wire_invariants(attempt_2_contents)

            tokens_1 = estimate_tokens(attempt_1_contents)
            tokens_2 = estimate_tokens(attempt_2_contents)
            assert tokens_2 < tokens_1, f"Tier 2 halving must reduce tokens further: tokens_1={tokens_1}, tokens_2={tokens_2}"

            # Verify backoff sleep was invoked before attempt 2 (Tier 2 requirement)
            backoff_sleeps = [
                call.args[0] for call in mock_sleep.call_args_list
                if call.args and call.args[0] >= 15
            ]
            assert len(backoff_sleeps) >= 1, (
                "Tier 2 shedding must execute exponential backoff sleep before retry"
            )

            # Telemetry counter increment verification
            bb.redis.incr.assert_any_call("darwin:flow:quota_shed_tier2_total")

    @pytest.mark.asyncio
    async def test_t7_burst_error_sheds_without_sleep_and_unshrinkable_fails_fast(self, monkeypatch):
        """CR-01: Verify RequestExceedsBurstError handling for shrinkable and unshrinkable payloads.

        Subcase A: Event with historical evidence shrinks across Tier 1 & 2 without 30s sleep.
        Subcase B: Single-turn unshrinkable event fails fast without sleep delay.
        """
        monkeypatch.setenv("BRAIN_THOUGHT_SIG_V2", "true")
        with patch("src.agents.brain._THOUGHT_SIG_V2", True):
            # --- Subcase A: Shrinkable event ---
            event = _make_shedding_event("evt-burst-shrink")
            fc = SimpleNamespace(name="select_agent", args={"agent": "developer"})
            success_stream = _async_stream_from_chunks([
                _make_chunk(
                    function_call=fc,
                    raw_parts=[{"functionCall": {"name": "select_agent", "args": {"agent": "developer"}}}],
                )
            ])

            burst_calls = [
                RequestExceedsBurstError(180_000, 100_000),
                RequestExceedsBurstError(120_000, 100_000),
                success_stream,
            ]

            def _burst_factory(*args, **kwargs):
                if burst_calls:
                    res = burst_calls.pop(0)
                    if isinstance(res, Exception):
                        raise res
                    return res
                return _async_stream_from_chunks([])

            brain_a, bb_a = _make_brain_for_shedding(_burst_factory)
            with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep_a:
                res_a = await brain_a._process_with_llm("evt-burst-shrink", event)

            assert res_a is True
            assert brain_a._adapter.generate_stream.call_count == 3
            mock_sleep_a.assert_not_awaited()

            # --- Subcase B: Unshrinkable event (single turn) ---
            evidence = EventEvidence(display_text="Unshrinkable", source_type="chat", domain="complicated")
            single_turn_event = EventDocument(
                id="evt-burst-unshrink",
                source="chat",
                service="payments",
                status=EventStatus.ACTIVE,
                brain_phase="dispatch",
                event=EventInput(reason="test", evidence=evidence, timeDate="2026-01-01T00:00:00Z"),
                conversation=[ConversationTurn(turn=1, actor="user", action="message", thoughts="Single user prompt")],
            )

            def _always_burst(*args, **kwargs):
                raise RequestExceedsBurstError(180_000, 100_000)

            brain_b, bb_b = _make_brain_for_shedding(_always_burst)
            with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep_b:
                res_b = await brain_b._process_with_llm("evt-burst-unshrink", single_turn_event)

            assert res_b is False
            # Fails fast without 30s/60s sleep
            long_sleeps_b = [call.args[0] for call in mock_sleep_b.call_args_list if call.args and call.args[0] >= 15]
            assert len(long_sleeps_b) == 0
            # Error turn appended
            assert brain_b._append_and_broadcast.call_count >= 1
            error_turn = brain_b._append_and_broadcast.call_args[0][1]
            assert error_turn.action == "error"

    @pytest.mark.asyncio
    async def test_tier1_still_runs_when_attempt0_was_transient_non_quota_error(self, monkeypatch):
        """CR-02: If attempt 0 fails with a generic 503 transient error, and attempt 1 hits
        QuotaExhaustedError, Tier 1 shedding must still execute properly.
        """
        monkeypatch.setenv("BRAIN_THOUGHT_SIG_V2", "true")
        with patch("src.agents.brain._THOUGHT_SIG_V2", True):
            event = _make_shedding_event()
            fc = SimpleNamespace(name="select_agent", args={"agent": "developer"})
            success_stream = _async_stream_from_chunks([
                _make_chunk(
                    function_call=fc,
                    raw_parts=[{"functionCall": {"name": "select_agent", "args": {"agent": "developer"}}}],
                )
            ])

            calls = [
                ConnectionError("503 Service Unavailable"),
                QuotaExhaustedError("429 Resource Exhausted"),
                success_stream,
            ]

            def _factory(*args, **kwargs):
                if calls:
                    res = calls.pop(0)
                    if isinstance(res, Exception):
                        raise res
                    return res
                return _async_stream_from_chunks([])

            brain, bb = _make_brain_for_shedding(_factory)
            with patch("asyncio.sleep", new_callable=AsyncMock):
                result = await brain._process_with_llm("evt-shed-test", event)

            assert result is True
            assert brain._adapter.generate_stream.call_count == 3
            bb.redis.incr.assert_any_call("darwin:flow:quota_shed_tier1_total")
            attempt_2_contents = brain._adapter.generate_stream.call_args_list[2].kwargs.get("contents")
            _assert_wire_invariants(attempt_2_contents)

    @pytest.mark.asyncio
    async def test_redis_incr_failure_does_not_abort_shedding_retry(self, monkeypatch):
        """CR-03: Redis blip during telemetry counter increment must never abort the shedding retry."""
        monkeypatch.setenv("BRAIN_THOUGHT_SIG_V2", "true")
        with patch("src.agents.brain._THOUGHT_SIG_V2", True):
            event = _make_shedding_event()
            fc = SimpleNamespace(name="select_agent", args={"agent": "developer"})
            success_stream = _async_stream_from_chunks([
                _make_chunk(
                    function_call=fc,
                    raw_parts=[{"functionCall": {"name": "select_agent", "args": {"agent": "developer"}}}],
                )
            ])

            calls = [
                QuotaExhaustedError("Quota exhausted attempt 0"),
                QuotaExhaustedError("Quota exhausted attempt 1"),
                success_stream,
            ]

            def _factory(*args, **kwargs):
                if calls:
                    res = calls.pop(0)
                    if isinstance(res, Exception):
                        raise res
                    return res
                return _async_stream_from_chunks([])

            brain, bb = _make_brain_for_shedding(_factory)
            bb.redis.incr = AsyncMock(side_effect=ConnectionError("Redis connection reset"))

            with patch("asyncio.sleep", new_callable=AsyncMock):
                result = await brain._process_with_llm("evt-shed-test", event)

            assert result is True

    @pytest.mark.asyncio
    async def test_mid_stream_retry_exhaustion_clears_partial_accumulators(self, monkeypatch):
        """CR-04: Stream yields partial chunks before raising QuotaExhaustedError across all retries;
        Brain must clear partial accumulators and append an action='error' turn without saving partial response.
        """
        event = _make_shedding_event()

        async def _failing_mid_stream():
            yield _make_chunk(text="Partial uncompleted thought", is_thought=True)
            raise QuotaExhaustedError("Mid-stream 429")

        def _factory(*args, **kwargs):
            return _failing_mid_stream()

        brain, bb = _make_brain_for_shedding(_factory)
        with patch("asyncio.sleep", new_callable=AsyncMock):
            result = await brain._process_with_llm("evt-shed-test", event)

        assert result is False
        # Verify action == "error" turn was written, NOT action == "response"
        assert brain._append_and_broadcast.call_count >= 1
        last_turn = brain._append_and_broadcast.call_args[0][1]
        assert last_turn.action == "error"
        assert "LLM call failed" in last_turn.thoughts

    @pytest.mark.asyncio
    async def test_tier1_reuses_cached_header_without_redundant_redis_reads(self, monkeypatch):
        """CR-05: Tier 1 prompt re-encoding reuses cached context and avoids redundant Redis service lookups."""
        monkeypatch.setenv("BRAIN_THOUGHT_SIG_V2", "true")
        with patch("src.agents.brain._THOUGHT_SIG_V2", True):
            event = _make_shedding_event()
            fc = SimpleNamespace(name="select_agent", args={"agent": "developer"})
            success_stream = _async_stream_from_chunks([
                _make_chunk(
                    function_call=fc,
                    raw_parts=[{"functionCall": {"name": "select_agent", "args": {"agent": "developer"}}}],
                )
            ])

            calls = [
                QuotaExhaustedError("Quota exhausted attempt 0"),
                success_stream,
            ]

            def _factory(*args, **kwargs):
                if calls:
                    res = calls.pop(0)
                    if isinstance(res, Exception):
                        raise res
                    return res
                return _async_stream_from_chunks([])

            brain, bb = _make_brain_for_shedding(_factory)
            with patch("asyncio.sleep", new_callable=AsyncMock):
                await brain._process_with_llm("evt-shed-test", event)

            # Blackboard service lookup should only be performed once (or zero times via cache)
            assert bb.get_service.call_count <= 1

    @pytest.mark.asyncio
    async def test_short_conversation_tier1_shedding_ungates_recall_pruned_turns(self, monkeypatch):
        """CR-06: A 6-turn casual conversation has no decayed turns initially.
        When Tier 1 shedding executes with turn_decay_distance=2, older turns are decayed,
        which must set has_pruned_or_decayed_turns=True and dynamically include recall_pruned_turns.
        """
        monkeypatch.setenv("BRAIN_THOUGHT_SIG_V2", "true")
        with patch("src.agents.brain._THOUGHT_SIG_V2", True):
            turns = [
                ConversationTurn(turn=1, actor="user", action="message", thoughts="User message 1"),
                ConversationTurn(
                    turn=2,
                    actor="brain",
                    action="tool_result",
                    waitingFor="run_bash",
                    evidence="POD_LOG_DUMP_" + ("A" * 12000),
                    response_parts=[{"functionCall": {"name": "run_bash", "args": {"cmd": "log"}}}],
                ),
                ConversationTurn(turn=3, actor="user", action="message", thoughts="User message 2"),
                ConversationTurn(
                    turn=4,
                    actor="brain",
                    action="tool_result",
                    waitingFor="run_bash",
                    evidence="POD_LOG_DUMP_" + ("B" * 12000),
                    response_parts=[{"functionCall": {"name": "run_bash", "args": {"cmd": "log2"}}}],
                ),
                ConversationTurn(turn=5, actor="user", action="message", thoughts="User message 3"),
                ConversationTurn(turn=6, actor="user", action="message", thoughts="User message 4"),
            ]
            evidence = EventEvidence(display_text="Short casual", source_type="chat", domain="casual")
            event = EventDocument(
                id="evt-casual-shed",
                source="chat",
                service="payments",
                status=EventStatus.ACTIVE,
                brain_phase="dispatch",
                event=EventInput(reason="test", evidence=evidence, timeDate="2026-01-01T00:00:00Z"),
                conversation=turns,
            )

            fc = SimpleNamespace(name="select_agent", args={"agent": "developer"})
            success_stream = _async_stream_from_chunks([
                _make_chunk(
                    function_call=fc,
                    raw_parts=[{"functionCall": {"name": "select_agent", "args": {"agent": "developer"}}}],
                )
            ])

            calls = [
                QuotaExhaustedError("Quota exhausted attempt 0"),
                success_stream,
            ]

            def _factory(*args, **kwargs):
                if calls:
                    res = calls.pop(0)
                    if isinstance(res, Exception):
                        raise res
                    return res
                return _async_stream_from_chunks([])

            brain, bb = _make_brain_for_shedding(_factory)
            brain._extract_context_flags = AsyncMock(return_value={"event_domain": "casual"})

            with patch("asyncio.sleep", new_callable=AsyncMock):
                await brain._process_with_llm("evt-casual-shed", event)

            # On attempt 1 (after Tier 1 shed), tools passed to generate_stream must include recall_pruned_turns
            attempt_1_tools = brain._adapter.generate_stream.call_args_list[1].kwargs.get("tools")
            assert attempt_1_tools is not None
            tool_names = {t["name"] if isinstance(t, dict) else getattr(t, "name", "") for t in attempt_1_tools}
            assert "recall_pruned_turns" in tool_names

    @pytest.mark.asyncio
    async def test_burst_error_with_recent_heavy_turns_escalates_tier1_noop_to_tier2(self, monkeypatch):
        """Post-merge gap #2: Given a 3-turn event where ALL heavy payload is inside the latest 2 turns
        (turn_distance <= 2, so Tier 1 turn_decay_distance=2 sheds 0 tokens),
        When RequestExceedsBurstError is raised on attempt 0,
        Then Tier 1 no-op escalates immediately in the same attempt to Tier 2 tail compression
        without sleeping or aborting, increments quota_shed_tier2_total (not tier1_total), and succeeds.
        """
        monkeypatch.setenv("BRAIN_THOUGHT_SIG_V2", "true")
        with patch("src.agents.brain._THOUGHT_SIG_V2", True):
            turns = [
                ConversationTurn(turn=1, actor="user", action="message", thoughts="Initial question"),
                ConversationTurn(
                    turn=2,
                    actor="brain",
                    action="tool_result",
                    waitingFor="run_bash",
                    evidence="RECENT_HEAVY_1_" + ("A" * 80000),  # ~20k tokens at turn_distance=1 (<=2)
                    response_parts=[{"functionCall": {"name": "run_bash", "args": {"cmd": "logs1"}}}],
                ),
                ConversationTurn(
                    turn=3,
                    actor="brain",
                    action="tool_result",
                    waitingFor="run_bash",
                    evidence="RECENT_HEAVY_2_" + ("B" * 60000),  # ~15k tokens at turn_distance=0 (<=2)
                    response_parts=[{"functionCall": {"name": "run_bash", "args": {"cmd": "logs2"}}}],
                ),
            ]
            evidence = EventEvidence(display_text="Recent heavy burst", source_type="chat", domain="complicated")
            event = EventDocument(
                id="evt-recent-burst",
                source="chat",
                service="payments",
                status=EventStatus.ACTIVE,
                brain_phase="dispatch",
                event=EventInput(reason="test", evidence=evidence, timeDate="2026-01-01T00:00:00Z"),
                conversation=turns,
            )

            fc = SimpleNamespace(name="select_agent", args={"agent": "developer"})
            success_stream = _async_stream_from_chunks([
                _make_chunk(
                    function_call=fc,
                    raw_parts=[{"functionCall": {"name": "select_agent", "args": {"agent": "developer"}}}],
                )
            ])
            calls = [
                RequestExceedsBurstError(120_000, 100_000),
                success_stream,
            ]

            def _factory(*args, **kwargs):
                if calls:
                    res = calls.pop(0)
                    if isinstance(res, Exception):
                        raise res
                    return res
                return _async_stream_from_chunks([])

            brain, bb = _make_brain_for_shedding(_factory)
            with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
                res = await brain._process_with_llm("evt-recent-burst", event)

            assert res is True, "Recent-turn burst error must escalate to Tier 2 compression instead of aborting"
            assert brain._adapter.generate_stream.call_count == 2
            mock_sleep.assert_not_awaited()

            tokens_0 = estimate_tokens(brain._adapter.generate_stream.call_args_list[0].kwargs["contents"])
            tokens_1 = estimate_tokens(brain._adapter.generate_stream.call_args_list[1].kwargs["contents"])
            assert tokens_1 < tokens_0, f"Tier 2 escalation must shrink tokens: {tokens_0} -> {tokens_1}"

            incr_keys = [c.args[0] for c in bb.redis.incr.call_args_list]
            assert "darwin:flow:quota_shed_tier2_total" in incr_keys
            assert "darwin:flow:quota_shed_tier1_total" not in incr_keys

    @pytest.mark.asyncio
    async def test_tier2_backoff_matches_main_2_pow_attempt_schedule_with_additive_jitter(self, monkeypatch):
        """Tier 2 backoff on attempt 1 follows main's schedule: min(30 * 2**attempt, 120) = 60s plus additive
        jitter 0-30% => [60.0, 78.0] (the PR's shorter 2**max(0, attempt-1) schedule was a regression vs main)."""
        monkeypatch.setenv("BRAIN_THOUGHT_SIG_V2", "true")
        with patch("src.agents.brain._THOUGHT_SIG_V2", True):
            event = _make_shedding_event("evt-jitter-parity")
            fc = SimpleNamespace(name="select_agent", args={"agent": "developer"})
            success_stream = _async_stream_from_chunks([
                _make_chunk(
                    function_call=fc,
                    raw_parts=[{"functionCall": {"name": "select_agent", "args": {"agent": "developer"}}}],
                )
            ])
            calls = [
                QuotaExhaustedError("Quota exhausted 0"),
                QuotaExhaustedError("Quota exhausted 1"),
                success_stream,
            ]

            def _factory(*args, **kwargs):
                if calls:
                    res = calls.pop(0)
                    if isinstance(res, Exception):
                        raise res
                    return res
                return _async_stream_from_chunks([])

            brain, _ = _make_brain_for_shedding(_factory)
            sleeps: list[float] = []

            async def _record_sleep(d: float):
                sleeps.append(d)

            # random.random() == 0.9: attempt 1 => 60 + 60 * 0.3 * 0.9 = 76.2s, inside [60.0, 78.0].
            with (
                patch("src.agents.brain.random.random", return_value=0.9),
                patch("asyncio.sleep", new_callable=AsyncMock, side_effect=_record_sleep),
            ):
                res = await brain._process_with_llm("evt-jitter-parity", event)

            assert res is True
            assert len(sleeps) == 1
            assert 60.0 <= sleeps[0] <= 78.0, f"Expected 2**attempt backoff with additive jitter in [60.0, 78.0], got {sleeps[0]}"
            assert sleeps[0] == pytest.approx(76.2)

    def test_helm_and_docs_sliding_window_budget_parity(self):
        """Post-merge gap #1: Helm values.yaml, deployment.yaml, helm/README.md, and docs/deployment.md
        must expose 60000 / 40000 sliding window budgets without stale 800000 override or path leaks.
        """
        from pathlib import Path

        repo_root = Path(__file__).resolve().parent.parent
        values_yaml = (repo_root / "helm" / "values.yaml").read_text(encoding="utf-8")
        deploy_tmpl = (repo_root / "helm" / "templates" / "deployment.yaml").read_text(encoding="utf-8")
        helm_readme = (repo_root / "helm" / "README.md").read_text(encoding="utf-8")
        docs_deploy = (repo_root / "docs" / "deployment.md").read_text(encoding="utf-8")

        import re
        assert 'contentBudgetTokens: "60000"' in values_yaml, "helm/values.yaml must default contentBudgetTokens to 60000"
        assert 'tailBudgetTokens: "40000"' in values_yaml, "helm/values.yaml must expose tailBudgetTokens: 40000"
        assert not re.search(r"\b800000\b", values_yaml), "Stale 800000 contentBudgetTokens still present in helm/values.yaml"
        assert not re.search(r"\b800000\b", deploy_tmpl), "Stale 800000 default still present in helm/templates/deployment.yaml"
        assert "BRAIN_CONTENT_BUDGET_TOKENS" in deploy_tmpl
        assert "BRAIN_TAIL_BUDGET_TOKENS" in deploy_tmpl

        for key, val in (("contentBudgetTokens", "60000"), ("tailBudgetTokens", "40000")):
            matching_val_lines = [l for l in values_yaml.splitlines() if f"{key}:" in l]
            assert matching_val_lines and "#" in matching_val_lines[0], (
                f"Expected inline '#' comment on {key} in helm/values.yaml"
            )
            readme_plain = helm_readme.replace("`", "")
            rows = [l.strip() for l in readme_plain.splitlines() if f"brain.{key}" in l]
            assert rows and rows[0].endswith(f"| {val} |"), (
                f"Expected brain.{key} default '{val}' in helm/README.md, got {rows!r}"
            )

        docs_plain = docs_deploy.replace("`", "")
        for env_var, val in (("BRAIN_CONTENT_BUDGET_TOKENS", "60000"), ("BRAIN_TAIL_BUDGET_TOKENS", "40000")):
            rows = [l.strip() for l in docs_plain.splitlines() if l.strip().startswith(f"| {env_var} |")]
            assert rows and rows[0].endswith(f"| {val} |"), (
                f"Expected {env_var} default '{val}' in docs/deployment.md, got {rows!r}"
            )


# ---------------------------------------------------------------------------
# H2/H4/M3/M4: local-vs-upstream backoff policy, shed guards, reservations, priority
# ---------------------------------------------------------------------------

import src.agents.brain as _brain_mod
from src.agents.context_parts import compress_contents as _real_compress
from src.agents.llm.quota_tracker import PRIORITY_NORMAL, QuotaTracker


def _fc_success_stream():
    fc = SimpleNamespace(name="select_agent", args={"agent": "developer"})
    return _async_stream_from_chunks([
        _make_chunk(
            function_call=fc,
            raw_parts=[{"functionCall": {"name": "select_agent", "args": {"agent": "developer"}}}],
        )
    ])


def _scripted_factory(script: list):
    """generate_stream factory: pops exceptions (raised) / streams (returned) in order."""
    def _factory(*args, **kwargs):
        if script:
            res = script.pop(0)
            if isinstance(res, BaseException):
                raise res
            return res
        return _async_stream_from_chunks([])
    return _factory


def _incr_keys(bb) -> list[str]:
    return [c.args[0] for c in bb.redis.incr.call_args_list]


UPSTREAM_429 = "429 RESOURCE_EXHAUSTED: Quota exceeded for aiplatform.googleapis.com"


class TestQuotaBackoffPolicy:
    """H2: local burst/quota errors retry at once after a real Tier-1 shrink; upstream 429s always back off."""

    def test_quota_backoff_delay_schedule_is_main_2_pow_attempt_bounded(self):
        with patch("src.agents.brain.random.random", return_value=0.0):
            assert [Brain._quota_backoff_delay(a) for a in range(5)] == [30, 60, 120, 120, 120]
        with patch("src.agents.brain.random.random", return_value=1.0):
            delays = [Brain._quota_backoff_delay(a) for a in range(5)]
        assert delays == pytest.approx([39.0, 78.0, 156.0, 156.0, 156.0])
        assert max(delays) <= 120 * 1.3 + 1e-9, "backoff must stay bounded"

    @pytest.mark.asyncio
    async def test_upstream_429_over_budget_sheds_tier1_but_still_sleeps_30s_base(self, monkeypatch):
        """Upstream 429 on an over-budget prompt: shed Tier 1 AND back off (never the zero-sleep local path)."""
        monkeypatch.setenv("BRAIN_THOUGHT_SIG_V2", "true")
        with patch("src.agents.brain._THOUGHT_SIG_V2", True), patch("src.agents.brain._TAIL_BUDGET", 1000):
            event = _make_shedding_event()
            brain, bb = _make_brain_for_shedding(
                _scripted_factory([RuntimeError(UPSTREAM_429), _fc_success_stream()])
            )
            with (
                patch("src.agents.brain.random.random", return_value=0.0),
                patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep,
            ):
                assert await brain._process_with_llm("evt-shed-test", event) is True

            assert [c.args[0] for c in mock_sleep.await_args_list] == [30.0]
            assert "darwin:flow:quota_shed_tier1_total" in _incr_keys(bb)
            calls = brain._adapter.generate_stream.call_args_list
            assert estimate_tokens(calls[1].kwargs["contents"]) < estimate_tokens(calls[0].kwargs["contents"])

    @pytest.mark.asyncio
    async def test_upstream_429_on_already_small_prompt_does_not_shed(self, monkeypatch):
        """Generic upstream rate limit + prompt within the tail budget: identical prompt, backoff only."""
        monkeypatch.setenv("BRAIN_THOUGHT_SIG_V2", "true")
        with patch("src.agents.brain._THOUGHT_SIG_V2", True), patch("src.agents.brain._TAIL_BUDGET", 10**7):
            event = _make_shedding_event()
            brain, bb = _make_brain_for_shedding(
                _scripted_factory([RuntimeError(UPSTREAM_429), _fc_success_stream()])
            )
            with (
                patch("src.agents.brain.random.random", return_value=0.0),
                patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep,
            ):
                assert await brain._process_with_llm("evt-shed-test", event) is True

            calls = brain._adapter.generate_stream.call_args_list
            assert calls[1].kwargs["contents"] == calls[0].kwargs["contents"], "prompt must not be shed"
            assert [c.args[0] for c in mock_sleep.await_args_list] == [30.0]
            assert not [k for k in _incr_keys(bb) if "quota_shed" in k]

    @pytest.mark.asyncio
    async def test_upstream_429_backoff_schedule_30_60_120_then_bounded_failure(self, monkeypatch):
        monkeypatch.setenv("BRAIN_THOUGHT_SIG_V2", "true")
        with patch("src.agents.brain._THOUGHT_SIG_V2", True), patch("src.agents.brain._TAIL_BUDGET", 10**7):
            event = _make_shedding_event()
            brain, _bb = _make_brain_for_shedding(
                _scripted_factory([RuntimeError(UPSTREAM_429) for _ in range(10)])
            )
            with (
                patch("src.agents.brain.random.random", return_value=0.0),
                patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep,
            ):
                assert await brain._process_with_llm("evt-shed-test", event) is False

            assert brain._adapter.generate_stream.call_count == 4, "bounded to max_retries + 1 attempts"
            assert [c.args[0] for c in mock_sleep.await_args_list] == [30.0, 60.0, 120.0]
            assert brain._append_and_broadcast.call_args[0][1].action == "error"

    @pytest.mark.asyncio
    async def test_local_burst_tier1_shrink_retries_with_zero_sleep(self, monkeypatch):
        monkeypatch.setenv("BRAIN_THOUGHT_SIG_V2", "true")
        with patch("src.agents.brain._THOUGHT_SIG_V2", True):
            event = _make_shedding_event()
            brain, bb = _make_brain_for_shedding(
                _scripted_factory([RequestExceedsBurstError(180_000, 100_000), _fc_success_stream()])
            )
            with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
                assert await brain._process_with_llm("evt-shed-test", event) is True
            mock_sleep.assert_not_awaited()
            assert _incr_keys(bb) == ["darwin:flow:quota_shed_tier1_total"]

    @pytest.mark.asyncio
    async def test_local_quota_exhausted_tier2_shrink_backs_off_with_2_pow_attempt(self, monkeypatch):
        """Tier-1 is zero-sleep, but a Tier-2 retry of a (non-burst) quota error waits main's 2**attempt delay."""
        monkeypatch.setenv("BRAIN_THOUGHT_SIG_V2", "true")
        with patch("src.agents.brain._THOUGHT_SIG_V2", True):
            event = _make_shedding_event()
            brain, bb = _make_brain_for_shedding(_scripted_factory([
                QuotaExhaustedError("q0"), QuotaExhaustedError("q1"), _fc_success_stream(),
            ]))
            with (
                patch("src.agents.brain.random.random", return_value=0.0),
                patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep,
            ):
                assert await brain._process_with_llm("evt-shed-test", event) is True
            assert [c.args[0] for c in mock_sleep.await_args_list] == [60.0]  # attempt 1 -> 30 * 2**1
            assert _incr_keys(bb) == [
                "darwin:flow:quota_shed_tier1_total", "darwin:flow:quota_shed_tier2_total",
            ]


class TestQuotaShedGuards:
    """H4/M4: counters only on real shrink, failures never escape the handler."""

    @staticmethod
    def _noop_compress():
        return patch.object(
            Brain, "_compress_contents",
            new=classmethod(lambda cls, contents, max_tokens=None, tail_budget=None: contents),
        )

    @pytest.mark.asyncio
    async def test_tier2_noop_compress_does_not_increment_counter_and_burst_fails_fast(self, monkeypatch):
        monkeypatch.setenv("BRAIN_THOUGHT_SIG_V2", "true")
        with patch("src.agents.brain._THOUGHT_SIG_V2", True), self._noop_compress():
            event = _make_shedding_event()
            brain, bb = _make_brain_for_shedding(_scripted_factory([
                RequestExceedsBurstError(180_000, 100_000),
                RequestExceedsBurstError(180_000, 100_000),
                _fc_success_stream(),
            ]))
            with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
                assert await brain._process_with_llm("evt-shed-test", event) is False

            assert brain._adapter.generate_stream.call_count == 2, "no identical-prompt retry after a no-op shed"
            mock_sleep.assert_not_awaited()
            keys = _incr_keys(bb)
            assert "darwin:flow:quota_shed_tier1_total" in keys
            assert "darwin:flow:quota_shed_tier2_total" not in keys
            assert brain._append_and_broadcast.call_args[0][1].action == "error"

    @pytest.mark.asyncio
    async def test_tier2_noop_compress_non_burst_backs_off_without_counting(self, monkeypatch):
        monkeypatch.setenv("BRAIN_THOUGHT_SIG_V2", "true")
        with patch("src.agents.brain._THOUGHT_SIG_V2", True), self._noop_compress():
            event = _make_shedding_event()
            brain, bb = _make_brain_for_shedding(_scripted_factory([
                QuotaExhaustedError("q0"), QuotaExhaustedError("q1"), _fc_success_stream(),
            ]))
            with (
                patch("src.agents.brain.random.random", return_value=0.0),
                patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep,
            ):
                assert await brain._process_with_llm("evt-shed-test", event) is True
            assert "darwin:flow:quota_shed_tier2_total" not in _incr_keys(bb)
            assert [c.args[0] for c in mock_sleep.await_args_list] == [60.0]

    @pytest.mark.asyncio
    async def test_recovery_compress_and_rebuild_failures_never_escape_and_error_turn_is_recorded(self, monkeypatch):
        """Tier-1 rebuild AND every explicit-budget compress raise: the handler must swallow them, keep
        retrying through the generic backoff, and finally record the error turn (no exception out)."""
        monkeypatch.setenv("BRAIN_THOUGHT_SIG_V2", "true")

        def _boom(cls, contents, max_tokens=None, tail_budget=None):
            if max_tokens is not None:
                raise RuntimeError("compress exploded")
            return _real_compress(contents)

        with (
            patch("src.agents.brain._THOUGHT_SIG_V2", True),
            patch.object(Brain, "_compress_contents", new=classmethod(_boom)),
        ):
            event = _make_shedding_event()
            brain, bb = _make_brain_for_shedding(
                _scripted_factory([QuotaExhaustedError(f"q{i}") for i in range(10)])
            )
            orig_build = brain._build_contents

            async def _build(*args, **kwargs):
                if kwargs.get("turn_decay_distance") == 2:
                    raise RuntimeError("rebuild exploded")
                return await orig_build(*args, **kwargs)

            brain._build_contents = _build
            with patch("asyncio.sleep", new_callable=AsyncMock):
                result = await brain._process_with_llm("evt-shed-test", event)

            assert result is False
            assert brain._adapter.generate_stream.call_count == 4
            turn = brain._append_and_broadcast.call_args[0][1]
            assert turn.action == "error" and "LLM call failed" in turn.thoughts
            assert not [k for k in _incr_keys(bb) if "quota_shed" in k], "failed sheds must not count"


class _TrackedAdapter:
    """Adapter double wired to a REAL QuotaTracker, mirroring GeminiClient's reservation hand-off contract."""

    def __init__(self, tracker: QuotaTracker, script: list):
        self._tracker = tracker
        self._script = script
        self.calls: list[dict] = []
        self.acquired: list = []
        self.set_search_enabled = MagicMock()

    async def acquire_stream_reservation(self, contents, priority: int = PRIORITY_NORMAL):
        estimate = max(1, estimate_tokens(contents))
        reservation = await self._tracker.acquire(estimate, max_wait_seconds=1.0, priority=priority)
        self.acquired.append(reservation)
        return [estimate, reservation, False]

    def generate_stream(self, **kwargs):
        self.calls.append(kwargs)
        item = self._script.pop(0)
        if isinstance(item, BaseException):
            raise item
        return self._started(kwargs["_preacquired"], item)

    async def _started(self, pre, stream):
        pre[2] = True  # handed off: the stream now owns record/rollback
        try:
            async for chunk in stream:
                yield chunk
        finally:
            self._tracker.rollback(pre[1])


class TestQuotaTrackerBalanceAndPriority:
    @pytest.mark.asyncio
    async def test_reserve_release_balanced_across_shedding_retries(self, monkeypatch):
        monkeypatch.setenv("BRAIN_THOUGHT_SIG_V2", "true")
        with patch("src.agents.brain._THOUGHT_SIG_V2", True):
            event = _make_shedding_event()
            brain, _bb = _make_brain_for_shedding(lambda *a, **k: None)
            tracker = QuotaTracker(tpm_limit=10_000_000)
            adapter = _TrackedAdapter(tracker, [
                QuotaExhaustedError("q0"), QuotaExhaustedError("q1"), _fc_success_stream(),
            ])
            brain._adapter = adapter
            with patch("asyncio.sleep", new_callable=AsyncMock):
                assert await brain._process_with_llm("evt-shed-test", event) is True

            assert len(adapter.acquired) == 3, "one fresh reservation per attempt"
            assert len({r.id for r in adapter.acquired}) == 3
            assert tracker._active_reservations == {}, "every reservation released (no leak, no double-release error)"

    @pytest.mark.asyncio
    async def test_cancelled_error_releases_reservation(self, monkeypatch):
        monkeypatch.setenv("BRAIN_THOUGHT_SIG_V2", "true")
        with patch("src.agents.brain._THOUGHT_SIG_V2", True):
            event = _make_shedding_event()
            brain, _bb = _make_brain_for_shedding(lambda *a, **k: None)
            tracker = QuotaTracker(tpm_limit=10_000_000)
            adapter = _TrackedAdapter(tracker, [asyncio.CancelledError()])
            brain._adapter = adapter
            with pytest.raises(asyncio.CancelledError):
                await brain._process_with_llm("evt-shed-test", event)
            assert len(adapter.acquired) == 1
            assert tracker._active_reservations == {}

    @pytest.mark.asyncio
    async def test_mid_retry_cancel_after_shed_releases_reservation(self, monkeypatch):
        monkeypatch.setenv("BRAIN_THOUGHT_SIG_V2", "true")
        with patch("src.agents.brain._THOUGHT_SIG_V2", True):
            event = _make_shedding_event()
            brain, _bb = _make_brain_for_shedding(lambda *a, **k: None)
            tracker = QuotaTracker(tpm_limit=10_000_000)
            adapter = _TrackedAdapter(tracker, [QuotaExhaustedError("q0"), asyncio.CancelledError()])
            brain._adapter = adapter
            with patch("asyncio.sleep", new_callable=AsyncMock), pytest.raises(asyncio.CancelledError):
                await brain._process_with_llm("evt-shed-test", event)
            assert len(adapter.acquired) == 2
            assert tracker._active_reservations == {}

    @pytest.mark.asyncio
    async def test_llm_priority_derived_once_and_stable_across_retries(self, monkeypatch):
        monkeypatch.setenv("BRAIN_THOUGHT_SIG_V2", "true")
        with patch("src.agents.brain._THOUGHT_SIG_V2", True):
            event = _make_shedding_event()
            brain, _bb = _make_brain_for_shedding(_scripted_factory([
                QuotaExhaustedError("q0"), QuotaExhaustedError("q1"), _fc_success_stream(),
            ]))
            with (
                patch.object(_brain_mod, "derive_llm_priority", return_value=2) as mock_priority,
                patch("asyncio.sleep", new_callable=AsyncMock),
            ):
                assert await brain._process_with_llm("evt-shed-test", event) is True

            mock_priority.assert_called_once()
            priorities = [c.kwargs["priority"] for c in brain._adapter.generate_stream.call_args_list]
            assert priorities == [2, 2, 2]

    def test_derive_llm_priority_is_pure_and_unaffected_by_shedding_state(self):
        from src.agents.llm import derive_llm_priority

        event = _make_shedding_event()
        first = derive_llm_priority(event)
        assert derive_llm_priority(event) == first == derive_llm_priority(event)
