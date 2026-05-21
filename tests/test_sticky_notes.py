# tests/test_sticky_notes.py
# @ai-rules:
# 1. [Pattern]: Tests sticky notes data model, tool gating, and context header injection.
# 2. [Constraint]: No Redis, no async for model/gating tests. Async only for blackboard method.
"""Unit tests for FRIDAY sticky notes feature."""
import json
import pytest
from unittest.mock import MagicMock
from src.models import EventDocument, EventInput


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


class TestStickyNotesContextHeader:
    def test_no_indicator_when_zero(self):
        from src.agents.brain import Brain
        event = MagicMock()
        event.conversation = []
        event.brain_phase = "investigate"
        event.event.evidence.brain_domain = "complicated"
        event.event.evidence.domain = "complicated"
        event.event.evidence.brain_severity = "info"
        event.event.evidence.severity = "info"
        event.unread_notes = 0
        header = Brain._build_event_state_header(event)
        assert "unread note" not in header

    def test_indicator_when_unread(self):
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
        assert "3 unread note(s)" in header
