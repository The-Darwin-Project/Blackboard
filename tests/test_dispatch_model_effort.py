# tests/test_dispatch_model_effort.py
# @ai-rules:
# 1. [Constraint]: No Redis, no real WS -- MagicMock agent connection + real TaskBridge.
# 2. [Pattern]: send_json side effect enqueues a "result" message so dispatch_to_agent unblocks.
"""Verify dispatch_to_agent forwards model/effort on the WS task payload (mirrors `mode`)."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.agents.dispatch import dispatch_to_agent, KNOWN_EFFORT_LEVELS
from src.agents.task_bridge import TaskBridge


class _FakeAgentConn:
    def __init__(self, bridge: TaskBridge) -> None:
        self.agent_id = "agent-1"
        self.busy = False
        self.current_event_id = None
        self.current_task_id = None
        self.current_role = None
        self.captured: dict = {}
        self._bridge = bridge
        self.ws = MagicMock()
        self.ws.send_json = AsyncMock(side_effect=self._on_send)

    async def _on_send(self, payload: dict) -> None:
        self.captured = payload
        self._bridge.put(payload["task_id"], {
            "type": "result", "output": "done", "source": "findings",
        })


def _make_registry(agent_conn: _FakeAgentConn):
    registry = AsyncMock()
    registry.get_available = AsyncMock(return_value=agent_conn)
    registry.get_by_id = AsyncMock(return_value=agent_conn)
    registry.mark_busy = AsyncMock()
    registry.mark_idle = AsyncMock()
    return registry


class TestModelEffortWSPayload:
    @pytest.mark.asyncio
    async def test_model_and_effort_included_in_ws_payload(self):
        bridge = TaskBridge()
        conn = _FakeAgentConn(bridge)
        registry = _make_registry(conn)

        result, _ = await dispatch_to_agent(
            registry, bridge, "architect", "evt-1", "do the thing",
            model="claude-opus-4-6[1m]", effort="high",
        )

        assert conn.captured["model"] == "claude-opus-4-6[1m]"
        assert conn.captured["effort"] == "high"
        assert result == "done"

    @pytest.mark.asyncio
    async def test_empty_model_and_effort_default_in_ws_payload(self):
        """Local dispatch (no override) sends model="" -- sidecar falls back to its own env."""
        bridge = TaskBridge()
        conn = _FakeAgentConn(bridge)
        registry = _make_registry(conn)

        await dispatch_to_agent(registry, bridge, "developer", "evt-2", "implement the fix")

        assert conn.captured["model"] == ""
        assert conn.captured["effort"] == ""

    @pytest.mark.asyncio
    async def test_unknown_effort_is_fail_open(self, caplog):
        """Unknown effort logs a warning but dispatch still proceeds (mirrors `mode`)."""
        bridge = TaskBridge()
        conn = _FakeAgentConn(bridge)
        registry = _make_registry(conn)

        result, _ = await dispatch_to_agent(
            registry, bridge, "qe", "evt-3", "verify the fix", effort="ludicrous",
        )

        assert result == "done"
        assert conn.captured["effort"] == "ludicrous"

    def test_known_effort_levels_contract(self):
        assert KNOWN_EFFORT_LEVELS == frozenset({"low", "medium", "high", "max"})
