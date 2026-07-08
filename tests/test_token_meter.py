# tests/test_token_meter.py
"""TokenMeter unit tests: snapshot, drain, platform totals, system bucket."""
from src.agents.llm.token_meter import TokenMeter
from src.agents.llm.types import TokenUsage

EXPECTED_KEYS = {"input_tokens", "output_tokens", "thinking_tokens", "cached_tokens",
                 "tool_use_tokens", "total_tokens", "calls"}


def _usage(inp=0, out=0, think=0, cached=0, tool=0, total=0):
    return TokenUsage(input_tokens=inp, output_tokens=out, thinking_tokens=think,
                      cached_tokens=cached, tool_use_tokens=tool, total_tokens=total)


def test_record_and_snapshot_returns_deltas():
    meter = TokenMeter()
    meter.record("brain", "gemini-3-pro", _usage(inp=100, out=50, total=150), "evt-1")
    meter.record("aligner", "gemini-3.5-flash", _usage(inp=20, out=10, total=30))
    meter.record("brain", "gemini-3-pro", _usage(inp=80, out=40, total=120), "evt-1")

    snap = meter.snapshot()
    assert set(snap.keys()) == EXPECTED_KEYS
    assert snap["input_tokens"] == 200  # 100+20+80
    assert snap["output_tokens"] == 100
    assert snap["total_tokens"] == 300
    assert snap["calls"] == 3


def test_snapshot_resets_interval_counters():
    meter = TokenMeter()
    meter.record("brain", "m", _usage(total=100))
    meter.snapshot()

    snap2 = meter.snapshot()
    assert snap2["total_tokens"] == 0
    assert snap2["calls"] == 0


def test_platform_totals_are_cumulative():
    meter = TokenMeter()
    meter.record("brain", "m", _usage(total=100))
    meter.snapshot()  # resets interval
    meter.record("brain", "m", _usage(total=50))

    totals = meter.get_platform_totals()
    assert totals["total_tokens"] == 150
    assert totals["calls"] == 2


def test_drain_event_returns_totals_and_clears():
    meter = TokenMeter()
    meter.record("brain", "m", _usage(inp=100, out=50, think=20, total=170), "evt-a")
    meter.record("brain", "m", _usage(inp=30, out=10, total=40), "evt-a")

    drained = meter.drain_event("evt-a")
    assert drained is not None
    assert set(drained.keys()) == EXPECTED_KEYS
    assert drained["input_tokens"] == 130
    assert drained["output_tokens"] == 60
    assert drained["thinking_tokens"] == 20
    assert drained["calls"] == 2


def test_drain_event_idempotent():
    meter = TokenMeter()
    meter.record("brain", "m", _usage(total=100), "evt-b")
    first = meter.drain_event("evt-b")
    assert first is not None

    second = meter.drain_event("evt-b")
    assert second is None


def test_system_bucket_not_in_drain():
    meter = TokenMeter()
    meter.record("aligner", "m", _usage(total=999))
    meter.record("brain", "m", _usage(total=50), "evt-c")

    drained = meter.drain_event("evt-c")
    assert drained is not None
    assert drained["total_tokens"] == 50

    drained_system = meter.drain_event("nonexistent")
    assert drained_system is None

    totals = meter.get_platform_totals()
    assert totals["total_tokens"] == 1049
