# tests/test_blackboard_title_race.py
# @ai-rules:
# 1. [Constraint]: Tests for atomic conditional title updates (T-4).
# 2. [Pattern]: Uses fakeredis for BlackboardState WATCH/MULTI concurrency tests.
# 3. [Security]: Verifies user rename cannot be overwritten by delayed background LLM.
"""Tests for atomic update_event_title_if_not_user and race-guarding."""
from __future__ import annotations

import json
from unittest.mock import patch
import pytest
import fakeredis.aioredis
from redis.exceptions import WatchError

from src.models import EventDocument
from src.state.blackboard import BlackboardState


@pytest.fixture
async def bb():
    redis = fakeredis.aioredis.FakeRedis()
    state = BlackboardState.__new__(BlackboardState)
    state.redis = redis
    state.EVENT_PREFIX = "darwin:event:"
    state.EVENT_QUEUE = "darwin:queue"
    state.EVENT_ACTIVE = "darwin:events:active"
    state.EVENT_WAITING_APPROVAL = "darwin:events:waiting_approval"
    state.EVENT_CLOSED = "darwin:events:closed"
    state.SLACK_THREAD_PREFIX = "darwin:slack:thread:"
    return state


async def _seed_event(
    bb: BlackboardState,
    event_id: str = "evt-test-title",
    title: str = "Initial Fallback",
    title_source: str = "fallback",
    status: str = "active",
) -> str:
    doc = {
        "id": event_id,
        "source": "chat",
        "service": "test-svc",
        "status": status,
        "event": {"reason": "test", "evidence": "test"},
        "title": title,
        "title_source": title_source,
    }
    await bb.redis.set(f"darwin:event:{event_id}", json.dumps(doc))
    return event_id


@pytest.mark.asyncio
async def test_schema_title_default_none():
    """T-UNIT-1: EventDocument defaults title and title_source to None."""
    doc = EventDocument(
        id="evt-default",
        source="chat",
        service="test-svc",
        status="active",
        event={"reason": "test", "evidence": "test"},
    )
    assert doc.title is None
    assert doc.title_source is None


@pytest.mark.asyncio
async def test_update_title_if_not_user_success(bb: BlackboardState):
    """LLM update succeeds when current title_source is 'fallback'."""
    evt_id = await _seed_event(bb, title="Help with redis", title_source="fallback")
    
    res = await bb.update_event_title_if_not_user(evt_id, "Redis Connection Help", "llm")
    assert res is True
    
    doc = await bb.get_event(evt_id)
    assert doc is not None
    assert doc.title == "Redis Connection Help"
    assert doc.title_source == "llm"


@pytest.mark.asyncio
async def test_update_title_preserves_user_title(bb: BlackboardState):
    """LLM update is rejected and returns False when user already renamed event."""
    evt_id = await _seed_event(bb, title="Manual User Fix", title_source="user")
    
    res = await bb.update_event_title_if_not_user(evt_id, "Automated LLM Overwrite", "llm")
    assert res is False
    
    doc = await bb.get_event(evt_id)
    assert doc is not None
    assert doc.title == "Manual User Fix"
    assert doc.title_source == "user"


@pytest.mark.asyncio
async def test_update_title_nonexistent_event(bb: BlackboardState):
    """Returns False for nonexistent event key."""
    res = await bb.update_event_title_if_not_user("evt-nonexistent", "Some Title", "llm")
    assert res is False


@pytest.mark.asyncio
async def test_update_title_rejects_closed_event(bb: BlackboardState):
    """Returns False when event status is closed (case-insensitive)."""
    evt_id = await _seed_event(bb, title="Fallback", title_source="fallback", status="closed")
    res = await bb.update_event_title_if_not_user(evt_id, "New Title", "llm")
    assert res is False

    evt_id_upper = await _seed_event(bb, event_id="evt-upper", title="Fallback", title_source="fallback", status="CLOSED")
    res2 = await bb.update_event_title_if_not_user(evt_id_upper, "New Title", "llm")
    assert res2 is False


@pytest.mark.asyncio
async def test_update_title_watch_conflict_retry(bb: BlackboardState):
    """T-UNIT-5: update_event_title_if_not_user retries upon WatchError and succeeds."""
    evt_id = await _seed_event(bb, title="Initial", title_source="fallback")

    orig_pipeline = bb.redis.pipeline
    attempt = 0

    class MockPipeline:
        def __init__(self, real_pipe):
            self._real = real_pipe

        async def __aenter__(self):
            await self._real.__aenter__()
            return self

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            return await self._real.__aexit__(exc_type, exc_val, exc_tb)

        async def watch(self, *args, **kwargs):
            return await self._real.watch(*args, **kwargs)

        async def unwatch(self):
            return await self._real.unwatch()

        async def get(self, *args, **kwargs):
            return await self._real.get(*args, **kwargs)

        def multi(self):
            return self._real.multi()

        def set(self, *args, **kwargs):
            return self._real.set(*args, **kwargs)

        async def execute(self):
            nonlocal attempt
            attempt += 1
            if attempt == 1:
                raise WatchError("Simulated concurrent mutation")
            return await self._real.execute()

    def pipeline_wrapper(*args, **kwargs):
        real_pipe = orig_pipeline(*args, **kwargs)
        return MockPipeline(real_pipe)

    with patch.object(bb.redis, "pipeline", side_effect=pipeline_wrapper):
        success = await bb.update_event_title_if_not_user(
            evt_id, "Retried Title", "llm", max_retries=3
        )
        assert success is True
        assert attempt == 2

    event = await bb.get_event(evt_id)
    assert event is not None
    assert event.title == "Retried Title"
    assert event.title_source == "llm"


@pytest.mark.asyncio
async def test_update_title_retry_exhaustion(bb: BlackboardState):
    """3 consecutive WatchErrors exhaust max_retries and return False cleanly."""
    evt_id = await _seed_event(bb, title="Initial", title_source="fallback")

    orig_pipeline = bb.redis.pipeline
    attempt = 0

    class FailingPipeline:
        def __init__(self, real_pipe):
            self._real = real_pipe

        async def __aenter__(self):
            await self._real.__aenter__()
            return self

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            return await self._real.__aexit__(exc_type, exc_val, exc_tb)

        async def watch(self, *args, **kwargs):
            return await self._real.watch(*args, **kwargs)

        async def unwatch(self):
            return await self._real.unwatch()

        async def get(self, *args, **kwargs):
            return await self._real.get(*args, **kwargs)

        def multi(self):
            return self._real.multi()

        def set(self, *args, **kwargs):
            return self._real.set(*args, **kwargs)

        async def execute(self):
            nonlocal attempt
            attempt += 1
            raise WatchError("Simulated persistent conflict")

    def pipeline_wrapper(*args, **kwargs):
        real_pipe = orig_pipeline(*args, **kwargs)
        return FailingPipeline(real_pipe)

    with patch.object(bb.redis, "pipeline", side_effect=pipeline_wrapper):
        success = await bb.update_event_title_if_not_user(
            evt_id, "Exhausted Title", "llm", max_retries=3
        )
        assert success is False
        assert attempt == 3


@pytest.mark.asyncio
async def test_update_title_rejects_resolved_event(bb: BlackboardState):
    """Returns False when event status is resolved."""
    evt_id = await _seed_event(bb, title="Fallback", title_source="fallback", status="resolved")
    res = await bb.update_event_title_if_not_user(evt_id, "New Title", "llm")
    assert res is False


