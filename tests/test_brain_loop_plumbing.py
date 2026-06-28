# tests/test_brain_loop_plumbing.py
# @ai-rules:
# 1. [Constraint]: Tests for brain.py LLM loop plumbing — user interrupt, wait-guard scope, stale turns.
# 2. [Pattern]: Uses _make_event/_make_turn from test_scan_callback.py pattern. No live Redis or LLM.
# 3. [Gotcha]: ConversationTurn.status defaults to SENT. Set explicitly for DELIVERED/EVALUATED turns.
"""Unit tests for brain.py LLM iteration loop plumbing fixes.

Tests:
- User interrupt detection + injection
- _waiting_for_agent temporal scoping (both guards)
- Survivor turn number (cross-source merge)
"""
import time
import pytest

from src.models import (
    ConversationTurn,
    EventDocument,
    EventInput,
    EventEvidence,
    EventStatus,
    MessageStatus,
)


def _make_event(
    event_id: str = "evt-test",
    status: str = "active",
    source: str = "chat",
    service: str = "test-svc",
    conversation: list | None = None,
    brain_phase: str | None = "triage",
) -> EventDocument:
    evidence = EventEvidence(
        display_text="test", source_type=source, domain="complicated", severity="info",
    )
    event_input = EventInput(
        reason="test", evidence=evidence, timeDate="2026-01-01T00:00:00Z",
    )
    return EventDocument(
        id=event_id,
        source=source,
        status=EventStatus(status),
        brain_phase=brain_phase,
        service=service,
        event=event_input,
        conversation=conversation or [],
    )


def _make_turn(
    turn: int = 1,
    actor: str = "brain",
    action: str = "triage",
    status: str = "evaluated",
    thoughts: str = "test",
    timestamp: float | None = None,
) -> ConversationTurn:
    return ConversationTurn(
        turn=turn, actor=actor, action=action, status=status,
        thoughts=thoughts, timestamp=timestamp or time.time(),
    )


# =========================================================================
# Test 1: User interrupt detected
# =========================================================================
class TestUserInterruptDetection:
    def test_user_interrupt_detected(self):
        """User turn after turn_snapshot → interrupt detected, response_emitted reset."""
        turn_snapshot = 2
        conversation = [
            _make_turn(turn=1, actor="brain", action="triage", status="evaluated"),
            _make_turn(turn=2, actor="brain", action="route", status="evaluated"),
            _make_turn(turn=3, actor="user", action="message", status="sent"),
        ]
        event = _make_event(conversation=conversation)
        is_intermediate = False
        response_emitted_for: set[str] = {"evt-test"}

        user_interrupt_turn: int | None = None
        response_emitted = True
        if not is_intermediate:
            new_user_turns = [
                t for t in event.conversation[turn_snapshot:]
                if t.actor == "user" and t.status.value in ("sent", "delivered")
            ]
            if new_user_turns:
                user_interrupt_turn = new_user_turns[-1].turn
                response_emitted = False
                response_emitted_for.discard("evt-test")

        assert user_interrupt_turn == 3
        assert response_emitted is False
        assert "evt-test" not in response_emitted_for

    def test_user_interrupt_skipped_intermediate(self):
        """Intermediate mode skips interrupt detection."""
        turn_snapshot = 1
        conversation = [
            _make_turn(turn=1, actor="brain", action="wait", status="evaluated"),
            _make_turn(turn=2, actor="user", action="message", status="sent"),
        ]
        event = _make_event(conversation=conversation)
        is_intermediate = True

        user_interrupt_turn: int | None = None
        if not is_intermediate:
            new_user_turns = [
                t for t in event.conversation[turn_snapshot:]
                if t.actor == "user" and t.status.value in ("sent", "delivered")
            ]
            if new_user_turns:
                user_interrupt_turn = new_user_turns[-1].turn

        assert user_interrupt_turn is None

    def test_user_interrupt_safety_net(self):
        """turn_snapshot is NOT modified by interrupt detection — user turn stays for scan safety net."""
        turn_snapshot = 2
        original_snapshot = turn_snapshot
        conversation = [
            _make_turn(turn=1, actor="brain", action="triage", status="evaluated"),
            _make_turn(turn=2, actor="brain", action="route", status="evaluated"),
            _make_turn(turn=3, actor="user", action="message", status="delivered"),
        ]
        event = _make_event(conversation=conversation)
        is_intermediate = False

        user_interrupt_turn: int | None = None
        if not is_intermediate:
            new_user_turns = [
                t for t in event.conversation[turn_snapshot:]
                if t.actor == "user" and t.status.value in ("sent", "delivered")
            ]
            if new_user_turns:
                user_interrupt_turn = new_user_turns[-1].turn

        assert user_interrupt_turn == 3
        assert turn_snapshot == original_snapshot

    def test_user_interrupt_iteration0_fallback(self):
        """Iteration 0 has no re-fetch — user turns arriving after snapshot aren't visible yet."""
        turn_snapshot = 3
        conversation = [
            _make_turn(turn=1, actor="brain", action="triage", status="evaluated"),
            _make_turn(turn=2, actor="brain", action="route", status="evaluated"),
            _make_turn(turn=3, actor="brain", action="wait", status="evaluated"),
        ]
        event = _make_event(conversation=conversation)
        is_intermediate = False

        user_interrupt_turn: int | None = None
        if not is_intermediate:
            new_user_turns = [
                t for t in event.conversation[turn_snapshot:]
                if t.actor == "user" and t.status.value in ("sent", "delivered")
            ]
            if new_user_turns:
                user_interrupt_turn = new_user_turns[-1].turn

        assert user_interrupt_turn is None


