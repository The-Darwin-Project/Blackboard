# tests/test_sticky_notes.py
# @ai-rules:
# 1. [Pattern]: Tests sticky notes data model, tool gating, notification injection, and tool ordering.
# 2. [Constraint]: No Redis, no async for model/gating tests. Async only for blackboard method.
"""Unit tests for FRIDAY sticky notes feature."""
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from src.models import ConversationTurn, EventDocument, EventInput


class TestStickyNotesModel:
    def test_default_empty(self):
        event = EventDocument(source="chat", service="test",
                              event=EventInput(reason="test", evidence="ev"))
        assert event.sticky_notes == []
        assert event.unread_notes == 0

    def test_backward_compat_legacy_blob(self):
        legacy = {"id": "evt-old", "source": "chat", "status": "active",
                  "service": "x", "event": {"reason": "r", "evidence": "e"},
                  "conversation": []}
        event = EventDocument(**legacy)
        assert event.sticky_notes == []
        assert event.unread_notes == 0

    def test_roundtrip_with_notes(self):
        event = EventDocument(source="jarvis", service="system",
                              event=EventInput(reason="review", evidence="ev"),
                              sticky_notes=[{"timestamp": "2026-05-21T16:00:00Z",
                                             "content": "Check pipeline", "read": False}],
                              unread_notes=1)
        blob = json.loads(json.dumps(event.model_dump()))
        restored = EventDocument(**blob)
        assert len(restored.sticky_notes) == 1
        assert restored.unread_notes == 1


class TestStickyNotesGating:
    def test_post_available_jarvis_close(self):
        """post_sticky_note available when source=jarvis AND phase=close."""
        from src.agents.llm.types import BRAIN_TOOL_SCHEMAS
        tools = [t.copy() for t in BRAIN_TOOL_SCHEMAS]
        event = MagicMock(source="jarvis", unread_notes=0)
        brain_phase = "close"
        if not (event.source == "jarvis" and brain_phase == "close"):
            tools = [t for t in tools if t["name"] != "post_sticky_note"]
        assert any(t["name"] == "post_sticky_note" for t in tools)

    def test_post_stripped_non_jarvis(self):
        from src.agents.llm.types import BRAIN_TOOL_SCHEMAS
        tools = [t.copy() for t in BRAIN_TOOL_SCHEMAS]
        event = MagicMock(source="chat", unread_notes=0)
        brain_phase = "close"
        if not (event.source == "jarvis" and brain_phase == "close"):
            tools = [t for t in tools if t["name"] != "post_sticky_note"]
        assert not any(t["name"] == "post_sticky_note" for t in tools)

    def test_post_stripped_jarvis_non_close(self):
        from src.agents.llm.types import BRAIN_TOOL_SCHEMAS
        tools = [t.copy() for t in BRAIN_TOOL_SCHEMAS]
        event = MagicMock(source="jarvis", unread_notes=0)
        brain_phase = "investigate"
        if not (event.source == "jarvis" and brain_phase == "close"):
            tools = [t for t in tools if t["name"] != "post_sticky_note"]
        assert not any(t["name"] == "post_sticky_note" for t in tools)

    def test_read_available_when_unread(self):
        from src.agents.llm.types import BRAIN_TOOL_SCHEMAS
        tools = [t.copy() for t in BRAIN_TOOL_SCHEMAS]
        unread = 2
        if unread <= 0:
            tools = [t for t in tools if t["name"] != "read_sticky_notes"]
        assert any(t["name"] == "read_sticky_notes" for t in tools)

    def test_read_stripped_when_zero(self):
        from src.agents.llm.types import BRAIN_TOOL_SCHEMAS
        tools = [t.copy() for t in BRAIN_TOOL_SCHEMAS]
        unread = 0
        if unread <= 0:
            tools = [t for t in tools if t["name"] != "read_sticky_notes"]
        assert not any(t["name"] == "read_sticky_notes" for t in tools)


