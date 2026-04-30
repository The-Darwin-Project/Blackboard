# tests/test_models.py
# @ai-rules:
# 1. [Pattern]: Pydantic model validation tests. Add tests for each new model in src/models.py.
# 2. [Constraint]: Test both valid construction and schema generation for API contract stability.
# 3. [Pattern]: EventDocument backward-compat tests verify that Redis blobs without new fields deserialize with defaults.
import json

import pytest
from src.models import EventDocument, EventInput, HealthResponse


def test_health_response_valid():
    resp = HealthResponse(status="brain_online")
    assert resp.status == "brain_online"


def test_health_response_schema():
    schema = HealthResponse.model_json_schema()
    assert "status" in schema["properties"]


def test_event_document_created_by_email_default():
    """New EventDocument has created_by_email=None by default."""
    event = EventDocument(
        source="chat",
        service="general",
        event=EventInput(reason="test", evidence="test evidence"),
    )
    assert event.created_by_email is None


def test_event_document_created_by_email_set():
    event = EventDocument(
        source="chat",
        service="general",
        event=EventInput(reason="test", evidence="test evidence"),
        created_by_email="user@example.com",
    )
    assert event.created_by_email == "user@example.com"


def test_event_document_backward_compat_no_created_by_email():
    """Simulate deserializing a Redis blob that was stored before created_by_email existed."""
    legacy_blob = {
        "id": "evt-legacy01",
        "source": "chat",
        "status": "new",
        "service": "general",
        "event": {"reason": "old event", "evidence": "old evidence"},
        "conversation": [],
    }
    event = EventDocument(**legacy_blob)
    assert event.created_by_email is None
    assert event.id == "evt-legacy01"


def test_event_document_roundtrip_with_created_by_email():
    """Verify created_by_email survives JSON serialization roundtrip."""
    event = EventDocument(
        source="chat",
        service="general",
        event=EventInput(reason="test", evidence="test evidence"),
        created_by_email="user@redhat.com",
    )
    blob = json.loads(json.dumps(event.model_dump()))
    restored = EventDocument(**blob)
    assert restored.created_by_email == "user@redhat.com"


@pytest.mark.asyncio
async def test_create_event_persists_created_by_email():
    """BlackboardState.create_event() round-trips created_by_email through Redis."""
    from unittest.mock import AsyncMock
    from src.state.blackboard import BlackboardState

    mock_redis = AsyncMock()
    stored_data = {}

    async def fake_set(key, value):
        stored_data[key] = value

    async def fake_get(key):
        return stored_data.get(key)

    mock_redis.set = AsyncMock(side_effect=fake_set)
    mock_redis.get = AsyncMock(side_effect=fake_get)
    mock_redis.sadd = AsyncMock()
    mock_redis.lpush = AsyncMock()

    bb = BlackboardState(redis=mock_redis)
    event_id = await bb.create_event(
        source="chat",
        service="general",
        reason="test message",
        evidence="test evidence",
        created_by_email="dev@redhat.com",
    )

    retrieved = await bb.get_event(event_id)
    assert retrieved is not None
    assert retrieved.created_by_email == "dev@redhat.com"
    assert retrieved.source == "chat"


@pytest.mark.asyncio
async def test_create_event_without_email_defaults_none():
    """Existing callers that don't pass created_by_email get None."""
    from unittest.mock import AsyncMock
    from src.state.blackboard import BlackboardState

    mock_redis = AsyncMock()
    stored_data = {}

    async def fake_set(key, value):
        stored_data[key] = value

    async def fake_get(key):
        return stored_data.get(key)

    mock_redis.set = AsyncMock(side_effect=fake_set)
    mock_redis.get = AsyncMock(side_effect=fake_get)
    mock_redis.sadd = AsyncMock()
    mock_redis.lpush = AsyncMock()

    bb = BlackboardState(redis=mock_redis)
    event_id = await bb.create_event(
        source="aligner",
        service="my-service",
        reason="CPU spike",
        evidence="test evidence",
    )

    retrieved = await bb.get_event(event_id)
    assert retrieved is not None
    assert retrieved.created_by_email is None
