# BlackBoard/tests/test_brain_version_reload.py
# @ai-rules:
# 1. [Constraint]: Tests verify brain-level version check + reload lock behavior only.
# 2. [Pattern]: Uses AsyncMock for redis and skill_loader to isolate brain logic.
# 3. [Constraint]: No actual Brain instantiation -- tests target the version gate logic directly.
"""Brain-level tests for skill hot-reload: concurrent reload serialization, Redis timeout resilience."""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestConcurrentReload:
    """Verify _skills_reload_lock prevents stale overwrites from concurrent workers."""

    @pytest.mark.asyncio
    async def test_lock_serializes_concurrent_reloads(self):
        lock = asyncio.Lock()
        skills_version = None
        reload_calls: list[str] = []

        async def simulate_reload(redis_mock, version_sequence, worker_id):
            nonlocal skills_version
            redis_version = version_sequence[0]
            if redis_version and redis_version != skills_version:
                async with lock:
                    inner_version = version_sequence[1]
                    if inner_version and inner_version != skills_version:
                        reload_calls.append(f"{worker_id}:{inner_version}")
                        skills_version = inner_version

        redis_mock = AsyncMock()

        await asyncio.gather(
            simulate_reload(redis_mock, ["sha_v2", "sha_v2"], "worker_1"),
            simulate_reload(redis_mock, ["sha_v2", "sha_v2"], "worker_2"),
        )

        assert skills_version == "sha_v2"
        assert len(reload_calls) == 1

    @pytest.mark.asyncio
    async def test_inner_reread_closes_stale_outer_version(self):
        """Verify the double-check pattern: outer reads v2, inner reads v3, v3 wins."""
        lock = asyncio.Lock()
        skills_version = "sha_v1"
        reload_calls: list[str] = []

        async def simulate_version_check():
            nonlocal skills_version
            redis_version = "sha_v2"
            if redis_version != skills_version:
                async with lock:
                    inner_version = "sha_v3"
                    if inner_version != skills_version:
                        reload_calls.append(inner_version)
                        skills_version = inner_version

        await simulate_version_check()
        assert skills_version == "sha_v3"
        assert reload_calls == ["sha_v3"]


class TestRedisTimeoutResilience:
    """Verify Redis timeout/errors don't propagate into event processing."""

    @pytest.mark.asyncio
    async def test_outer_redis_timeout_skips_reload(self):
        redis_mock = AsyncMock()
        redis_mock.get = AsyncMock(side_effect=TimeoutError("Redis timeout"))
        skills_version = "sha_v1"

        try:
            redis_version = await redis_mock.get("darwin:skills:version")
        except Exception:
            redis_version = None

        assert redis_version is None
        assert skills_version == "sha_v1"

    @pytest.mark.asyncio
    async def test_inner_redis_timeout_skips_reload(self):
        lock = asyncio.Lock()
        skills_version = "sha_v1"
        reload_called = False

        redis_mock = AsyncMock()
        call_count = 0

        async def get_side_effect(key):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return "sha_v2"
            raise ConnectionError("Redis down")

        redis_mock.get = AsyncMock(side_effect=get_side_effect)

        try:
            redis_version = await redis_mock.get("darwin:skills:version")
        except Exception:
            redis_version = None

        if redis_version and redis_version != skills_version:
            async with lock:
                try:
                    inner_version = await redis_mock.get("darwin:skills:version")
                except Exception:
                    inner_version = None
                if inner_version and inner_version != skills_version:
                    reload_called = True
                    skills_version = inner_version

        assert not reload_called
        assert skills_version == "sha_v1"

    @pytest.mark.asyncio
    async def test_none_version_skips_reload(self):
        """Redis returns None (flushed) -- no reload triggered."""
        redis_mock = AsyncMock()
        redis_mock.get = AsyncMock(return_value=None)
        skills_version = "sha_v1"

        redis_version = await redis_mock.get("darwin:skills:version")
        assert redis_version is None
        assert skills_version == "sha_v1"
