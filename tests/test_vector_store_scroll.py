# tests/test_vector_store_scroll.py
# @ai-rules:
# 1. [Pattern]: Written from the knowledge-scroll plan's Test Specification (T-9) BEFORE the
#    implementation landed -- tests target the documented contract, not the executor's code.
# 2. [Pattern]: VectorStore._get_client() is mocked (returns an AsyncMock httpx client) so no
#    real Qdrant instance is required. Mirrors the mock-at-call-boundary style used across
#    tests/test_knowledge_graph_api.py and tests/test_deep_memory_filters.py.
# 3. [Constraint]: These tests assert on the PRE-EXISTING `scroll(collection, limit, offset)`
#    contract (points, next_offset) plus the Step-1 `filter` kwarg addition. If Step 1 changes
#    the tuple shape (e.g. wraps next_offset through an opaque string encoder inside scroll()
#    itself rather than at a higher layer) these tests will need reconciliation -- that
#    divergence is a signal, not a defect in either artifact.
"""
Tests for VectorStore.scroll() cursor round-trip semantics (Test Spec T-9)
plus the optional `filter` passthrough added in knowledge-scroll Step 1.

Covers:
- T-9: uuid-string offset round-trips through a second scroll() call's request body.
- T-9: object-shaped (dict) offset round-trips through a second scroll() call's request body.
- T-9: None offset signals end-of-pagination (has_more=false at the caller level).
- Bonus (Step 1 precondition for T-5/T-5c): `filter` kwarg passed through to the Qdrant
  scroll request body, mirroring VectorStore.search()'s existing `filter` kwarg.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.memory.vector_store import VectorStore


def _make_store_with_responses(responses: list[dict]):
    """Build a VectorStore whose httpx client returns canned JSON bodies in order.

    Returns (store, mock_client) so callers can inspect mock_client.post.call_args_list
    for request-body assertions.
    """
    store = VectorStore.__new__(VectorStore)
    store.base_url = "http://localhost:6333"

    mock_client = AsyncMock()
    remaining = list(responses)

    async def _post(url, json=None):  # noqa: A002 - matches httpx signature
        resp = MagicMock()
        resp.raise_for_status = MagicMock()
        resp.json.return_value = remaining.pop(0)
        return resp

    mock_client.post = AsyncMock(side_effect=_post)
    store._get_client = AsyncMock(return_value=mock_client)
    return store, mock_client


@pytest.mark.asyncio
class TestScrollCursorRoundTrip:
    """T-9: Cursor round-trip -- uuid and object offset shapes."""

    async def test_uuid_string_offset_round_trips_into_next_call_body(self):
        """A UUID-string next_page_offset from page 1 must appear verbatim in page 2's request body."""
        uuid_offset = "11111111-1111-1111-1111-111111111111"
        page1 = {"result": {"points": [{"id": "a", "payload": {}}], "next_page_offset": uuid_offset}}
        page2 = {"result": {"points": [{"id": "b", "payload": {}}], "next_page_offset": None}}
        store, client = _make_store_with_responses([page1, page2])

        points1, offset1 = await store.scroll("darwin_knowledge", limit=50)
        assert points1 == [{"id": "a", "payload": {}}]
        assert offset1 == uuid_offset

        points2, offset2 = await store.scroll("darwin_knowledge", limit=50, offset=offset1)
        assert points2 == [{"id": "b", "payload": {}}]
        assert offset2 is None

        first_body = client.post.call_args_list[0].kwargs["json"]
        assert "offset" not in first_body
        second_body = client.post.call_args_list[1].kwargs["json"]
        assert second_body["offset"] == uuid_offset

    async def test_object_shaped_offset_round_trips_into_next_call_body(self):
        """Qdrant may return a non-string (object) next_page_offset. Per the plan's Step-1
        cursor contract ("Encode next_page_offset as an opaque string... json.dumps otherwise;
        decode before the next scroll(offset=...) call"), the object is opaque-encoded as a
        string cursor -- it must decode back to the ORIGINAL object shape in the next request
        body, not leak as a raw dict through the public API."""
        object_offset = {"start_id": 42, "shard_key": "s1"}
        page1 = {"result": {"points": [{"id": 1, "payload": {}}], "next_page_offset": object_offset}}
        page2 = {"result": {"points": [], "next_page_offset": None}}
        store, client = _make_store_with_responses([page1, page2])

        _points1, offset1 = await store.scroll("darwin_knowledge", limit=50)
        assert isinstance(offset1, str), "Non-str next_page_offset must be opaque-encoded as a string cursor"

        await store.scroll("darwin_knowledge", limit=50, offset=offset1)

        second_body = client.post.call_args_list[1].kwargs["json"]
        assert second_body["offset"] == object_offset, (
            "The opaque string cursor must decode back to the original object offset "
            "in the next scroll() call's request body"
        )

    async def test_none_offset_signals_end_of_pagination(self):
        """A None next_page_offset means the caller's has_more must resolve to False."""
        page1 = {"result": {"points": [], "next_page_offset": None}}
        store, _client = _make_store_with_responses([page1])

        points, offset = await store.scroll("darwin_knowledge", limit=50)
        assert points == []
        assert offset is None

    async def test_first_call_omits_offset_key_entirely(self):
        """First page (no cursor yet) must not send a null/empty offset key -- Qdrant treats
        an explicit `offset: null` differently from an absent key in some client versions."""
        page1 = {"result": {"points": [], "next_page_offset": None}}
        store, client = _make_store_with_responses([page1])

        await store.scroll("darwin_knowledge", limit=50, offset=None)

        body = client.post.call_args_list[0].kwargs["json"]
        assert "offset" not in body


@pytest.mark.asyncio
class TestScrollFilterPassthrough:
    """Step-1 precondition for T-5 (scope filter) / T-5c (service filter):
    VectorStore.scroll must accept and forward a `filter` kwarg, mirroring the
    existing `filter` kwarg on VectorStore.search()."""

    async def test_filter_kwarg_passed_to_request_body(self):
        page1 = {"result": {"points": [], "next_page_offset": None}}
        store, client = _make_store_with_responses([page1])

        test_filter = {"must": [{"key": "scope", "match": {"value": "ownership"}}]}
        await store.scroll("darwin_knowledge", limit=50, filter=test_filter)

        body = client.post.call_args_list[0].kwargs["json"]
        assert body.get("filter") == test_filter

    async def test_no_filter_omits_filter_key(self):
        page1 = {"result": {"points": [], "next_page_offset": None}}
        store, client = _make_store_with_responses([page1])

        await store.scroll("darwin_knowledge", limit=50)

        body = client.post.call_args_list[0].kwargs["json"]
        assert "filter" not in body
