# BlackBoard/tests/test_handoff.py
# @ai-rules:
# 1. [Pattern]: Tests for JARVIS handoff report pipeline (go_away -> collect -> Redis store).
# 2. [Constraint]: All Redis + broadcast interactions are mocked. No live connections.
# 3. [Gotcha]: LiveAPIAdapter.__init__ requires blackboard, archivist, pulse_tracker, broadcast.
"""Unit tests for JARVIS session handoff report pipeline."""
from __future__ import annotations

import asyncio
import json
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


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


@pytest.mark.asyncio
async def test_store_handoff_report():
    """_store_handoff_report writes to Redis and broadcasts."""
    adapter = _make_adapter()
    adapter._last_pulse_event_id = "evt-abc"
    redis = adapter._blackboard.redis

    await adapter._store_handoff_report("Tracking evt-abc in verify phase. No friction.")

    redis.rpush.assert_awaited_once()
    args = redis.rpush.call_args
    assert args[0][0] == "darwin:cortex:handoff_reports"
    entry = json.loads(args[0][1])
    assert "Tracking evt-abc" in entry["report"]
    assert entry["events_tracked"] == "evt-abc"
    assert "timestamp" in entry

    redis.expire.assert_awaited_once_with("darwin:cortex:handoff_reports", 86400)

    adapter._broadcast.assert_awaited_once()
    bc_args = adapter._broadcast.call_args[0][0]
    assert bc_args["type"] == "cortex_handoff_report"
    assert "Tracking evt-abc" in bc_args["report"]


@pytest.mark.asyncio
async def test_store_handoff_report_skips_empty():
    """Empty or 'no significant' reports are not stored."""
    adapter = _make_adapter()
    redis = adapter._blackboard.redis

    await adapter._store_handoff_report("")
    redis.rpush.assert_not_awaited()

    await adapter._store_handoff_report("No significant observations this session.")
    redis.rpush.assert_not_awaited()

    adapter._broadcast.assert_not_awaited()


@pytest.mark.asyncio
async def test_store_handoff_report_truncates():
    """Reports exceeding 4KB are truncated."""
    adapter = _make_adapter()
    long_report = "x" * 5000

    await adapter._store_handoff_report(long_report)

    entry = json.loads(adapter._blackboard.redis.rpush.call_args[0][1])
    assert len(entry["report"]) == 4000


@pytest.mark.asyncio
async def test_get_handoff_history():
    """_get_handoff_history formats Redis entries into readable text."""
    adapter = _make_adapter()
    ts1 = time.time() - 600
    ts2 = time.time() - 300
    entries = [
        json.dumps({"timestamp": ts1, "report": "Tracking evt-1 in triage."}),
        json.dumps({"timestamp": ts2, "report": "evt-1 moved to verify. No friction."}),
    ]
    adapter._blackboard.redis.lrange = AsyncMock(return_value=entries)

    result = await adapter._get_handoff_history()

    assert "Tracking evt-1 in triage." in result
    assert "evt-1 moved to verify" in result
    assert "---" in result
    assert result.count("[") == 2  # two timestamp brackets


@pytest.mark.asyncio
async def test_get_handoff_history_empty():
    """No reports returns empty string."""
    adapter = _make_adapter()
    adapter._blackboard.redis.lrange = AsyncMock(return_value=[])

    result = await adapter._get_handoff_history()

    assert result == ""


@pytest.mark.asyncio
async def test_text_buffer_gate_normal():
    """When NOT collecting handoff, text goes to _text_buffer."""
    adapter = _make_adapter()
    adapter._collecting_handoff = False
    adapter._last_pulse_event_id = "evt-1"

    msg = MagicMock()
    msg.text = "JARVIS observes friction."
    msg.go_away = None
    msg.session_resumption_update = None
    msg.server_content = MagicMock(turn_complete=False)
    msg.tool_call = None
    msg.tool_call_cancellation = None

    with patch("src.adapters.live_api_adapter.types", create=True):
        await adapter._process_message(msg)

    assert "JARVIS observes friction." in adapter._text_buffer
    assert adapter._handoff_buffer == []


@pytest.mark.asyncio
async def test_text_buffer_gate_handoff():
    """When collecting handoff, text goes to _handoff_buffer."""
    adapter = _make_adapter()
    adapter._collecting_handoff = True
    adapter._last_pulse_event_id = "evt-1"

    msg = MagicMock()
    msg.text = "Session notes: tracking evt-1."
    msg.go_away = None
    msg.session_resumption_update = None
    msg.server_content = MagicMock(turn_complete=False)
    msg.tool_call = None
    msg.tool_call_cancellation = None

    with patch("src.adapters.live_api_adapter.types", create=True):
        await adapter._process_message(msg)

    assert "Session notes: tracking evt-1." in adapter._handoff_buffer
    assert adapter._text_buffer == []
