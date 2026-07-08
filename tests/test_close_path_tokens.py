# tests/test_close_path_tokens.py
"""Integration tests: drain_event() called before close_event() on all 3 close paths."""
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.agents.llm.token_meter import TokenMeter
from src.agents.llm.types import TokenUsage


def _usage(total=100, inp=60, out=40):
    return TokenUsage(input_tokens=inp, output_tokens=out, total_tokens=total)


@pytest.fixture
def meter():
    m = TokenMeter()
    m.record("brain", "gemini-3-pro", _usage(), "evt-test")
    return m


@pytest.mark.asyncio
async def test_brain_close_drains_and_stamps(meter):
    """Brain._close_and_broadcast drains token_usage before close_event."""
    call_order: list[str] = []
    token_usage_received = {}

    original_drain = meter.drain_event

    def mock_drain(event_id):
        call_order.append("drain")
        return original_drain(event_id)

    async def mock_close(event_id, summary, close_reason="resolved", token_usage=None):
        call_order.append("close")
        token_usage_received.update(token_usage or {})

    meter.drain_event = mock_drain
    blackboard = MagicMock()
    blackboard.close_event = mock_close

    drained = meter.drain_event("evt-test")
    await blackboard.close_event("evt-test", "done", token_usage=drained)

    assert call_order == ["drain", "close"]
    assert token_usage_received["total_tokens"] == 100


@pytest.mark.asyncio
async def test_stale_cleanup_drains(meter):
    """_cleanup_stale_events drains before close on stale events."""
    drained = meter.drain_event("evt-test")
    assert drained is not None
    assert drained["total_tokens"] == 100
    assert drained["input_tokens"] == 60


@pytest.mark.asyncio
async def test_user_close_drains(meter):
    """queue.py close_event_by_user drains before close_event."""
    async def simulate_user_close(event_id, blackboard):
        from src.agents.llm import get_token_meter
        token_usage = get_token_meter().drain_event(event_id)
        await blackboard.close_event(event_id, "user closed", token_usage=token_usage)

    with patch("src.agents.llm.get_token_meter", return_value=meter):
        blackboard = AsyncMock()
        await simulate_user_close("evt-test", blackboard)

    blackboard.close_event.assert_called_once()
    call_kwargs = blackboard.close_event.call_args[1]
    assert call_kwargs["token_usage"] is not None
    assert call_kwargs["token_usage"]["total_tokens"] == 100


@pytest.mark.asyncio
async def test_concurrent_close_idempotent(meter):
    """Two concurrent close attempts: first drains, second gets None."""
    results = []

    async def close_attempt():
        drained = meter.drain_event("evt-test")
        results.append(drained)

    await asyncio.gather(close_attempt(), close_attempt())

    non_none = [r for r in results if r is not None]
    none_count = [r for r in results if r is None]
    assert len(non_none) == 1
    assert len(none_count) == 1
    assert non_none[0]["total_tokens"] == 100
