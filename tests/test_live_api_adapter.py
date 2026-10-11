"""Tests for LiveAPIAdapter duplicate review handling."""
import pytest
from unittest.mock import AsyncMock, MagicMock
from src.adapters.live_api_adapter import LiveAPIAdapter

@pytest.mark.asyncio
async def test_duplicate_system_review_returns_existing():
    adapter = LiveAPIAdapter.__new__(LiveAPIAdapter)
    adapter._shadow = False
    adapter._brain = None
    adapter._blackboard = MagicMock()
    adapter._blackboard.get_active_events = AsyncMock(return_value=["evt-1"])
    adapter._blackboard.find_active_event_by_source = AsyncMock(return_value="evt-12345")
    
    result = await adapter._tool_create_system_review(reason="test review pattern")
    assert "evt-12345" in result
    assert "Review already active" in result
