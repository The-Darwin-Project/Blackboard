# tests/test_jenkins_queue_endpoint.py
# @ai-rules:
# 1. [Gotcha]: Patch lifespan like test_queue.py so app import does not require live Redis.
# 2. [Pattern]: ASGITransport + httpx.AsyncClient for in-process GET tests.
# 3. [Constraint]: Mock blackboard.redis.zrange and blackboard.redis.hget — endpoint is a pure Redis read.
# 4. [Pattern]: Key format is {category}:{job_name}|{version}. Target is everything before '|'.
# 5. [Pattern]: ZSET key = darwin:jenkins:pending, HASH key = darwin:jenkins:pending:meta.
"""Route-level tests for GET /queue/jenkins/pending endpoint."""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient


async def _get_jenkins_pending(mock_bb) -> "httpx.Response":
    """GET /queue/jenkins/pending with the given mock blackboard."""
    with patch("src.main.lifespan") as mock_lifespan:
        mock_lifespan.return_value.__aenter__ = AsyncMock()
        mock_lifespan.return_value.__aexit__ = AsyncMock()
        from src import dependencies
        from src.main import app

        original_bb = dependencies._blackboard
        dependencies._blackboard = mock_bb
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                return await client.get("/queue/jenkins/pending")
        finally:
            dependencies._blackboard = original_bb


def _mock_bb_with_redis():
    """Build a mock BlackboardState with a .redis sub-mock."""
    bb = AsyncMock()
    bb.redis = AsyncMock()
    bb.redis.zrange = AsyncMock(return_value=[])
    bb.redis.hget = AsyncMock(return_value=None)
    return bb


# =========================================================================
# T-Q1: Empty queue returns empty list
# =========================================================================

@pytest.mark.asyncio
async def test_empty_queue_returns_empty_list():
    """GET /queue/jenkins/pending with no items in ZSET returns []."""
    bb = _mock_bb_with_redis()
    bb.redis.zrange.return_value = []

    resp = await _get_jenkins_pending(bb)

    assert resp.status_code == 200
    assert resp.json() == []


# =========================================================================
# T-Q2: Populated queue returns items with metadata
# =========================================================================

@pytest.mark.asyncio
async def test_populated_queue_returns_items_with_metadata():
    """Two items in ZSET + metadata in HASH → response contains both with expected fields."""
    bb = _mock_bb_with_redis()

    first_seen_a = 1724680000.0
    first_seen_b = 1724680060.0

    bb.redis.zrange.return_value = [
        ("gating:cnv-tests-e2e|4.18", first_seen_a),
        ("gating:cnv-tests-upgrade|4.19", first_seen_b),
    ]

    meta_a = {
        "job_name": "cnv-tests-e2e",
        "version": "4.18",
        "result": "FAILURE",
        "build_number": 42,
        "url": "https://jenkins.example.com/job/cnv-tests-e2e/42/",
    }
    meta_b = {
        "job_name": "cnv-tests-upgrade",
        "version": "4.19",
        "result": "NOT_BUILT",
        "build_number": 7,
        "url": "https://jenkins.example.com/job/cnv-tests-upgrade/7/",
    }

    async def fake_hget(hash_key, member):
        return {
            "gating:cnv-tests-e2e|4.18": json.dumps(meta_a),
            "gating:cnv-tests-upgrade|4.19": json.dumps(meta_b),
        }.get(member)

    bb.redis.hget = AsyncMock(side_effect=fake_hget)

    resp = await _get_jenkins_pending(bb)

    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2

    by_key = {item["key"]: item for item in data}
    item_a = by_key["gating:cnv-tests-e2e|4.18"]
    assert item_a["target"] == "cnv-tests-e2e"
    assert item_a["category"] == "gating"
    assert item_a["first_seen"] == first_seen_a
    assert item_a["job_name"] == "cnv-tests-e2e"
    assert item_a["version"] == "4.18"
    assert item_a["result"] == "FAILURE"
    assert item_a["build_number"] == 42

    item_b = by_key["gating:cnv-tests-upgrade|4.19"]
    assert item_b["target"] == "cnv-tests-upgrade"
    assert item_b["category"] == "gating"
    assert item_b["first_seen"] == first_seen_b


