# tests/test_jarvis_drilldown_tools.py
# @ai-rules:
# 1. [Pattern]: Tests for JARVIS drill-down tools -- read_event_turns + view_event_blackboard
#    evidence-gap fix. Mirrors _make_adapter() mock pattern from test_handoff.py.
# 2. [Constraint]: All Redis + broadcast interactions are mocked. No live connections.
#    Each test sets blackboard.get_event = AsyncMock(return_value=...) explicitly.
# 3. [Gotcha]: Guard order in _tool_read_event_turns clamps to_turn to len(conversation) --
#    fixtures must include enough turns for the requested range to stay valid.
"""Unit tests for JARVIS event drill-down tools (read_event_turns, view_event_blackboard)."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.models import ConversationTurn, EventDocument, EventInput


def _make_adapter():
    """Build a LiveAPIAdapter with all dependencies mocked."""
    from src.adapters.live_api_adapter import LiveAPIAdapter

    blackboard = MagicMock()
    blackboard.redis = AsyncMock()
    archivist = AsyncMock()
    pulse_tracker = MagicMock()
    broadcast = AsyncMock()

    adapter = LiveAPIAdapter(
        blackboard=blackboard,
        archivist=archivist,
        pulse_tracker=pulse_tracker,
        broadcast=broadcast,
    )
    return adapter


def _make_turn(**kwargs) -> ConversationTurn:
    defaults = {"turn": 1, "actor": "brain", "action": "tool_result"}
    defaults.update(kwargs)
    return ConversationTurn(**defaults)


def _make_event(*turns: ConversationTurn, **overrides) -> EventDocument:
    defaults = dict(
        source="chat",
        service="test-service",
        event=EventInput(reason="test", evidence="test evidence"),
        conversation=list(turns),
    )
    defaults.update(overrides)
    return EventDocument(**defaults)


# -----------------------------------------------------------------------------
# read_event_turns
# -----------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_read_turns_both_fields_shown():
    """Turn with both thoughts and evidence must show both, labeled."""
    adapter = _make_adapter()
    turn = _make_turn(turn=1, thoughts="Deciding next step", evidence="MR State: merged")
    event = _make_event(turn)
    adapter._blackboard.get_event = AsyncMock(return_value=event)

    result = await adapter._tool_read_event_turns("evt-1", 1, 1)

    assert "Thoughts: Deciding next step" in result
    assert "Evidence: MR State: merged" in result


@pytest.mark.asyncio
async def test_read_turns_waitingFor_in_header():
    """waitingFor field must surface as tool=<name> in the turn header."""
    adapter = _make_adapter()
    turn = _make_turn(turn=1, waitingFor="refresh_gitlab_context")
    event = _make_event(turn)
    adapter._blackboard.get_event = AsyncMock(return_value=event)

    result = await adapter._tool_read_event_turns("evt-1", 1, 1)

    assert "tool=refresh_gitlab_context" in result


@pytest.mark.asyncio
async def test_read_turns_range_clamp():
    """Requesting more than 10 turns clamps to the first 10 with a note."""
    adapter = _make_adapter()
    turns = [_make_turn(turn=i) for i in range(1, 21)]
    event = _make_event(*turns)
    adapter._blackboard.get_event = AsyncMock(return_value=event)

    result = await adapter._tool_read_event_turns("evt-1", 1, 15)

    assert "Turn 1 " in result
    assert "Turn 10 " in result
    assert "Turn 11 " not in result
    assert "(showing first 10 of 15 turns)" in result


@pytest.mark.asyncio
async def test_read_turns_invalid_range():
    """from_turn beyond the clamped to_turn returns a descriptive error."""
    adapter = _make_adapter()
    turns = [_make_turn(turn=i) for i in range(1, 11)]
    event = _make_event(*turns)
    adapter._blackboard.get_event = AsyncMock(return_value=event)

    result = await adapter._tool_read_event_turns("evt-1", 50, 100)

    assert "Error" in result
    assert "50" in result
    assert "10" in result


@pytest.mark.asyncio
async def test_read_turns_parse_error():
    """Non-integer from_turn/to_turn returns a clean error, not a stack trace."""
    adapter = _make_adapter()

    result = await adapter._tool_read_event_turns("evt-1", "first", 5)

    assert "must be integers" in result


@pytest.mark.asyncio
async def test_read_turns_empty_conversation():
    """Event with zero conversation turns returns a dedicated message."""
    adapter = _make_adapter()
    event = _make_event()
    adapter._blackboard.get_event = AsyncMock(return_value=event)

    result = await adapter._tool_read_event_turns("evt-1", 1, 5)

    assert "has no conversation turns" in result


@pytest.mark.asyncio
async def test_read_turns_event_not_found():
    """Missing event returns an error, not an exception."""
    adapter = _make_adapter()
    adapter._blackboard.get_event = AsyncMock(return_value=None)

    result = await adapter._tool_read_event_turns("evt-missing", 1, 5)

    assert "not found" in result


@pytest.mark.asyncio
async def test_read_turns_truncation_marker():
    """A per-turn block over 2000 chars is truncated with a marker."""
    adapter = _make_adapter()
    turn = _make_turn(turn=1, evidence="E" * 3000)
    event = _make_event(turn)
    adapter._blackboard.get_event = AsyncMock(return_value=event)

    result = await adapter._tool_read_event_turns("evt-1", 1, 1)

    assert "...(truncated at 2000 chars)" in result


@pytest.mark.asyncio
async def test_read_turns_filters_by_turn_number():
    """Requesting a single turn number must not leak adjacent turns."""
    adapter = _make_adapter()
    turns = [_make_turn(turn=i, thoughts=f"content for turn {i}") for i in range(1, 8)]
    event = _make_event(*turns)
    adapter._blackboard.get_event = AsyncMock(return_value=event)

    result = await adapter._tool_read_event_turns("evt-1", 6, 6)

    assert "content for turn 6" in result
    assert "content for turn 5" not in result
    assert "content for turn 7" not in result


# -----------------------------------------------------------------------------
# view_event_blackboard (evidence gap fix)
# -----------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_view_blackboard_evidence_visible():
    """Evidence-only turns (no thoughts) must be visible in the summary view."""
    adapter = _make_adapter()
    turn = _make_turn(turn=1, thoughts=None, evidence="MR State: merged\nPipeline: success")
    event = _make_event(turn)
    adapter._blackboard.get_event = AsyncMock(return_value=event)

    result = await adapter._tool_view_event_blackboard("evt-1")

    assert "MR State:" in result


@pytest.mark.asyncio
async def test_view_blackboard_300_char_cap():
    """Per-turn content in the summary view is capped at 300 chars."""
    adapter = _make_adapter()
    turn = _make_turn(turn=1, thoughts=None, evidence="E" * 500)
    event = _make_event(turn)
    adapter._blackboard.get_event = AsyncMock(return_value=event)

    result = await adapter._tool_view_event_blackboard("evt-1")

    assert ("E" * 300) in result
    assert ("E" * 301) not in result
