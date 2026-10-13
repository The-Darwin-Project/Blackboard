# BlackBoard/tests/test_blackboard_orphan_pruning.py
"""Tests for Blackboard active event orphan pruning and bytes normalization."""
import json
import pytest
from unittest.mock import AsyncMock

from src.state.blackboard import BlackboardState



@pytest.fixture
def blackboard_mock():
    """Create a BlackboardState instance with mocked Redis."""
    bb = BlackboardState.__new__(BlackboardState)
    bb.redis = AsyncMock()
    return bb


@pytest.mark.asyncio
async def test_find_active_event_prunes_none_tombstone(blackboard_mock):
    """T-5: Evicts missing event (None tombstone) from EVENT_ACTIVE via srem."""
    bb = blackboard_mock
    bb.redis.smembers.return_value = ["evt-tombstone", "evt-live"]

    async def mock_get(key):
        if key == f"{bb.EVENT_PREFIX}evt-tombstone":
            return None
        if key == f"{bb.EVENT_PREFIX}evt-live":
            return json.dumps({"source": "jarvis", "status": "active"})
        return None

    bb.redis.get.side_effect = mock_get

    result = await bb.find_active_event_by_source("jarvis")

    assert result == "evt-live"
    bb.redis.srem.assert_awaited_once_with(bb.EVENT_ACTIVE, "evt-tombstone")


@pytest.mark.asyncio
async def test_find_active_event_prunes_closed_status(blackboard_mock):
    """T-5: Evicts status='closed' event from EVENT_ACTIVE via srem."""
    bb = blackboard_mock
    bb.redis.smembers.return_value = ["evt-closed", "evt-live"]

    async def mock_get(key):
        if key == f"{bb.EVENT_PREFIX}evt-closed":
            return json.dumps({"source": "jarvis", "status": "closed"})
        if key == f"{bb.EVENT_PREFIX}evt-live":
            return json.dumps({"source": "jarvis", "status": "active"})
        return None

    bb.redis.get.side_effect = mock_get

    result = await bb.find_active_event_by_source("jarvis")

    assert result == "evt-live"
    bb.redis.srem.assert_awaited_once_with(bb.EVENT_ACTIVE, "evt-closed")


@pytest.mark.asyncio
async def test_find_active_event_prunes_resolved_status(blackboard_mock):
    """T-5: Evicts status='resolved' event from EVENT_ACTIVE via srem."""
    bb = blackboard_mock
    bb.redis.smembers.return_value = ["evt-resolved", "evt-live"]

    async def mock_get(key):
        if key == f"{bb.EVENT_PREFIX}evt-resolved":
            return json.dumps({"source": "jarvis", "status": "resolved"})
        if key == f"{bb.EVENT_PREFIX}evt-live":
            return json.dumps({"source": "jarvis", "status": "active"})
        return None

    bb.redis.get.side_effect = mock_get

    result = await bb.find_active_event_by_source("jarvis")

    assert result == "evt-live"
    bb.redis.srem.assert_awaited_once_with(bb.EVENT_ACTIVE, "evt-resolved")


@pytest.mark.asyncio
async def test_find_active_event_handles_bytes_without_key_corruption(blackboard_mock):
    """T-5: Normalizes bytes members so Redis get key is not corrupted (b'...') and srem receives original bytes."""
    bb = blackboard_mock
    bb.redis.smembers.return_value = [b"evt-bytes-closed", b"evt-bytes-active"]

    called_keys = []

    async def mock_get(key):
        called_keys.append(key)
        if key == f"{bb.EVENT_PREFIX}evt-bytes-closed":
            return json.dumps({"source": "jarvis", "status": "closed"})
        if key == f"{bb.EVENT_PREFIX}evt-bytes-active":
            return json.dumps({"source": "jarvis", "status": "active"})
        return None

    bb.redis.get.side_effect = mock_get

    result = await bb.find_active_event_by_source("jarvis")

    assert result == "evt-bytes-active"
    assert isinstance(result, str)
    # Check that keys queried did not contain b'...' repr artifacts
    for key in called_keys:
        assert "b'" not in key
        assert key.startswith(bb.EVENT_PREFIX)

    # srem should have been called with the exact member from smembers (bytes)
    bb.redis.srem.assert_awaited_once_with(bb.EVENT_ACTIVE, b"evt-bytes-closed")


@pytest.mark.asyncio
async def test_find_active_event_source_mismatch_not_returned_nor_pruned(blackboard_mock):
    """Active events for other sources are not returned and not pruned."""
    bb = blackboard_mock
    bb.redis.smembers.return_value = ["evt-github"]
    bb.redis.get.return_value = json.dumps({"source": "github", "status": "active"})

    result = await bb.find_active_event_by_source("jarvis")

    assert result is None
    bb.redis.srem.assert_not_called()


@pytest.mark.asyncio
async def test_find_active_event_empty_set_returns_none(blackboard_mock):
    """Empty EVENT_ACTIVE returns None without srem calls."""
    bb = blackboard_mock
    bb.redis.smembers.return_value = []

    result = await bb.find_active_event_by_source("jarvis")

    assert result is None
    bb.redis.srem.assert_not_called()


@pytest.mark.asyncio
async def test_find_active_event_corrupted_json_skipped_not_pruned(blackboard_mock):
    """Corrupted JSON payload in active key is safely skipped without crash or false pruning."""
    bb = blackboard_mock
    bb.redis.smembers.return_value = ["evt-corrupted", "evt-live"]

    async def mock_get(key):
        if key == f"{bb.EVENT_PREFIX}evt-corrupted":
            return "not-valid-json"
        if key == f"{bb.EVENT_PREFIX}evt-live":
            return json.dumps({"source": "jarvis", "status": "active"})
        return None

    bb.redis.get.side_effect = mock_get

    result = await bb.find_active_event_by_source("jarvis")

    assert result == "evt-live"
    bb.redis.srem.assert_not_called()


@pytest.mark.asyncio
async def test_get_active_events_normalizes_bytes(blackboard_mock):
    """get_active_events normalizes bytes members to strings."""
    bb = blackboard_mock
    bb.redis.smembers.return_value = [b"evt-1", "evt-2", b"evt-3"]

    result = await bb.get_active_events()

    assert result == ["evt-1", "evt-2", "evt-3"]
    assert all(isinstance(x, str) for x in result)

