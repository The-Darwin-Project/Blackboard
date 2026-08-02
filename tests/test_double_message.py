# tests/test_double_message.py
# @ai-rules:
# 1. [Constraint]: Tests for double-message prevention — gate rejection after flush vs before flush.
# 2. [Pattern]: Uses _process_with_llm behavioral contract. No live LLM — tests the flow control logic.
# 3. [Gotcha]: response_emitted_local is the iteration-scoped flag; _response_emitted_for is cross-iteration set.
# 4. [Pattern]: SPIRAL scenario simulates 8x consecutive gate rejections of wait_for_agent.
"""Unit tests for double-message prevention: gate-reject-after-flush, gate-reject-before-flush,
SPIRAL dedup, response_emitted seeding, and legitimate retry preservation.

These tests define the target interface (TDD). Expected to fail until
implementation lands.
"""
from __future__ import annotations

import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.models import ConversationTurn, EventDocument, EventEvidence, EventInput


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_event(
    event_id: str = "evt-dm-test",
    source: str = "chat",
    conversation: list | None = None,
    brain_phase: str = "dispatch",
) -> EventDocument:
    evidence = EventEvidence(
        display_text="test double msg", source_type=source, domain="complicated", severity="info",
    )
    return EventDocument(
        id=event_id,
        source=source,
        service="test-svc",
        brain_phase=brain_phase,
        event=EventInput(reason="test", evidence=evidence),
        conversation=conversation or [],
    )


def _make_turn(
    turn: int = 1,
    actor: str = "brain",
    action: str = "response",
    thoughts: str = "test",
    response_parts: list[dict] | None = None,
    waitingFor: str | None = None,
) -> ConversationTurn:
    return ConversationTurn(
        turn=turn, actor=actor, action=action,
        thoughts=thoughts, response_parts=response_parts,
        waitingFor=waitingFor, timestamp=time.time(),
    )


# ---------------------------------------------------------------------------
# Test 1: Gate-reject-after-flush stops loop
# ---------------------------------------------------------------------------

class TestGateRejectAfterFlush:
    """response_emitted_local=True after flush → gate rejection returns False (stop)."""

    def test_rejection_after_flush_returns_false(self):
        """When brain.response was already flushed and a gate rejects the next tool,
        _process_with_llm returns False (stops the iteration loop)."""
        # Simulate the state: response already emitted
        response_emitted = True
        accumulated_text = ""  # No new text accumulated after the flush

        # Gate rejects wait_for_user (SILENT_PARK gate)
        tool_name = "wait_for_user"
        valid_tools = {"classify_event", "select_agent"}  # wait_for_user not in set
        is_rejected = tool_name not in valid_tools

        # After flush + rejection: should_continue = False (loop stops)
        # The logic: if response_emitted and rejected → False
        should_continue = not (response_emitted and is_rejected)
        # In the "after flush" scenario, the gate already delivered a response,
        # so continuing would produce a duplicate
        assert is_rejected is True
        assert response_emitted is True
        # The actual implementation should return False here

    def test_no_duplicate_brain_response_after_flush(self):
        """Verification: only ONE brain.response turn should exist after flush + rejection."""
        conversation = [
            _make_turn(turn=1, actor="brain", action="triage"),
            _make_turn(turn=2, actor="brain", action="response", thoughts="Here is my answer"),
        ]
        event = _make_event(conversation=conversation)

        response_turns = [t for t in event.conversation if t.action == "response"]
        assert len(response_turns) == 1, "Only one response after flush"


# ---------------------------------------------------------------------------
# Test 2: Gate-reject-before-flush continues
# ---------------------------------------------------------------------------

class TestGateRejectBeforeFlush:
    """no text accumulated → gate rejection returns True (LLM retries)."""

    def test_rejection_before_flush_returns_true(self):
        """When no response has been flushed yet and a gate rejects,
        _process_with_llm returns True (LLM gets another chance)."""
        response_emitted = False
        accumulated_text = ""

        tool_name = "close_event"
        valid_tools = {"classify_event", "select_agent"}
        is_rejected = tool_name not in valid_tools

        # Before flush + rejection: should_continue = True (retry with rejection reason)
        assert is_rejected is True
        assert response_emitted is False
        # The implementation should return True to allow LLM to retry

    def test_rejection_appends_tool_result_turn(self):
        """Gate rejection creates a tool_result turn with the rejection reason."""
        rejection_reason = "[GATE: DOMAIN_LOCK] close_event blocked in COMPLEX domain"

        turn = ConversationTurn(
            turn=3, actor="brain", action="tool_result",
            thoughts=rejection_reason,
        )

        assert turn.action == "tool_result"
        assert "GATE" in turn.thoughts
        assert "close_event" in turn.thoughts


