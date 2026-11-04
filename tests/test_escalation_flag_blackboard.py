# tests/test_escalation_flag_blackboard.py
# @ai-rules:
# 1. [Constraint]: No real Redis. AsyncMock redis; the Lua script is a mock callable, so its
#    compare-and-delete semantics are covered by a faithful Python simulation below.
# 2. [Gotcha]: Keep _simulate_lua() in lock-step with BlackboardState._LUA_CLEAR_ESCALATION.
"""BlackboardState.clear_escalation_flag legacy-field CAS + has_staged_escalation."""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.state.blackboard import BlackboardState


def _bb():
    redis = AsyncMock()
    script = AsyncMock(return_value=1)
    redis.register_script = MagicMock(return_value=script)
    return BlackboardState(redis), redis, script


def _simulate_lua(hash_data: dict, args: list[str]) -> int:
    """Python mirror of _LUA_CLEAR_ESCALATION: ARGV[1]=event id, ARGV[2..]=fields."""
    expected = args[0]
    fields = args[1:] or ["escalation_flag"]
    deleted = 0
    for field in fields:
        val = hash_data.get(field)
        if val:
            prefix = val.split("|", 1)[0]
            if prefix == expected:
                del hash_data[field]
                deleted += 1
    return deleted


class TestClearEscalationFlagLegacyCas:
    async def test_cas_passes_scoped_and_legacy_field_to_lua(self):
        bb, redis, script = _bb()
        res = await bb.clear_escalation_flag("svc", scope="jenkins", expected_event_id="evt-1")
        assert res == 1
        script.assert_awaited_once_with(
            keys=["darwin:service:svc"],
            args=["evt-1", "escalation_flag:jenkins", "escalation_flag"],
        )
        redis.hdel.assert_not_called()  # no unconditional legacy delete under CAS

    async def test_cas_returns_zero_when_nothing_matched(self):
        bb, _, script = _bb()
        script.return_value = 0
        assert await bb.clear_escalation_flag("svc", scope="jenkins", expected_event_id="evt-x") == 0

    async def test_unconditional_clear_deletes_scoped_and_legacy(self):
        bb, redis, script = _bb()
        redis.hdel.return_value = 2
        res = await bb.clear_escalation_flag("svc", scope="jenkins")
        assert res == 2
        redis.hdel.assert_awaited_once_with(
            "darwin:service:svc", "escalation_flag:jenkins", "escalation_flag",
        )
        script.assert_not_called()

    def test_lua_source_compares_every_field_before_deleting(self):
        lua = BlackboardState._LUA_CLEAR_ESCALATION
        assert "for i = 2, nfields do" in lua
        assert lua.count("HDEL") == 1  # only inside the prefix-match branch
        assert "prefix == ARGV[1]" in lua

    def test_lua_semantics_legacy_of_other_event_is_preserved(self):
        h = {"escalation_flag:jenkins": "evt-1|a", "escalation_flag": "evt-2|legacy"}
        assert _simulate_lua(h, ["evt-1", "escalation_flag:jenkins", "escalation_flag"]) == 1
        assert h == {"escalation_flag": "evt-2|legacy"}

    def test_lua_semantics_legacy_of_same_event_is_cleared(self):
        h = {"escalation_flag:jenkins": "evt-1|a", "escalation_flag": "evt-1|legacy"}
        assert _simulate_lua(h, ["evt-1", "escalation_flag:jenkins", "escalation_flag"]) == 2
        assert h == {}

    def test_lua_semantics_flag_read_from_legacy_field_only(self):
        h = {"escalation_flag": "evt-1|legacy"}
        assert _simulate_lua(h, ["evt-1", "escalation_flag:jenkins", "escalation_flag"]) == 1
        assert h == {}

    def test_lua_semantics_no_match_returns_zero(self):
        h = {"escalation_flag:jenkins": "evt-9|a", "escalation_flag": "evt-8|b"}
        assert _simulate_lua(h, ["evt-1", "escalation_flag:jenkins", "escalation_flag"]) == 0
        assert len(h) == 2


class TestHasStagedEscalation:
    async def test_found_in_pending(self):
        bb, redis, _ = _bb()
        redis.zrange.return_value = [json.dumps({"event_id": "evt-1", "service": "s"})]
        redis.smembers.return_value = set()
        assert await bb.has_staged_escalation("evt-1") is True
        redis.zrange.assert_awaited_once_with(BlackboardState.NIGHTWATCHER_PENDING, 0, -1)
        redis.smembers.assert_awaited_once_with(BlackboardState.NIGHTWATCHER_INFLIGHT)

    async def test_found_in_inflight_bytes(self):
        bb, redis, _ = _bb()
        redis.zrange.return_value = []
        redis.smembers.return_value = {json.dumps({"event_id": "evt-2"}).encode()}
        assert await bb.has_staged_escalation("evt-2") is True

    async def test_not_found_and_substring_ids_do_not_match(self):
        bb, redis, _ = _bb()
        redis.zrange.return_value = [json.dumps({"event_id": "evt-10"})]
        redis.smembers.return_value = set()
        assert await bb.has_staged_escalation("evt-1") is False

    async def test_corrupt_members_are_skipped(self):
        bb, redis, _ = _bb()
        redis.zrange.return_value = ["not-json", json.dumps({"event_id": "evt-3"})]
        redis.smembers.return_value = {"{broken"}
        assert await bb.has_staged_escalation("evt-3") is True

    async def test_redis_error_propagates(self):
        bb, redis, _ = _bb()
        redis.zrange.side_effect = ConnectionError("down")
        with pytest.raises(ConnectionError):
            await bb.has_staged_escalation("evt-1")