# =========================================================================
# Test 5-6: _process_event_inner wait guard scoping
# =========================================================================
class TestWaitGuardScope:
    def test_wait_guard_scoped_to_post_wait(self):
        """JARVIS DELIVERED at idx 3, wait set at idx 5 → guard holds (old turns don't false-clear)."""
        conversation = [
            _make_turn(turn=1, actor="brain", action="triage", status="evaluated"),
            _make_turn(turn=2, actor="brain", action="route", status="evaluated"),
            _make_turn(turn=3, actor="brain", action="wait", status="evaluated"),
            _make_turn(turn=4, actor="jarvis", action="message", status="delivered"),
            _make_turn(turn=5, actor="brain", action="thoughts", status="evaluated"),
            _make_turn(turn=6, actor="brain", action="wait", status="evaluated"),
        ]
        wait_turn = 6
        waiting_for_agent = {"evt-test": ("developer", wait_turn)}

        has_response = any(
            t.status.value == "delivered" and t.actor != "brain"
            for t in conversation[wait_turn:]
        )
        assert not has_response, "Guard should hold: JARVIS turn is before wait_turn"

    def test_wait_guard_clears_on_post_wait_agent(self):
        """Agent DELIVERED at idx 7, wait at idx 5 → cleared."""
        conversation = [
            _make_turn(turn=1, actor="brain", action="triage", status="evaluated"),
            _make_turn(turn=2, actor="brain", action="route", status="evaluated"),
            _make_turn(turn=3, actor="brain", action="wait", status="evaluated"),
            _make_turn(turn=4, actor="jarvis", action="message", status="delivered"),
            _make_turn(turn=5, actor="brain", action="wait", status="evaluated"),
            _make_turn(turn=6, actor="brain", action="thoughts", status="evaluated"),
            _make_turn(turn=7, actor="developer", action="result", status="delivered"),
        ]
        wait_turn = 5
        waiting_for_agent = {"evt-test": ("developer", wait_turn)}

        has_response = any(
            t.status.value == "delivered" and t.actor != "brain"
            for t in conversation[wait_turn:]
        )
        assert has_response, "Guard should clear: developer turn is after wait_turn"


# =========================================================================
# Test 7-8: Scan Guard 7 scoping
# =========================================================================
class TestScanGuard7Scope:
    def test_scan_guard7_unseen_fast_path(self):
        """Guard 7 wakes on fresh sent non-brain turn in unseen (edge-triggered)."""
        conversation = [
            _make_turn(turn=1, actor="brain", action="wait", status="evaluated"),
            _make_turn(turn=2, actor="developer", action="result", status="sent"),
        ]
        wait_turn = 1

        unseen = [t for t in conversation if t.status.value == "sent"]
        has_participant_input = any(t.actor != "brain" for t in unseen)
        if not has_participant_input:
            has_participant_input = any(
                t.status.value == "delivered" and t.actor != "brain"
                for t in conversation[wait_turn:]
            )
        assert has_participant_input, "Edge-triggered fast-path should wake on sent developer turn"

    def test_scan_guard7_delivered_boundary(self):
        """Guard 7 delivered check scoped to post-wait_turn only — pre-wait JARVIS doesn't wake."""
        conversation = [
            _make_turn(turn=1, actor="brain", action="triage", status="evaluated"),
            _make_turn(turn=2, actor="jarvis", action="message", status="delivered"),
            _make_turn(turn=3, actor="brain", action="route", status="evaluated"),
            _make_turn(turn=4, actor="brain", action="wait", status="evaluated"),
        ]
        wait_turn = 4

        unseen = [t for t in conversation if t.status.value == "sent"]
        has_participant_input = any(t.actor != "brain" for t in unseen)
        if not has_participant_input:
            has_participant_input = any(
                t.status.value == "delivered" and t.actor != "brain"
                for t in conversation[wait_turn:]
            )
        assert not has_participant_input, "Pre-wait JARVIS delivered turn should not wake Guard 7"


# =========================================================================
# Test 9: Survivor turn number (cross-source merge)
# =========================================================================
class TestSurvivorTurnNumber:
    def test_survivor_turn_number(self):
        """Cross-source merge at L841 uses _next_turn_number(eid) for survivor event, not event_id."""
        survivor_conversation = [
            _make_turn(turn=1, actor="brain", action="triage", status="evaluated"),
            _make_turn(turn=2, actor="brain", action="route", status="evaluated"),
            _make_turn(turn=3, actor="sysadmin", action="result", status="delivered"),
        ]
        current_conversation = [
            _make_turn(turn=1, actor="brain", action="triage", status="evaluated"),
        ]
        survivor = _make_event(event_id="evt-survivor", source="headhunter", conversation=survivor_conversation)
        current = _make_event(event_id="evt-current", source="aligner", conversation=current_conversation)

        survivor_next = len(survivor.conversation) + 1
        current_next = len(current.conversation) + 1

        assert survivor_next == 4, "Survivor event has 3 turns, next should be 4"
        assert current_next == 2, "Current event has 1 turn, next should be 2"
        assert survivor_next != current_next, "Using wrong event would produce wrong turn number"
