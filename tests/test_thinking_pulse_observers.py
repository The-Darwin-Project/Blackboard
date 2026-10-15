# tests/test_thinking_pulse_observers.py
# @ai-rules:
# 1. [Constraint]: Covers the downstream consumers of thinking pulses added in PR #281:
#    PulseTracker redaction, LiveAPIAdapter observer throttle + pulse-history tally.
# 2. [Pattern]: LiveAPIAdapter built via __new__ with only the attributes the method under test reads
#    (same convention as test_live_api_adapter._make_connect_adapter). No live Redis / Live API.
"""Tests for thinking-pulse consumers: PulseTracker redaction and LiveAPIAdapter handling."""
from __future__ import annotations

import json
import time
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.adapters import live_api_adapter as adapter_mod
from src.adapters.live_api_adapter import LiveAPIAdapter
from src.memory.pulse import Pulse, PulseBatch
from src.memory.pulse_tracker import LOG_KEY, PulseTracker

SECRET = "hunter2hunter2hunter2"


def _thinking_batch(event_id="evt-1", reasoning="reasoning"):
    return PulseBatch(
        event_id=event_id, pulses=[Pulse("thinking:friday", "thinking", 1.0, True)],
        reasoning=reasoning, event_source="chat",
    )


# ---------------------------------------------------------------------------
# PulseTracker: reasoning is redacted before Redis log, broadcast, observers
# ---------------------------------------------------------------------------
class TestPulseTrackerRedaction:
    def _tracker(self):
        pipe = MagicMock()
        pipe.execute = AsyncMock()
        redis = MagicMock()
        redis.pipeline = MagicMock(return_value=pipe)
        broadcast = AsyncMock()
        return PulseTracker(redis, broadcast), pipe, broadcast

    @pytest.mark.asyncio
    async def test_reasoning_redacted_in_log_and_broadcast_and_observer(self):
        tracker, pipe, broadcast = self._tracker()
        observer = MagicMock()
        observer.send_pulse = AsyncMock()
        tracker.add_observer(observer)
        batch = _thinking_batch(reasoning=f"call tal@example.com with password={SECRET} now")

        await tracker.on_pulse_batch(batch)

        logged = json.loads(pipe.xadd.call_args.args[1]["batch"])["reasoning"]
        broadcasted = broadcast.await_args.args[0]["batch"]["reasoning"]
        for text in (logged, broadcasted):
            assert SECRET not in text and "tal@example.com" not in text
        import asyncio
        await asyncio.sleep(0)  # let the observer task run
        assert SECRET not in observer.send_pulse.await_args.args[0].reasoning
        assert pipe.xadd.call_args.args[0] == LOG_KEY

    @pytest.mark.asyncio
    async def test_original_batch_not_mutated_and_none_reasoning_ok(self):
        tracker, pipe, _ = self._tracker()
        batch = _thinking_batch(reasoning=f"password={SECRET}")
        await tracker.on_pulse_batch(batch)
        assert SECRET in batch.reasoning  # caller's object untouched (dataclasses.replace)

        none_batch = _thinking_batch(reasoning=None)
        await tracker.on_pulse_batch(none_batch)
        assert json.loads(pipe.xadd.call_args.args[1]["batch"])["reasoning"] is None


# ---------------------------------------------------------------------------
# LiveAPIAdapter.send_pulse: thinking-only pulses are throttled per event
# ---------------------------------------------------------------------------
def _observer_adapter():
    a = LiveAPIAdapter.__new__(LiveAPIAdapter)
    a._last_pulse_event_id = None
    a._last_pulse_time = 0
    a._active_meta_event_id = None
    a._generating_report = False
    a._last_thinking_forward = {}
    a._session = MagicMock()
    a._session.send = AsyncMock()
    a._seen_neurons = set()
    a._neuron_labels = {}
    return a


