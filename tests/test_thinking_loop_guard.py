# tests/test_thinking_loop_guard.py
# @ai-rules:
# 1. [Constraint]: Pure unit and async tests for thinking loop prevention across context_parts, tool_gates, and scan_active_events.
# 2. [Pattern]: Validates the fix for live incident evt-3e11b42d (infinite thinking loop on JARVIS bare acks).
"""Unit tests for thinking loop stall guard and JARVIS acknowledgment handling."""
from __future__ import annotations

import time
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.agents.brain import Brain
from src.agents.context_parts import turn_to_parts
from src.agents.tool_gates import (
    GateContext,
    evaluate_gates,
    has_unevaluated_close_blocker,
)
from src.models import (
    ConversationTurn,
    EventDocument,
    EventEvidence,
    EventInput,
    EventStatus,
    MessageStatus,
)
from src.utils.jarvis_ack import is_jarvis_acknowledgment


def _make_turn(actor: str, action: str, thoughts: str | None = None, status=None, turn: int = 1) -> ConversationTurn:
    return ConversationTurn(
        turn=turn,
        actor=actor,
        action=action,
        thoughts=thoughts,
        status=status or MessageStatus.EVALUATED,
        timestamp=time.time(),
    )


def _make_event(
    event_id: str = "evt-loop-test",
    source: str = "headhunter",
    conversation: list[ConversationTurn] | None = None,
    brain_phase: str = "dispatch",
) -> EventDocument:
    evidence = EventEvidence(
        display_text="test", source_type=source, domain="complicated", severity="info",
    )
    return EventDocument(
        id=event_id,
        source=source,
        status=EventStatus.ACTIVE,
        brain_phase=brain_phase,
        service="test-svc",
        event=EventInput(
            reason="test", evidence=evidence, timeDate="2026-01-01T00:00:00Z",
        ),
        conversation=conversation or [],
    )


class TestJarvisAckHelper:
    def test_recognizes_acknowledgments(self):
        acks = [
            "watching",
            "watching.",
            "Watching",
            "silently observing",
            "Silently observing.",
            "acknowledged",
            "Acknowledged.",
            "confirmed",
            "Confirmed",
            "understood",
            "Understood.",
            "no observations",
            "No observations.",
            "noted",
            "ok",
            "ok.",
            "OK",
        ]
        for text in acks:
            assert is_jarvis_acknowledgment(text) is True, f"Failed for {text}"

    def test_rejects_non_acknowledgments(self):
        non_acks = [
            "What is the next step?",
            "Can you verify the deployment?",
            "Please fix the failing CI.",
            "Could you explain this error?",
            "watching for deployment failure on pod 3",  # longer sentence
            None,
            "",
            "   ",
            123,
            ["watching"],
            {"ack": True},
        ]
        for text in non_acks:
            assert is_jarvis_acknowledgment(text) is False, f"Should be False for {text}"

    def test_markdown_stripped_acknowledgments(self):
        markdown_acks = [
            "*watching*",
            "**ok**",
            "_acknowledged_",
            '"silently observing"',
            "'noted'",
        ]
        for text in markdown_acks:
            assert is_jarvis_acknowledgment(text) is True, f"Failed for {text}"



class TestContextPartsNoDirectiveOnAck:
    def test_ack_does_not_inject_directive(self):
        turn = _make_turn("jarvis", "message", thoughts="watching")
        parts = turn_to_parts(turn)
        assert len(parts) == 1
        assert parts[0]["text"] == "[AGENT jarvis]: watching"
        assert "JARVIS asked you a question" not in parts[0]["text"]

    def test_question_injects_directive(self):
        turn = _make_turn("jarvis", "message", thoughts="What is the next step?")
        parts = turn_to_parts(turn)
        assert len(parts) == 1
        assert "JARVIS asked you a question. Send your answer back to JARVIS before doing anything else." in parts[0]["text"]


class TestToolGatesAckStripping:
    def test_respond_to_jarvis_stripped_on_ack(self):
        schemas = [{"name": "respond_to_jarvis"}, {"name": "select_agent"}, {"name": "defer_event"}]
        turns = [
            _make_turn("brain", "respond_jarvis", turn=1),
            _make_turn("jarvis", "message", thoughts="watching", turn=2),
        ]
        ctx = GateContext(
            brain_phase="dispatch",
            event_source="headhunter",
            context_flags={"brain_has_classified": True, "event_domain": "complicated"},
            conversation=turns,
            is_defer_wake=False,
            iteration=0,
            has_kargo_context=True,
            has_github_context=True,
            unread_notes=0,
            refresh_budget=5,
            refresh_count=0,
            has_dispatch_backpressure=False,
            jarvis_already_waiting=False,
            jarvis_wait_count=0,
        )
        surviving = evaluate_gates(schemas, ctx)
        names = {s["name"] for s in surviving}
        assert "respond_to_jarvis" not in names

    def test_close_blocker_ignores_jarvis_ack(self):
        turns = [
            _make_turn("jarvis", "message", thoughts="silently observing", status=MessageStatus.SENT),
        ]
        assert has_unevaluated_close_blocker(turns) is False


class TestScanActiveEventsStallGuard:
    @pytest.mark.asyncio
    async def test_scan_suppresses_re_enqueue_on_consecutive_thoughts(self):
        bb = AsyncMock()
        brain = Brain(blackboard=bb)
        eid = "evt-stall-1"

        # Event with 2 trailing thoughts turns and idle > 60s
        turns = [
            _make_turn("brain", "respond_jarvis", turn=1),
            _make_turn("jarvis", "message", thoughts="watching", turn=2),
            _make_turn("brain", "thoughts", thoughts="I am pondering...", turn=3),
            _make_turn("brain", "thoughts", thoughts="I am still pondering...", turn=4),
        ]
        event = _make_event(event_id=eid, conversation=turns)
        bb.get_active_events_with_status.return_value = {eid: "active"}
        bb.get_event.return_value = event

        brain._last_processed[eid] = time.time() - 120  # Idle for 120s

        to_enqueue = await brain._scan_active_for_reconcile()
        assert eid not in to_enqueue, "Event with 2 consecutive thoughts should be suppressed by stall guard"

    @pytest.mark.asyncio
    async def test_scan_enqueues_when_unread_turn_arrives_despite_thoughts(self):
        bb = AsyncMock()
        brain = Brain(blackboard=bb)
        eid = "evt-stall-2"

        # Event had 2 thoughts turns, but a new delivered user message arrived
        turns = [
            _make_turn("brain", "thoughts", thoughts="thinking 1", turn=1),
            _make_turn("brain", "thoughts", thoughts="thinking 2", turn=2),
            _make_turn("user", "message", thoughts="Wake up!", status=MessageStatus.DELIVERED, turn=3),
        ]
        event = _make_event(event_id=eid, conversation=turns)
        bb.get_active_events_with_status.return_value = {eid: "active"}
        bb.get_event.return_value = event

        brain._last_processed[eid] = time.time() - 120

        to_enqueue = await brain._scan_active_for_reconcile()
        assert eid in to_enqueue, "Event with new unread message must be enqueued despite prior thoughts"
