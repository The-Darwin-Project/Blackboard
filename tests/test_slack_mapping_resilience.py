# BlackBoard/tests/test_slack_mapping_resilience.py
# @ai-rules:
# 1. [Constraint]: Tests Slack thread mapping resilience, SUNION atomic fallback, and 14-day retention.
# 2. [Pattern]: Uses fakeredis for BlackboardState integration tests with decode_responses=True.
# 3. [Pattern]: Verifies atomic SUNION fallback across EVENT_ACTIVE and EVENT_WAITING_APPROVAL sets.
# 4. [Pattern]: Verifies SET NX self-healing behavior and exclusion of zombie CLOSED events.
# 5. [Pattern]: Verifies resuscitation in park_for_approval with non-empty Slack context guard.
# 6. [Pattern]: Verifies delete_slack_mapping converts deletion to 14-day archival retention.
"""Integration tests for Slack thread mapping resilience and lifecycle harmonization."""
from __future__ import annotations

import json
import time
from typing import Optional

import fakeredis.aioredis
import pytest

from src.models import EventDocument, EventEvidence, EventInput, EventStatus
from src.state.blackboard import BlackboardState
from src.state.ports import EventRepository


# =============================================================================
# Helpers & Fixtures
# =============================================================================


def _make_event_doc(
    event_id: str = "evt-test01",
    status: EventStatus = EventStatus.ACTIVE,
    slack_channel_id: Optional[str] = "C12345",
    slack_thread_ts: Optional[str] = "1700000000.123456",
    queued_at: Optional[float] = None,
) -> EventDocument:
    """Construct a typed EventDocument for testing."""
    return EventDocument(
        id=event_id,
        source="slack",
        service="test-service",
        status=status,
        event=EventInput(
            reason="Slack thread resilience test event",
            evidence=EventEvidence(
                display_text="Test evidence payload",
                source_type="slack",
                domain="complicated",
                severity="info",
            ),
        ),
        slack_channel_id=slack_channel_id,
        slack_thread_ts=slack_thread_ts,
        queued_at=queued_at or time.time(),
        conversation=[],
    )


@pytest.fixture
async def bb():
    """Create a real BlackboardState backed by fakeredis."""
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    return BlackboardState(redis)


async def _seed(bb: BlackboardState, event: EventDocument) -> None:
    """Seed event document in Redis."""
    await bb.redis.set(f"{bb.EVENT_PREFIX}{event.id}", json.dumps(event.model_dump()))


# =============================================================================
# Test Suite: Slack Mapping Resilience & Archival Retention
# =============================================================================


