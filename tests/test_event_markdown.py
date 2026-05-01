# tests/test_event_markdown.py
# @ai-rules:
# 1. [Constraint]: Pure function tests only -- Brain._event_to_markdown is a @staticmethod, no instance needed.
# 2. [Pattern]: Constructs minimal EventDocument + ConversationTurn, asserts on markdown output labels.
"""Tests for actor-aware label rendering in Brain._event_to_markdown."""
from __future__ import annotations

from src.agents.brain import Brain
from src.models import ConversationTurn, EventDocument, EventInput


def _make_event(*turns: ConversationTurn) -> EventDocument:
    return EventDocument(
        source="chat",
        service="test-service",
        event=EventInput(reason="test", evidence="test evidence"),
        conversation=list(turns),
    )


def _make_turn(**kwargs) -> ConversationTurn:
    defaults = {"turn": 1, "actor": "brain", "action": "think", "timestamp": 1714500000.0}
    defaults.update(kwargs)
    return ConversationTurn(**defaults)


def test_user_turn_renders_message_label():
    """User turn must render **Message:** not **Thoughts:**."""
    turn = _make_turn(actor="user", action="message", thoughts="Hello from user")
    md = Brain._event_to_markdown(_make_event(turn))
    assert "**Message:** Hello from user" in md
    assert "**Thoughts:**" not in md


def test_user_turn_falls_back_to_result():
    """User turn with no thoughts falls back to result field."""
    turn = _make_turn(actor="user", action="message", thoughts=None, result="fallback text")
    md = Brain._event_to_markdown(_make_event(turn))
    assert "**Message:** fallback text" in md


def test_brain_turn_still_renders_thoughts():
    """Brain turn must still render **Thoughts:** (regression check)."""
    turn = _make_turn(actor="brain", action="think", thoughts="Analyzing the situation")
    md = Brain._event_to_markdown(_make_event(turn))
    assert "**Thoughts:** Analyzing the situation" in md


def test_tool_result_renders_evidence_label():
    """tool_result action must render **Evidence:** from result field."""
    turn = _make_turn(actor="brain", action="tool_result", result="service is healthy")
    md = Brain._event_to_markdown(_make_event(turn))
    assert "**Evidence:** service is healthy" in md
    assert "**Thoughts:**" not in md


def test_non_user_fields_preserved():
    """plan, evidence, selectedAgents, waitingFor still render for non-user turns."""
    turn = _make_turn(
        actor="brain",
        action="route",
        thoughts="Routing to developer",
        plan="## Step 1\nDo something",
        selectedAgents=["developer"],
        waitingFor="agent",
    )
    md = Brain._event_to_markdown(_make_event(turn))
    assert "**Thoughts:** Routing to developer" in md
    assert "**Plan:**" in md
    assert "**Selected Agents:** developer" in md
    assert "**Waiting For:** agent" in md


def test_user_turn_does_not_render_extra_fields():
    """User turn should only render Message, not Thoughts or Result separately."""
    turn = _make_turn(actor="user", action="message", thoughts="user msg", result="should not appear")
    md = Brain._event_to_markdown(_make_event(turn))
    assert "**Message:** user msg" in md
    assert "**Result:**" not in md
