"""Tests for integration handlers."""
import pytest
from unittest.mock import AsyncMock, MagicMock
from src.agents.handlers_integration import handle_search_open_incidents

@pytest.mark.asyncio
async def test_empty_search_incidents_pulse_score():
    ctx = MagicMock()
    adapter = AsyncMock()
    adapter.search_open_incidents.return_value = []
    ctx.get_incident_adapter.return_value = adapter
    ctx.next_turn_number = AsyncMock(return_value=1)
    ctx.append_and_broadcast = AsyncMock()
    ctx.emit_pulse = AsyncMock()
    
    await handle_search_open_incidents(ctx, "evt-1", {}, None)
    
    ctx.emit_pulse.assert_called_once_with("evt-1", [("tool:search_open_incidents", "tool", 1.0)])

@pytest.mark.asyncio
async def test_failed_search_incidents_pulse_score():
    ctx = MagicMock()
    adapter = AsyncMock()
    adapter.search_open_incidents.side_effect = RuntimeError("Failed")
    ctx.get_incident_adapter.return_value = adapter
    ctx.next_turn_number = AsyncMock(return_value=1)
    ctx.append_and_broadcast = AsyncMock()
    ctx.emit_pulse = AsyncMock()
    
    await handle_search_open_incidents(ctx, "evt-1", {}, None)
    
    ctx.emit_pulse.assert_called_once_with("evt-1", [("tool:search_open_incidents", "tool", 0.0)])
