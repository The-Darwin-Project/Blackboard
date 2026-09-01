# BlackBoard/tests/test_agent_ws_handler.py
# @ai-rules:
# 1. [Constraint]: Transport-only tests for websocket heartbeat and cleanup; no Brain or Redis.
# 2. [Pattern]: Drive N heartbeat cycles via patched asyncio.sleep; send_json succeeds so
#    the missed-ping check runs. Raise RuntimeError("stop") from sleep after max_cycles
#    to bound the infinite loop. Simulate pongs by resetting missed_pings during sleep.
# 3. [Gotcha]: agent_websocket_handler cleanup is asserted through registry.unregister after disconnect.
"""Unit and integration tests for websocket heartbeat pong deadlines."""
from __future__ import annotations

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import WebSocketDisconnect

from src.agents.agent_ws_handler import (
    _PONG_MISS_THRESHOLD,
    _heartbeat,
    agent_websocket_handler,
)


def _make_ws() -> MagicMock:
    ws = MagicMock()
    ws.send_json = AsyncMock()
    ws.close = AsyncMock()
    ws.accept = AsyncMock()
    return ws


def _make_sleep(
    max_cycles: int,
    missed_pings: list[int],
    last_pong: list[float],
    pong_before_cycles: frozenset[int] = frozenset(),
):
    """Advance one heartbeat cycle per sleep; reset missed_pings to mimic a pong."""
    n = {"i": 0}

    async def _sleep(_seconds: int) -> None:
        n["i"] += 1
        if n["i"] > max_cycles:
            raise RuntimeError("stop")
        if n["i"] in pong_before_cycles:
            missed_pings[0] = 0
            last_pong[0] = time.monotonic()

    return _sleep


async def _run_heartbeat(
    ws: MagicMock,
    last_pong: list[float],
    missed_pings: list[int],
    max_cycles: int,
    pong_before_cycles: frozenset[int] = frozenset(),
    agent_id: str = "agent-1",
) -> None:
    sleep = _make_sleep(max_cycles, missed_pings, last_pong, pong_before_cycles)
    with patch("src.agents.agent_ws_handler.asyncio.sleep", new=sleep):
        try:
            await _heartbeat(ws, last_pong, missed_pings, agent_id, interval=30)
        except RuntimeError as exc:
            if str(exc) != "stop":
                raise


class TestHeartbeatPongDeadline:
    @pytest.mark.asyncio
    async def test_pong_received_resets_deadline(self):
        ws = _make_ws()
        last_pong = [time.monotonic()]
        missed_pings = [0]
        # Pong before every ping after the first: missed oscillates 0 → 1 → 0.
        await _run_heartbeat(
            ws, last_pong, missed_pings, max_cycles=5,
            pong_before_cycles=frozenset({2, 3, 4, 5}),
        )
        assert ws.send_json.await_count == 5
        ws.close.assert_not_awaited()
        assert missed_pings[0] == 1

    @pytest.mark.asyncio
    async def test_partial_misses_recover_without_close(self):
        ws = _make_ws()
        last_pong = [time.monotonic()]
        missed_pings = [0]
        # Two unanswered pings, then a pong, then one more ping. Threshold is 3.
        await _run_heartbeat(
            ws, last_pong, missed_pings, max_cycles=3,
            pong_before_cycles=frozenset({3}),
        )
        assert ws.send_json.await_count == 3
        ws.close.assert_not_awaited()
        assert missed_pings[0] == 1

    @pytest.mark.asyncio
    async def test_pong_deadline_exceeded_closes_on_third_cycle(self):
        assert _PONG_MISS_THRESHOLD == 3
        ws = _make_ws()
        last_pong = [0.0]
        missed_pings = [0]
        await _run_heartbeat(ws, last_pong, missed_pings, max_cycles=10)
        assert ws.send_json.await_count == 3
        assert missed_pings[0] == 3
        ws.close.assert_awaited_once_with(code=1001, reason="Pong deadline exceeded")

    @pytest.mark.asyncio
    async def test_ping_send_failure_closes_websocket(self):
        ws = _make_ws()
        ws.send_json.side_effect = RuntimeError("broken pipe")
        last_pong = [time.monotonic()]
        missed_pings = [0]
        await _run_heartbeat(ws, last_pong, missed_pings, max_cycles=3)
        ws.close.assert_awaited_once_with(code=1001, reason="Heartbeat ping failed")
        assert missed_pings[0] == 0

    @pytest.mark.asyncio
    async def test_ping_send_failure_close_error_does_not_propagate(self):
        ws = _make_ws()
        ws.send_json.side_effect = RuntimeError("broken pipe")
        ws.close.side_effect = RuntimeError("already gone")
        last_pong = [time.monotonic()]
        missed_pings = [0]
        await _run_heartbeat(ws, last_pong, missed_pings, max_cycles=3)
        ws.close.assert_awaited_once_with(code=1001, reason="Heartbeat ping failed")


class TestAgentWebsocketHandlerCleanup:
    @pytest.mark.asyncio
    async def test_pong_timeout_close_triggers_unregister(self):
        ws = _make_ws()
        closed = asyncio.Event()
        receive_count = 0

        async def receive_json():
            nonlocal receive_count
            receive_count += 1
            if receive_count == 1:
                return {
                    "type": "register",
                    "agent_id": "agent-1",
                    "role": "developer",
                    "capabilities": [],
                    "cli": "gemini",
                    "model": "test",
                }
            await closed.wait()
            raise WebSocketDisconnect()

        async def close(*, code: int, reason: str) -> None:
            closed.set()

        ws.receive_json = AsyncMock(side_effect=receive_json)
        ws.close = AsyncMock(side_effect=close)

        registry = MagicMock()
        registry.register = AsyncMock()
        registry.unregister = AsyncMock()
        registry.mark_busy = AsyncMock()
        bridge = MagicMock()

        async def heartbeat_timeout(
            websocket, last_pong, missed_pings, agent_id, interval=30,
        ):
            await websocket.close(code=1001, reason="Pong deadline exceeded")

        with patch("src.agents.agent_ws_handler._heartbeat", side_effect=heartbeat_timeout):
            await agent_websocket_handler(ws, registry, bridge)

        registry.register.assert_awaited_once()
        registry.unregister.assert_awaited_once_with("agent-1")
        ws.close.assert_any_await(code=1001, reason="Pong deadline exceeded")
