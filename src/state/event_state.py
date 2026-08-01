# BlackBoard/src/state/event_state.py
# @ai-rules:
# 1. [Pattern]: Facade with pluggable backend (Redis HASH vs in-memory dict).
#    BRAIN_REDIS_STATE_ENABLED env var selects backend at init. Zero scattered ifs.
# 2. [Pattern]: CycleSnapshot is a mutable write-through wrapper. Local reads are
#    sync (zero await). Writes mutate local + persist to Redis.
# 3. [Constraint]: Fail-closed on Redis errors — raise, let ResyncTrigger retry in 5s.
# 4. [Gotcha]: All values stored as strings (Redis HASH native type). Callers convert.
# 5. [Pattern]: Redis key: darwin:event:{id}:state. TTL 24h, touched on write/defer/wake/entry.
"""
Per-event cycle state backed by Redis HASH (or in-memory dict for emergency rollback).

The EventState facade provides CRUD over per-event mutable state that must survive
pod restarts and be shared across concurrent workers. CycleSnapshot gives handlers
zero-await synchronous reads with write-through persistence.
"""
from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from redis.asyncio import Redis

logger = logging.getLogger(__name__)

STATE_TTL_SECONDS = 86400  # 24h
_KEY_PREFIX = "darwin:event:"
_KEY_SUFFIX = ":state"


def _state_key(event_id: str) -> str:
    return f"{_KEY_PREFIX}{event_id}{_KEY_SUFFIX}"


class _Backend(Protocol):
    """Minimal storage contract for event state."""

    async def hgetall(self, event_id: str) -> dict[str, str]: ...
    async def hset(self, event_id: str, mapping: dict[str, str]) -> None: ...
    async def hdel(self, event_id: str, *fields: str) -> None: ...
    async def delete(self, event_id: str) -> None: ...
    async def touch_ttl(self, event_id: str) -> None: ...
    async def scan_keys(self) -> list[str]: ...


class _RedisBackend:
    """Redis HASH backend — production path."""

    __slots__ = ("_redis",)

    def __init__(self, redis: "Redis") -> None:
        self._redis = redis

    async def hgetall(self, event_id: str) -> dict[str, str]:
        key = _state_key(event_id)
        data = await self._redis.hgetall(key)
        if data:
            await self._redis.expire(key, STATE_TTL_SECONDS)
        return data or {}

    async def hset(self, event_id: str, mapping: dict[str, str]) -> None:
        key = _state_key(event_id)
        if mapping:
            await self._redis.hset(key, mapping=mapping)
            await self._redis.expire(key, STATE_TTL_SECONDS)

    async def hdel(self, event_id: str, *fields: str) -> None:
        if fields:
            await self._redis.hdel(_state_key(event_id), *fields)

    async def delete(self, event_id: str) -> None:
        await self._redis.delete(_state_key(event_id))

    async def touch_ttl(self, event_id: str) -> None:
        await self._redis.expire(_state_key(event_id), STATE_TTL_SECONDS)

    async def scan_keys(self) -> list[str]:
        """Return event IDs that have state hashes."""
        pattern = f"{_KEY_PREFIX}*{_KEY_SUFFIX}"
        keys: list[str] = []
        async for key in self._redis.scan_iter(match=pattern, count=100):
            eid = key.removeprefix(_KEY_PREFIX).removesuffix(_KEY_SUFFIX)
            if eid:
                keys.append(eid)
        return keys


class _MemoryBackend:
    """In-memory dict backend — emergency rollback only."""

    __slots__ = ("_store",)

    def __init__(self) -> None:
        self._store: dict[str, dict[str, str]] = {}

    async def hgetall(self, event_id: str) -> dict[str, str]:
        return dict(self._store.get(event_id, {}))

    async def hset(self, event_id: str, mapping: dict[str, str]) -> None:
        if event_id not in self._store:
            self._store[event_id] = {}
        self._store[event_id].update(mapping)

    async def hdel(self, event_id: str, *fields: str) -> None:
        store = self._store.get(event_id)
        if store:
            for f in fields:
                store.pop(f, None)

    async def delete(self, event_id: str) -> None:
        self._store.pop(event_id, None)

    async def touch_ttl(self, event_id: str) -> None:
        pass  # No-op for in-memory

    async def scan_keys(self) -> list[str]:
        return list(self._store.keys())