class TestSlackMappingResilience:
    """Test suite for Slack mapping lifecycle, fallback lookup, and self-healing."""

    @pytest.mark.asyncio
    async def test_01_set_slack_mapping_ttl_is_14_days(self, bb: BlackboardState):
        """Test 1: TTL is 1,209,600s (14 days) upon write via set_slack_mapping."""
        channel_id = "C_CHANNEL_01"
        thread_ts = "1700000000.000100"
        event_id = "evt-ttl-check-01"

        # Verify class constant
        assert bb.SLACK_MAPPING_TTL == 1_209_600, "SLACK_MAPPING_TTL must be 14 days (1,209,600s)"

        # Write mapping
        await bb.set_slack_mapping(channel_id, thread_ts, event_id)

        key = f"{bb.SLACK_THREAD_PREFIX}{channel_id}:{thread_ts}"
        stored_id = await bb.redis.get(key)
        assert stored_id == event_id

        ttl = await bb.redis.ttl(key)
        assert 1_209_500 <= ttl <= 1_209_600, f"Expected TTL ~1,209,600s, got {ttl}s"

        # Verify EventRepository protocol includes set_slack_mapping
        assert isinstance(bb, EventRepository)

    @pytest.mark.asyncio
    async def test_02_sunion_fallback_lookup_finds_parked_event(self, bb: BlackboardState):
        """Test 2: Atomic SUNION fallback lookup finds parked event in EVENT_WAITING_APPROVAL when direct key expired."""
        channel_id = "C_PARKED_02"
        thread_ts = "1700000000.000200"
        event_id = "evt-parked-target-02"

        # Create parked event in EVENT_WAITING_APPROVAL
        event = _make_event_doc(
            event_id=event_id,
            status=EventStatus.WAITING_APPROVAL,
            slack_channel_id=channel_id,
            slack_thread_ts=thread_ts,
        )
        await _seed(bb, event)
        await bb.redis.sadd(bb.EVENT_WAITING_APPROVAL, event.id)

        # Simulate direct key expiration (key absent in Redis)
        direct_key = f"{bb.SLACK_THREAD_PREFIX}{channel_id}:{thread_ts}"
        await bb.redis.delete(direct_key)
        assert await bb.redis.get(direct_key) is None

        # Fallback lookup must find the event via SUNION
        resolved_id = await bb.get_event_by_slack_thread(channel_id, thread_ts)
        assert resolved_id == event_id, "SUNION fallback must resolve parked event from EVENT_WAITING_APPROVAL"

        # Also verify fallback finds active events in EVENT_ACTIVE when direct key is expired
        act_channel = "C_ACTIVE_02"
        act_thread = "1700000000.000201"
        act_event = _make_event_doc(
            event_id="evt-active-target-02",
            status=EventStatus.ACTIVE,
            slack_channel_id=act_channel,
            slack_thread_ts=act_thread,
        )
        await _seed(bb, act_event)
        await bb.redis.sadd(bb.EVENT_ACTIVE, act_event.id)

        resolved_active = await bb.get_event_by_slack_thread(act_channel, act_thread)
        assert resolved_active == "evt-active-target-02", "SUNION fallback must resolve active event from EVENT_ACTIVE"

    @pytest.mark.asyncio
    async def test_03_fallback_lookup_self_heals_with_set_nx(self, bb: BlackboardState):
        """Test 3: Fallback lookup self-heals with SET NX and restores 14-day TTL."""
        channel_id = "C_SELFHEAL_03"
        thread_ts = "1700000000.000300"
        event_id = "evt-selfheal-03"

        event = _make_event_doc(
            event_id=event_id,
            status=EventStatus.WAITING_APPROVAL,
            slack_channel_id=channel_id,
            slack_thread_ts=thread_ts,
        )
        await _seed(bb, event)
        await bb.redis.sadd(bb.EVENT_WAITING_APPROVAL, event.id)

        direct_key = f"{bb.SLACK_THREAD_PREFIX}{channel_id}:{thread_ts}"
        assert await bb.redis.exists(direct_key) == 0

        # Initial lookup triggers self-heal via SET NX EX
        found_id = await bb.get_event_by_slack_thread(channel_id, thread_ts)
        assert found_id == event_id

        # Verify key was created with full 14-day TTL
        assert await bb.redis.exists(direct_key) == 1
        assert await bb.redis.get(direct_key) == event_id
        ttl = await bb.redis.ttl(direct_key)
        assert 1_209_500 <= ttl <= 1_209_600

        # Verify second lookup hits the restored direct key
        second_lookup = await bb.get_event_by_slack_thread(channel_id, thread_ts)
        assert second_lookup == event_id

    @pytest.mark.asyncio
    async def test_04_fallback_lookup_ignores_zombie_closed_events(self, bb: BlackboardState):
        """Test 4: Zombie closed events (status == CLOSED) in active sets are ignored by fallback."""
        channel_id = "C_ZOMBIE_04"
        thread_ts = "1700000000.000400"
        zombie_id = "evt-zombie-closed-04"

        # Zombie: marked CLOSED but lingering in EVENT_WAITING_APPROVAL and EVENT_ACTIVE
        zombie_doc = _make_event_doc(
            event_id=zombie_id,
            status=EventStatus.CLOSED,
            slack_channel_id=channel_id,
            slack_thread_ts=thread_ts,
        )
        await _seed(bb, zombie_doc)
        await bb.redis.sadd(bb.EVENT_WAITING_APPROVAL, zombie_id)
        await bb.redis.sadd(bb.EVENT_ACTIVE, zombie_id)

        direct_key = f"{bb.SLACK_THREAD_PREFIX}{channel_id}:{thread_ts}"
        await bb.redis.delete(direct_key)

        # Fallback lookup must ignore zombie closed event
        resolved = await bb.get_event_by_slack_thread(channel_id, thread_ts)
        assert resolved is None, "Fallback lookup must not return a CLOSED event"
        assert await bb.redis.exists(direct_key) == 0, "Zombie closed events must not self-heal into direct key"

        # Disambiguation: if a closed zombie AND a valid waiting event coexist, return valid event
        valid_id = "evt-valid-coexist-04"
        valid_doc = _make_event_doc(
            event_id=valid_id,
            status=EventStatus.WAITING_APPROVAL,
            slack_channel_id=channel_id,
            slack_thread_ts=thread_ts,
            queued_at=time.time() + 10,
        )
        await _seed(bb, valid_doc)
        await bb.redis.sadd(bb.EVENT_WAITING_APPROVAL, valid_id)

        resolved_valid = await bb.get_event_by_slack_thread(channel_id, thread_ts)
        assert resolved_valid == valid_id, "Fallback lookup must pick the non-closed candidate"

    @pytest.mark.asyncio
    async def test_05_park_for_approval_resuscitation_guard(self, bb: BlackboardState):
        """Test 5: Resuscitation in park_for_approval revives expired keys only when slack context is non-empty (no None:None keys)."""
        # Case A: Valid Slack context -> Resuscitates expired key with 14d TTL
        channel_id = "C_RESUSCITATE_05"
        thread_ts = "1700000000.000500"
        event_id = "evt-resuscitate-05"

        event = _make_event_doc(
            event_id=event_id,
            status=EventStatus.ACTIVE,
            slack_channel_id=channel_id,
            slack_thread_ts=thread_ts,
        )
        await _seed(bb, event)
        await bb.redis.sadd(bb.EVENT_ACTIVE, event.id)

        direct_key = f"{bb.SLACK_THREAD_PREFIX}{channel_id}:{thread_ts}"
        await bb.redis.delete(direct_key)
        assert await bb.redis.exists(direct_key) == 0

        await bb.park_for_approval(event.id)

        # Direct key must be resuscitated
        assert await bb.redis.exists(direct_key) == 1
        assert await bb.redis.get(direct_key) == event_id
        ttl = await bb.redis.ttl(direct_key)
        assert 1_209_500 <= ttl <= 1_209_600

        # Case B: Non-Slack event (both fields None) -> No None:None key poisoning
        no_slack_id = "evt-noslack-05"
        no_slack_event = _make_event_doc(
            event_id=no_slack_id,
            status=EventStatus.ACTIVE,
            slack_channel_id=None,
            slack_thread_ts=None,
        )
        await _seed(bb, no_slack_event)
        await bb.redis.sadd(bb.EVENT_ACTIVE, no_slack_id)

        await bb.park_for_approval(no_slack_id)

        assert await bb.redis.exists(f"{bb.SLACK_THREAD_PREFIX}None:None") == 0
        none_keys = await bb.redis.keys(f"{bb.SLACK_THREAD_PREFIX}*None*")
        assert len(none_keys) == 0, f"Found poisoned keys: {none_keys}"

        # Case C: Partial Slack context (channel set, thread_ts None) -> Guarded
        partial_id = "evt-partial-05"
        partial_event = _make_event_doc(
            event_id=partial_id,
            status=EventStatus.ACTIVE,
            slack_channel_id="C_PARTIAL",
            slack_thread_ts=None,
        )
        await _seed(bb, partial_event)
        await bb.redis.sadd(bb.EVENT_ACTIVE, partial_id)

        await bb.park_for_approval(partial_id)
        assert await bb.redis.exists(f"{bb.SLACK_THREAD_PREFIX}C_PARTIAL:None") == 0
        partial_keys = await bb.redis.keys(f"{bb.SLACK_THREAD_PREFIX}*C_PARTIAL*")
        assert len(partial_keys) == 0

    @pytest.mark.asyncio
    async def test_06_closed_events_retain_mapping_with_14d_ttl(self, bb: BlackboardState):
        """Test 6: Closed events retain mapping allowing smart follow-up routing (14d post-close TTL)."""
        channel_id = "C_CLOSED_06"
        thread_ts = "1700000000.000600"
        event_id = "evt-closed-06"

        # Pre-seed mapping
        await bb.set_slack_mapping(channel_id, thread_ts, event_id)
        key = f"{bb.SLACK_THREAD_PREFIX}{channel_id}:{thread_ts}"
        assert await bb.redis.get(key) == event_id

        # Invoking delete_slack_mapping must retain the key with 14-day archival TTL instead of deleting
        await bb.delete_slack_mapping(channel_id, thread_ts)

        # Mapping is retained
        assert await bb.redis.exists(key) == 1
        assert await bb.redis.get(key) == event_id

        # TTL is set to 14 days
        ttl = await bb.redis.ttl(key)
        assert 1_209_500 <= ttl <= 1_209_600, f"Expected 14d archival TTL, got {ttl}s"

        # Smart follow-up direct lookup resolves the closed event
        resolved = await bb.redis.get(key)
        assert resolved == event_id
