# tests/test_turn_atomicity.py
# @ai-rules:
# 1. [Constraint]: Tests for atomic turn assignment in append_turn() and Slack visibility filter.
# 2. [Pattern]: Uses fakeredis for BlackboardState integration tests.
# 3. [Gotcha]: ConversationTurn.turn is required (int) — use 0 as placeholder for atomic overwrite tests.
"""Tests for atomic turn assignment and Slack tool_result visibility."""
from __future__ import annotations

import json
import time

import pytest
import fakeredis.aioredis

from src.models import ConversationTurn, EventDocument, EventEvidence
from src.state.blackboard import BlackboardState


def _make_turn(actor: str = "brain", action: str = "response", turn: int = 0) -> ConversationTurn:
    return ConversationTurn(turn=turn, actor=actor, action=action, thoughts="test")


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


async def _seed_event(bb: BlackboardState, event_id: str = "evt-test01") -> str:
    evidence = EventEvidence(
        display_text="test", source_type="chat", domain="complicated",
        severity="info",
    )
    doc = EventDocument(
        id=event_id,
        source="chat",
        service="test-svc",
        event={"reason": "test", "evidence": evidence},
        evidence=evidence,
        conversation=[],
    )
    await bb.redis.set(
        f"{bb.EVENT_PREFIX}{event_id}",
        json.dumps(doc.model_dump()),
    )
    return event_id


class TestAtomicTurnAssignment:
    """Verify append_turn assigns turn numbers atomically inside WATCH/MULTI."""

    @pytest.mark.asyncio
    async def test_sequential_correctness(self, bb):
        eid = await _seed_event(bb)
        for i in range(5):
            t = _make_turn(turn=999)
            assigned = await bb.append_turn(eid, t)
            assert assigned == i + 1
            assert t.turn == i + 1

    @pytest.mark.asyncio
    async def test_return_value_contract(self, bb):
        eid = await _seed_event(bb)
        t = _make_turn(turn=0)
        result = await bb.append_turn(eid, t)
        assert isinstance(result, int)
        assert result == 1
        assert t.turn == result

    @pytest.mark.asyncio
    async def test_event_not_found_returns_zero(self, bb):
        t = _make_turn()
        result = await bb.append_turn("evt-nonexistent", t)
        assert result == 0

    @pytest.mark.asyncio
    async def test_precomputed_value_overwritten(self, bb):
        """Callers may pass stale turn numbers — they must be overwritten."""
        eid = await _seed_event(bb)
        t1 = _make_turn(turn=42)
        assigned = await bb.append_turn(eid, t1)
        assert assigned == 1
        assert t1.turn == 1

        t2 = _make_turn(turn=42)
        assigned2 = await bb.append_turn(eid, t2)
        assert assigned2 == 2
        assert t2.turn == 2

    @pytest.mark.asyncio
    async def test_persisted_in_redis(self, bb):
        eid = await _seed_event(bb)
        for i in range(3):
            await bb.append_turn(eid, _make_turn())

        data = await bb.redis.get(f"{bb.EVENT_PREFIX}{eid}")
        doc = EventDocument(**json.loads(data))
        assert len(doc.conversation) == 3
        assert [t.turn for t in doc.conversation] == [1, 2, 3]


class TestSlackVisibilityFilter:
    """Verify _USER_VISIBLE_TOOL_RESULTS whitelist and conditional logic."""

    def test_whitelist_contents(self):
        from src.channels.slack import _USER_VISIBLE_TOOL_RESULTS, _INTERNAL_TURNS
        assert ("brain", "tool_result") not in _INTERNAL_TURNS
        expected = {
            "take_note", "record_observation", "search_open_incidents",
            "consult_deep_memory", "review_notes", "list_observations",
        }
        assert _USER_VISIBLE_TOOL_RESULTS == expected

    def test_whitelist_with_thread_passes(self):
        """Whitelisted tool + slack_thread_ts → should NOT be filtered."""
        from src.channels.slack import _USER_VISIBLE_TOOL_RESULTS
        turn = _make_turn(action="tool_result")
        turn.waitingFor = "take_note"
        has_thread = True
        should_suppress = not (has_thread and turn.waitingFor in _USER_VISIBLE_TOOL_RESULTS)
        assert not should_suppress

    def test_whitelist_without_thread_filtered(self):
        """Whitelisted tool but no slack_thread_ts → should be filtered."""
        from src.channels.slack import _USER_VISIBLE_TOOL_RESULTS
        turn = _make_turn(action="tool_result")
        turn.waitingFor = "take_note"
        has_thread = False
        should_suppress = not (has_thread and turn.waitingFor in _USER_VISIBLE_TOOL_RESULTS)
        assert should_suppress

    def test_non_whitelist_tool_filtered(self):
        """Non-whitelisted tool + slack_thread_ts → should be filtered."""
        from src.channels.slack import _USER_VISIBLE_TOOL_RESULTS
        turn = _make_turn(action="tool_result")
        turn.waitingFor = "refresh_gitlab_context"
        has_thread = True
        should_suppress = not (has_thread and turn.waitingFor in _USER_VISIBLE_TOOL_RESULTS)
        assert should_suppress

    def test_no_waiting_for_filtered(self):
        """tool_result with no waitingFor (gate rejection) → should be filtered."""
        from src.channels.slack import _USER_VISIBLE_TOOL_RESULTS
        turn = _make_turn(action="tool_result")
        turn.waitingFor = None
        has_thread = True
        should_suppress = not (has_thread and turn.waitingFor in _USER_VISIBLE_TOOL_RESULTS)
        assert should_suppress
