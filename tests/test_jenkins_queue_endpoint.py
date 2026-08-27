# tests/test_jenkins_queue_endpoint.py
# @ai-rules:
# 1. [Gotcha]: Patch lifespan like test_queue.py so app import does not require live Redis.
# 2. [Pattern]: ASGITransport + httpx.AsyncClient for in-process GET tests.
# 3. [Constraint]: Mock blackboard.redis.zrange and blackboard.redis.hget — endpoint is a pure Redis read.
# 4. [Contract]: Meta-last: target = meta.get("job_name") or member. Version from meta only.
#    New key format is job_name only (no pipe). Legacy pipe keys may still exist pre-cutover.
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
        ("cnv-tests-e2e|4.18", first_seen_a),
        ("cnv-tests-upgrade|4.19", first_seen_b),
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
            "cnv-tests-e2e|4.18": json.dumps(meta_a),
            "cnv-tests-upgrade|4.19": json.dumps(meta_b),
        }.get(member)

    bb.redis.hget = AsyncMock(side_effect=fake_hget)

    resp = await _get_jenkins_pending(bb)

    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2

    by_key = {item["key"]: item for item in data}
    item_a = by_key["cnv-tests-e2e|4.18"]
    assert item_a["target"] == "cnv-tests-e2e"
    assert item_a["first_seen"] == first_seen_a
    assert item_a["job_name"] == "cnv-tests-e2e"
    assert item_a["version"] == "4.18"
    assert item_a["result"] == "FAILURE"
    assert item_a["build_number"] == 42

    item_b = by_key["cnv-tests-upgrade|4.19"]
    assert item_b["target"] == "cnv-tests-upgrade"
    assert item_b["first_seen"] == first_seen_b


# =========================================================================
# T-Q3: Items with metadata JSON parse correctly
# =========================================================================

@pytest.mark.asyncio
async def test_metadata_json_parsed_correctly():
    """Valid JSON in HASH → metadata fields (job_name, version, result, build_number, url) present."""
    bb = _mock_bb_with_redis()

    bb.redis.zrange.return_value = [
        ("cnv-smoke-test|4.20", 1724690000.0),
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
# T-Q4: Missing metadata — meta-last behavior (rewritten)
# =========================================================================

@pytest.mark.asyncio
async def test_missing_metadata_returns_item_with_key_and_target():
    """T-Q4 (rewritten): Item in ZSET but no metadata in HASH.

    Meta-last contract: target = meta.get("job_name") or member.
    With no metadata, target falls back to the full ZSET member key (unsplit).
    This is a DELIBERATE behavior change from the old key-split contract.
    """
    bb = _mock_bb_with_redis()

    bb.redis.zrange.return_value = [
        ("cnv-tests-e2e|4.21", 1724700000.0),
    ]
    bb.redis.hget = AsyncMock(return_value=None)

    resp = await _get_jenkins_pending(bb)

    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1

    item = data[0]
    assert item["key"] == "cnv-tests-e2e|4.21"
    assert item["target"] == "cnv-tests-e2e|4.21", \
        "Meta-last: no metadata means target = full member key (no split)"
    assert item["first_seen"] == 1724700000.0


@pytest.mark.asyncio
async def test_missing_metadata_new_key_format():
    """T-Q4b: New-format key (no pipe) with no metadata — target = full key."""
    bb = _mock_bb_with_redis()

    bb.redis.zrange.return_value = [
        ("cnv-tests-e2e", 1724700000.0),
    ]
    bb.redis.hget = AsyncMock(return_value=None)

    resp = await _get_jenkins_pending(bb)

    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1

    item = data[0]
    assert item["key"] == "cnv-tests-e2e"
    assert item["target"] == "cnv-tests-e2e"
    assert item["first_seen"] == 1724700000.0


# =========================================================================
# T-Q5: Key split produces target and version
# =========================================================================

@pytest.mark.asyncio
async def test_key_split_produces_correct_target():
    """Key format job-name|4.23 → target = 'job-name' (portion before '|')."""
    bb = _mock_bb_with_redis()

    bb.redis.zrange.return_value = [
        ("cnv-tests-complex-name|4.23", 1724710000.0),
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
    assert item["key"] == "cnv-tests-complex-name|4.23"
    assert item["target"] == "cnv-tests-complex-name"
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


# =========================================================================
# T-Q-meta: Meta-last — version comes from metadata, not key-derived
# =========================================================================

@pytest.mark.asyncio
async def test_version_from_meta_not_key_derived():
    """T-Q-meta: With meta-last, version is from metadata dict, never split from key.

    In the new contract, keys are job_name only (no pipe). Version is exclusively
    a metadata field. This test verifies the version field comes from HASH metadata,
    not from parsing the ZSET member key.
    """
    bb = _mock_bb_with_redis()

    bb.redis.zrange.return_value = [
        ("cnv-tests-e2e", 1724700000.0),
    ]

    meta = {
        "job_name": "cnv-tests-e2e",
        "version": "4.23",
        "view": "Gating Wrappers",
        "result": "FAILURE",
        "build_number": 42,
        "url": "https://jenkins.example.com/job/cnv-tests-e2e/42/",
    }
    bb.redis.hget = AsyncMock(return_value=json.dumps(meta))

    resp = await _get_jenkins_pending(bb)

    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1

    item = data[0]
    assert item["key"] == "cnv-tests-e2e"
    assert item["target"] == "cnv-tests-e2e"
    assert item["version"] == "4.23", \
        "Version must come from meta, not from key splitting"
    assert item.get("view") == "Gating Wrappers", \
        "View field from meta should be present in response"


@pytest.mark.asyncio
async def test_meta_last_splatting_order():
    """T-Q-meta (ordering): Meta dict splatted last — meta fields override
    the explicitly set 'key', 'target', 'first_seen' only if meta has those keys.
    Verify that job_name from meta is the target source."""
    bb = _mock_bb_with_redis()

    bb.redis.zrange.return_value = [
        ("cnv-tests-e2e", 1724700000.0),
    ]

    meta = {
        "job_name": "cnv-tests-e2e",
        "version": "4.23",
        "view": "Gating Wrappers",
        "result": "FAILURE",
    }
    bb.redis.hget = AsyncMock(return_value=json.dumps(meta))

    resp = await _get_jenkins_pending(bb)
    data = resp.json()

    item = data[0]
    assert item["target"] == "cnv-tests-e2e"
    assert item["job_name"] == "cnv-tests-e2e"
    assert item["first_seen"] == 1724700000.0