# =========================================================================
# T-Q3: Items with metadata JSON parse correctly
# =========================================================================

@pytest.mark.asyncio
async def test_metadata_json_parsed_correctly():
    """Valid JSON in HASH → metadata fields (job_name, version, result, build_number, url) present."""
    bb = _mock_bb_with_redis()

    bb.redis.zrange.return_value = [
        ("smoke:cnv-smoke-test|4.20", 1724690000.0),
    ]

    meta = {
        "job_name": "cnv-smoke-test",
        "version": "4.20",
        "result": "UNSTABLE",
        "build_number": 101,
        "url": "https://jenkins.example.com/job/cnv-smoke-test/101/",
    }

    bb.redis.hget = AsyncMock(return_value=json.dumps(meta))

    resp = await _get_jenkins_pending(bb)

    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1

    item = data[0]
    assert item["job_name"] == "cnv-smoke-test"
    assert item["version"] == "4.20"
    assert item["result"] == "UNSTABLE"
    assert item["build_number"] == 101
    assert item["url"] == "https://jenkins.example.com/job/cnv-smoke-test/101/"


# =========================================================================
# T-Q4: Missing metadata returns item with defaults
# =========================================================================

@pytest.mark.asyncio
async def test_missing_metadata_returns_item_with_key_and_target():
    """Item in ZSET but no entry in HASH → item returned with key, target, first_seen but empty metadata."""
    bb = _mock_bb_with_redis()

    bb.redis.zrange.return_value = [
        ("gating:cnv-tests-e2e|4.21", 1724700000.0),
    ]
    bb.redis.hget = AsyncMock(return_value=None)

    resp = await _get_jenkins_pending(bb)

    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1

    item = data[0]
    assert item["key"] == "gating:cnv-tests-e2e|4.21"
    assert item["target"] == "cnv-tests-e2e"
    assert item["category"] == "gating"
    assert item["first_seen"] == 1724700000.0
    assert item.get("job_name") is None or item.get("job_name") == ""


# =========================================================================
# T-Q5: Key split produces target and version
# =========================================================================

@pytest.mark.asyncio
async def test_key_split_produces_correct_target():
    """Key format gating:job-name|4.23 → target = 'gating:job-name' (portion before '|')."""
    bb = _mock_bb_with_redis()

    bb.redis.zrange.return_value = [
        ("gating:cnv-tests-complex-name|4.23", 1724710000.0),
    ]
    bb.redis.hget = AsyncMock(return_value=json.dumps({
        "job_name": "cnv-tests-complex-name",
        "version": "4.23",
        "result": "FAILURE",
        "build_number": 55,
        "url": "https://jenkins.example.com/job/cnv-tests-complex-name/55/",
    }))

    resp = await _get_jenkins_pending(bb)

    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1

    item = data[0]
    assert item["key"] == "gating:cnv-tests-complex-name|4.23"
    assert item["target"] == "cnv-tests-complex-name"
    assert item["category"] == "gating"
    assert item["version"] == "4.23"


@pytest.mark.asyncio
async def test_key_without_pipe_uses_full_key_as_target():
    """Key without '|' → target is the full key (fallback behavior mirroring aligner)."""
    bb = _mock_bb_with_redis()

    bb.redis.zrange.return_value = [
        ("orphan-key-no-pipe", 1724720000.0),
    ]
    bb.redis.hget = AsyncMock(return_value=None)

    resp = await _get_jenkins_pending(bb)

    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1

    item = data[0]
    assert item["key"] == "orphan-key-no-pipe"
    assert item["target"] == "orphan-key-no-pipe"