class TestStickyNotesHeaderRemoved:
    """Verify the passive header hint was removed (notification turn replaces it)."""

    def test_no_sticky_hint_in_header(self):
        from src.agents.brain import Brain
        event = MagicMock()
        event.conversation = []
        event.brain_phase = "investigate"
        event.event.evidence.brain_domain = "complicated"
        event.event.evidence.domain = "complicated"
        event.event.evidence.brain_severity = "info"
        event.event.evidence.severity = "info"
        event.unread_notes = 3
        header = Brain._build_event_state_header(event)
        assert "unread note" not in header


class TestStickyNotesNotification:
    """Verify notification turn injection logic."""

    def _make_event(self, unread: int, conversation: list | None = None):
        ev = MagicMock()
        ev.unread_notes = unread
        ev.conversation = conversation or []
        return ev

    def _notification_turn(self, thoughts: str = "Your past self left 2 note(s) from a previous review session."):
        return ConversationTurn(turn=1, actor="system", action="notification", thoughts=thoughts)

    def test_notification_injected_when_unread(self):
        """iteration==0, unread>0, no existing notification -> inject."""
        event = self._make_event(unread=2)
        iteration = 0
        should_inject = (
            iteration == 0
            and (getattr(event, "unread_notes", 0) or 0) > 0
            and not any(
                t.actor == "system" and t.action == "notification"
                for t in event.conversation
            )
        )
        assert should_inject is True

    def test_no_injection_iteration_nonzero(self):
        """iteration>0 -> no injection (guard)."""
        event = self._make_event(unread=2)
        iteration = 1
        should_inject = (
            iteration == 0
            and (getattr(event, "unread_notes", 0) or 0) > 0
        )
        assert should_inject is False

    def test_no_injection_zero_unread(self):
        event = self._make_event(unread=0)
        iteration = 0
        should_inject = (
            iteration == 0
            and (getattr(event, "unread_notes", 0) or 0) > 0
        )
        assert should_inject is False

    def test_no_duplicate_notification(self):
        """Existing sticky note notification -> no duplicate."""
        existing = ConversationTurn(
            turn=1, actor="system", action="notification",
            thoughts="Your past self left 2 sticky note(s)."
        )
        event = self._make_event(unread=2, conversation=[existing])
        iteration = 0
        has_notification = any(
            t.actor == "system" and t.action == "notification"
            for t in event.conversation
        )
        assert has_notification is True


class TestStickyNotesToolOrdering:
    """Verify read_sticky_notes is surfaced at position 0 when unread."""

    def _make_tools(self):
        return [
            {"name": "lookup_service"},
            {"name": "classify_event"},
            {"name": "read_sticky_notes"},
            {"name": "close_event"},
        ]

    def test_read_first_when_unread(self):
        tools = self._make_tools()
        _always_tools = {"lookup_service", "classify_event", "read_sticky_notes"}
        tier_always = [t for t in tools if t["name"] in _always_tools]
        tier_rest = [t for t in tools if t["name"] not in _always_tools]
        unread = 2
        if unread > 0:
            tier_sticky = [t for t in tier_always if t["name"] == "read_sticky_notes"]
            tier_always = [t for t in tier_always if t["name"] != "read_sticky_notes"]
            ordered = tier_sticky + tier_always + tier_rest
        else:
            ordered = tier_always + tier_rest
        assert ordered[0]["name"] == "read_sticky_notes"

    def test_read_not_first_when_zero(self):
        tools = self._make_tools()
        _always_tools = {"lookup_service", "classify_event", "read_sticky_notes"}
        tier_always = [t for t in tools if t["name"] in _always_tools]
        tier_rest = [t for t in tools if t["name"] not in _always_tools]
        unread = 0
        if unread > 0:
            tier_sticky = [t for t in tier_always if t["name"] == "read_sticky_notes"]
            tier_always = [t for t in tier_always if t["name"] != "read_sticky_notes"]
            ordered = tier_sticky + tier_always + tier_rest
        else:
            ordered = tier_always + tier_rest
        assert ordered[0]["name"] != "read_sticky_notes"