class CycleSnapshot:
    """
    Mutable write-through dict wrapper with typed property accessors.

    Reads are synchronous (zero await) — handlers access properties directly.
    Writes go through EventState.set_fields() which mutates _data locally AND
    persists to Redis.
    """

    __slots__ = ("_data",)

    def __init__(self, data: dict[str, str] | None = None) -> None:
        self._data = data or {}

    # --- Typed property accessors (sync reads) ---

    @property
    def agent_name(self) -> str:
        return self._data.get("agent_name", "")

    @property
    def agent_task_started_at(self) -> float:
        val = self._data.get("agent_task_started_at", "")
        return float(val) if val else 0.0

    @property
    def waiting_agent(self) -> str:
        return self._data.get("waiting_agent", "")

    @property
    def wait_turn(self) -> int:
        val = self._data.get("wait_turn", "")
        return int(val) if val else 0

    @property
    def routing_depth(self) -> int:
        val = self._data.get("routing_depth", "")
        return int(val) if val else 0

    @property
    def reflex_fired(self) -> bool:
        return self._data.get("reflex_fired", "") == "1"

    @property
    def response_emitted(self) -> bool:
        return self._data.get("response_emitted", "") == "1"

    @property
    def session_id(self) -> str:
        return self._data.get("session_id", "")

    @property
    def session_mode(self) -> str:
        return self._data.get("session_mode", "")

    def get(self, key: str, default: str = "") -> str:
        return self._data.get(key, default)

    def __contains__(self, key: str) -> bool:
        return key in self._data

    def __repr__(self) -> str:
        return f"CycleSnapshot({self._data})"


class EventState:
    """
    Facade over per-event cycle state with pluggable backend.

    Usage:
        state = EventState(redis, flag_enabled=True)
        snapshot = await state.get(event_id)          # HGETALL -> CycleSnapshot
        await state.set_fields(eid, snapshot, agent_name="architect")
        await state.clear_fields(eid, snapshot, "agent_name", "wait_turn")
        await state.delete(event_id)                  # Full cleanup
        await state.touch_ttl(event_id)               # Refresh 24h expiry
    """

    __slots__ = ("_backend",)

    def __init__(self, redis: "Redis | None" = None, flag_enabled: bool = True) -> None:
        if flag_enabled and redis is not None:
            self._backend: _Backend = _RedisBackend(redis)
        else:
            if flag_enabled and redis is None:
                logger.warning("BRAIN_REDIS_STATE_ENABLED=true but no Redis client — falling back to memory backend")
            self._backend = _MemoryBackend()

    async def get(self, event_id: str) -> CycleSnapshot:
        """Load full state for an event. Returns empty snapshot if none exists."""
        data = await self._backend.hgetall(event_id)
        return CycleSnapshot(data)

    async def set_fields(self, event_id: str, snapshot: CycleSnapshot, **fields: str) -> None:
        """
        Write fields to both local snapshot and persistent backend.

        All values MUST be strings (Redis HASH constraint). Callers convert.
        Mutates snapshot._data immediately (sync reads see new values).
        """
        str_fields = {k: str(v) for k, v in fields.items()}
        snapshot._data.update(str_fields)
        await self._backend.hset(event_id, str_fields)

    async def clear_fields(self, event_id: str, snapshot: CycleSnapshot, *field_names: str) -> None:
        """Remove specific fields from snapshot and backend."""
        for f in field_names:
            snapshot._data.pop(f, None)
        await self._backend.hdel(event_id, *field_names)

    async def delete(self, event_id: str) -> None:
        """Full state deletion (event closed/resolved)."""
        await self._backend.delete(event_id)

    async def touch_ttl(self, event_id: str) -> None:
        """Refresh TTL without modifying data (defer/wake/entry)."""
        await self._backend.touch_ttl(event_id)

    async def scan_stale_events(self) -> list[str]:
        """Return event IDs with active state hashes (for startup reconciliation)."""
        return await self._backend.scan_keys()


def create_event_state(redis: "Redis | None" = None) -> EventState:
    """Factory that reads the feature flag from environment.

    Falls back to memory backend if the Redis client is not a proper
    async Redis instance (e.g., test mocks).
    """
    flag = os.getenv("BRAIN_REDIS_STATE_ENABLED", "true").lower() == "true"
    if flag and redis is not None:
        try:
            from redis.asyncio import Redis as AsyncRedis
            if isinstance(redis, AsyncRedis):
                return EventState(redis=redis, flag_enabled=True)
        except ImportError:
            pass
        logger.debug("Redis client not async-compatible for EventState, using memory backend")
    return EventState(redis=None, flag_enabled=False)