class TestObserverThinkingThrottle:
    @pytest.mark.asyncio
    async def test_second_thinking_pulse_within_window_is_dropped(self):
        a = _observer_adapter()
        await a.send_pulse(_thinking_batch())
        await a.send_pulse(_thinking_batch())
        assert a._session.send.await_count == 1

    @pytest.mark.asyncio
    async def test_thinking_pulse_forwarded_again_after_window(self):
        a = _observer_adapter()
        await a.send_pulse(_thinking_batch())
        a._last_thinking_forward["evt-1"] -= adapter_mod._THINKING_FORWARD_MIN_INTERVAL_S + 1
        await a.send_pulse(_thinking_batch())
        assert a._session.send.await_count == 2

    @pytest.mark.asyncio
    async def test_throttle_is_per_event(self):
        a = _observer_adapter()
        await a.send_pulse(_thinking_batch("evt-1"))
        await a.send_pulse(_thinking_batch("evt-2"))
        assert a._session.send.await_count == 2

    @pytest.mark.asyncio
    async def test_non_thinking_and_mixed_pulses_never_throttled(self):
        a = _observer_adapter()
        tool = PulseBatch(event_id="evt-1", pulses=[Pulse("tool:classify_event", "tool", 1.0, True)])
        mixed = PulseBatch(event_id="evt-1", pulses=[
            Pulse("thinking:friday", "thinking", 1.0, True), Pulse("tool:set_phase", "tool", 1.0, True),
        ])
        await a.send_pulse(_thinking_batch())   # arms the throttle
        await a.send_pulse(tool)
        await a.send_pulse(tool)
        await a.send_pulse(mixed)
        assert a._session.send.await_count == 4

    @pytest.mark.asyncio
    async def test_forwarded_text_is_redacted(self):
        a = _observer_adapter()
        await a.send_pulse(_thinking_batch(reasoning=f"password={SECRET}"))
        assert SECRET not in a._session.send.await_args.kwargs["input"]


# ---------------------------------------------------------------------------
# _tool_get_pulse_history: thinking tally
# ---------------------------------------------------------------------------
class TestPulseHistoryThinkingTally:
    @pytest.mark.asyncio
    async def test_thinking_pulses_tallied_and_not_counted_as_tools(self):
        a = LiveAPIAdapter.__new__(LiveAPIAdapter)
        now = time.time()
        a._pulse_tracker = MagicMock()
        a._pulse_tracker.get_batches = AsyncMock(return_value=[
            {"timestamp": now, "pulses": [{"neuron_id": "thinking:friday", "neuron_type": "thinking"}]},
            {"timestamp": now, "pulses": [{"neuron_id": "thinking:friday", "neuron_type": "thinking"}]},
            {"timestamp": now, "pulses": [{"neuron_id": "tool:classify_event", "neuron_type": "tool"}]},
            {"timestamp": now, "pulses": [{"neuron_id": "phase:triage", "neuron_type": "phase"}]},
        ])
        a._blackboard = MagicMock()
        a._blackboard.get_event = AsyncMock(return_value=None)

        out = await a._tool_get_pulse_history("evt-1", 10)

        assert "Thinking pulses: 2" in out
        assert "thinking:friday (2 times)" in out
        assert "Tool trail: [classify_event x1]" in out  # thinking never leaks into the trail
        assert "triage" in out

    @pytest.mark.asyncio
    async def test_zero_thinking_pulses_reported_as_zero(self):
        a = LiveAPIAdapter.__new__(LiveAPIAdapter)
        a._pulse_tracker = MagicMock()
        a._pulse_tracker.get_batches = AsyncMock(return_value=[
            {"timestamp": time.time(), "pulses": [{"neuron_id": "tool:x", "neuron_type": "tool"}]},
        ])
        a._blackboard = MagicMock()
        a._blackboard.get_event = AsyncMock(return_value=None)
        assert "Thinking pulses: 0" in await a._tool_get_pulse_history("evt-1", 10)