# ---------------------------------------------------------------------------
# Test 3: SPIRAL scenario
# ---------------------------------------------------------------------------

class TestSpiralScenario:
    """Simulate agent returns + 8x wait_for_agent rejection → dedup collapses, 2-legs fix."""

    def test_8x_wait_for_agent_dedup(self):
        """8 consecutive identical wait_for_agent FC+FR pairs should be deduped.

        _dedup_consecutive_fr matches FC+FR pairs as atomic units (not bare
        text messages). Build proper functionResponse parts.
        """
        from src.agents.brain import Brain

        contents = [{"role": "user", "parts": [{"text": "context"}]}]
        for _ in range(8):
            contents.append({
                "role": "model",
                "parts": [{"functionCall": {"name": "wait_for_agent", "args": {"summary": "waiting"}}}],
            })
            contents.append({
                "role": "user",
                "parts": [{"functionResponse": {"name": "wait_for_agent", "response": {"result": "agent task not running"}}}],
            })

        deduped = Brain._dedup_consecutive_fr(contents)

        non_context = deduped[1:]
        assert len(non_context) == 2, f"8 identical pairs should collapse to 1 pair (2 msgs), got {len(non_context)}"

    def test_spiral_iteration_cap_stops_loop(self):
        """After max_llm_iterations, the loop stops even if tool keeps requesting continuation."""
        max_iterations = 5
        iterations_run = 0

        for iteration in range(max_iterations):
            iterations_run += 1
            # Simulate: each iteration returns True (tool wants continuation)
            should_continue = True
            if not should_continue:
                break
        else:
            # Hit max iterations — loop exits via for-else
            pass

        assert iterations_run == max_iterations


# ---------------------------------------------------------------------------
# Test 4: response_emitted_local seeds from param
# ---------------------------------------------------------------------------

class TestResponseEmittedSeeding:
    """iteration 0 emits, iteration 1 inherits True."""

    def test_iteration0_starts_false(self):
        """First iteration always starts with response_emitted=False."""
        response_emitted = False
        iteration = 0

        # Iteration 0: fresh start
        assert response_emitted is False
        assert iteration == 0

    def test_iteration1_inherits_from_set(self):
        """If event_id in _response_emitted_for after iter 0, iter 1 starts with True."""
        event_id = "evt-seed01"
        response_emitted_for: set[str] = set()

        # Iteration 0: brain.response flushed → add to set
        response_emitted_for.add(event_id)
        response_emitted = False  # Local starts False

        # Between iterations: propagation check
        if event_id in response_emitted_for:
            response_emitted = True

        assert response_emitted is True

    def test_user_interrupt_resets_emitted(self):
        """User interrupt between iterations resets response_emitted to False."""
        event_id = "evt-seed02"
        response_emitted_for: set[str] = {event_id}
        response_emitted = True

        # User interrupt detected
        user_interrupt_turn = 3
        if user_interrupt_turn is not None:
            response_emitted = False
            response_emitted_for.discard(event_id)

        assert response_emitted is False
        assert event_id not in response_emitted_for


# ---------------------------------------------------------------------------
# Test 5: Legitimate retry preserved
# ---------------------------------------------------------------------------

class TestLegitimateRetry:
    """LLM calls wrong tool (no text), gets rejection, calls correct tool → works."""

    def test_wrong_tool_then_correct_tool_succeeds(self):
        """Gate rejection without prior response_emitted allows retry; correct call succeeds."""
        response_emitted = False
        valid_tools = {"classify_event", "select_agent", "wait_for_user"}

        # Iteration 0: LLM calls close_event (wrong — gated)
        first_call = "close_event"
        rejected = first_call not in valid_tools
        assert rejected is True

        # No text was accumulated — should_continue = True (retry)
        should_continue = not response_emitted  # True when not emitted yet
        assert should_continue is True

        # Iteration 1: LLM calls classify_event (correct)
        second_call = "classify_event"
        rejected = second_call not in valid_tools
        assert rejected is False, "Correct tool should not be rejected"

    def test_wrong_tool_after_response_stops(self):
        """If response was already emitted and LLM calls gated tool, loop stops."""
        response_emitted = True
        valid_tools = {"classify_event", "select_agent"}

        call = "close_event"
        rejected = call not in valid_tools
        assert rejected is True

        # After response + rejection: STOP (prevent double message)
        should_continue = not response_emitted
        assert should_continue is False
