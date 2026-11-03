# tests/test_blackboard_title_race.py
# @ai-rules:
# 1. [Constraint]: Tests for atomic conditional title updates (T-4).
# 2. [Pattern]: Uses fakeredis for BlackboardState WATCH/MULTI concurrency tests. Race tests use
#    _InterleavingPipeline (real pipeline + concurrent write before first execute()) so WatchError is genuine;
#    hand-rolled mock pipelines must reset() before raising WatchError, as redis-py does.
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
                await self._real.reset()  # redis-py resets the pipeline in execute()'s finally
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
            await self._real.reset()  # redis-py resets the pipeline in execute()'s finally
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




class _InterleavingPipeline:
    """Proxy over a REAL fakeredis pipeline that runs ``before_execute`` once, right before the
    first ``execute()`` -- i.e. after the code under test has done WATCH + GET + MULTI + SET.

    The concurrent write goes through the real server, so the first ``execute()`` raises a genuine
    ``WatchError`` from fakeredis' key-version tracking (nothing is simulated).
    """

    def __init__(self, real_pipe, state: dict):
        self._real = real_pipe
        self._state = state

    async def __aenter__(self):
        await self._real.__aenter__()
        return self

    async def __aexit__(self, *exc):
        return await self._real.__aexit__(*exc)

    def __getattr__(self, name):  # watch/unwatch/get/multi/set -> real pipeline
        return getattr(self._real, name)

    async def execute(self):
        self._state["executes"] += 1
        if self._state["executes"] == 1:
            self._state["in_hook"] = True
            try:
                await self._state["before_execute"]()
            finally:
                self._state["in_hook"] = False
        try:
            return await self._real.execute()
        except WatchError:
            self._state["watch_errors"] += 1
            raise


def _interleave(bb: BlackboardState, before_execute) -> dict:
    """Patch ``bb.redis.pipeline`` so the first execute() is preceded by ``before_execute``."""
    state = {"executes": 0, "watch_errors": 0, "pipelines": 0, "in_hook": False, "before_execute": before_execute}
    orig = bb.redis.pipeline

    def _wrapper(*args, **kwargs):
        if state["in_hook"]:  # the concurrent writer (e.g. stamp_event) uses an un-intercepted pipeline
            return orig(*args, **kwargs)
        state["pipelines"] += 1
        return _InterleavingPipeline(orig(*args, **kwargs), state)

    patcher = patch.object(bb.redis, "pipeline", side_effect=_wrapper)
    patcher.start()
    state["_patcher"] = patcher
    return state


@pytest.mark.asyncio
async def test_concurrent_user_rename_between_watch_and_execute_wins(bb: BlackboardState):
    """H1: a user rename landing between WATCH and EXEC aborts the LLM write (real WatchError).

    Sequence: LLM path WATCHes+GETs (title_source=fallback) -> user rename commits on the real
    server -> LLM EXEC raises WatchError -> retry re-reads title_source=="user" -> returns False.
    Removing the in-transaction ``title_source == "user"`` re-check makes the retry overwrite the
    user's title and this test fail.
    """
    evt_id = await _seed_event(bb, title="Fallback Title", title_source="fallback")

    async def _user_rename():
        await bb.stamp_event(evt_id, title="User Chosen Title", title_source="user")

    state = _interleave(bb, _user_rename)
    try:
        result = await bb.update_event_title_if_not_user(evt_id, "LLM Generated Title", "llm")
    finally:
        state["_patcher"].stop()

    assert state["watch_errors"] == 1, "first execute() must raise a real WatchError"
    assert state["executes"] == 1, "retry must bail on title_source=='user' before a second EXEC"
    assert result is False
    doc = await bb.get_event(evt_id)
    assert doc is not None
    assert doc.title == "User Chosen Title"
    assert doc.title_source == "user"


@pytest.mark.asyncio
async def test_concurrent_non_user_write_retries_and_lands(bb: BlackboardState):
    """H1 control: a concurrent NON-user write also triggers a real WatchError, but the retry wins."""
    evt_id = await _seed_event(bb, title="Fallback Title", title_source="fallback")

    async def _other_writer():
        raw = json.loads(await bb.redis.get(f"darwin:event:{evt_id}"))
        raw["service"] = "changed-by-someone-else"
        await bb.redis.set(f"darwin:event:{evt_id}", json.dumps(raw))

    state = _interleave(bb, _other_writer)
    try:
        result = await bb.update_event_title_if_not_user(evt_id, "LLM Generated Title", "llm")
    finally:
        state["_patcher"].stop()

    assert state["watch_errors"] == 1
    assert state["executes"] == 2
    assert result is True
    doc = await bb.get_event(evt_id)
    assert doc is not None
    assert (doc.title, doc.title_source) == ("LLM Generated Title", "llm")
    assert doc.service == "changed-by-someone-else", "retry must re-read, not clobber the other write"


@pytest.mark.asyncio
async def test_concurrent_close_between_watch_and_execute_aborts(bb: BlackboardState):
    """A close landing between WATCH and EXEC also aborts the title write on retry."""
    evt_id = await _seed_event(bb, title="Fallback Title", title_source="fallback")

    async def _close():
        raw = json.loads(await bb.redis.get(f"darwin:event:{evt_id}"))
        raw["status"] = "closed"
        await bb.redis.set(f"darwin:event:{evt_id}", json.dumps(raw))

    state = _interleave(bb, _close)
    try:
        result = await bb.update_event_title_if_not_user(evt_id, "LLM Generated Title", "llm")
    finally:
        state["_patcher"].stop()

    assert state["watch_errors"] == 1
    assert result is False
    doc = await bb.get_event(evt_id)
    assert doc is not None and doc.title == "Fallback Title"


@pytest.mark.asyncio
async def test_update_title_reuses_single_pipeline_across_retries(bb: BlackboardState):
    """M8: one pipeline is opened outside the retry loop and reused after a WatchError."""
    evt_id = await _seed_event(bb, title="Initial", title_source="fallback")

    async def _other_writer():
        await bb.redis.set("darwin:event:" + evt_id, await bb.redis.get("darwin:event:" + evt_id))

    state = _interleave(bb, _other_writer)
    try:
        result = await bb.update_event_title_if_not_user(evt_id, "Retried", "llm")
    finally:
        state["_patcher"].stop()

    assert result is True
    assert state["watch_errors"] == 1
    assert state["pipelines"] == 1
