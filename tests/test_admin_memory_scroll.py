# tests/test_admin_memory_scroll.py
# @ai-rules:
# 1. [Pattern]: Written from the knowledge-scroll plan's Test Specification (T-1..T-8, T-11,
#    plus a T-13 regression probe) BEFORE the implementation landed. Tests target the plan's
#    documented REST contract `{items, next_cursor, has_more}`, not the executor's code --
#    divergence between this file and the implementation is a reconciliation signal.
# 2. [Pattern]: `src.routes.queue.get_archivist` is patched at the router import site (same
#    convention as tests/test_knowledge_graph_api.py patching `get_kg_store`). Admin routes call
#    `await get_archivist()` directly in the handler body, not via FastAPI Depends().
# 3. [Assumption]: Archivist gains `scroll_knowledge`/`scroll_lessons`/`scroll_memories` (plan
#    Step 2, "Archivist.scroll_* (or one scroll_collection)"). Each returns ONE page as
#    `{"items": [...], "next_offset": <opaque-or-None>}` per the plan's Step-2 wording verbatim.
#    Route wraps this into `{items, next_cursor, has_more}` (has_more = next_offset is truthy).
# 4. [Assumption]: Indexed-field filters (knowledge `scope`, memories `service`) are translated
#    by the route into a Qdrant filter dict (`{"must": [{"key": ..., "match": {"value": ...}}]}`)
#    passed as `filter=` to the scroll_* call -- mirrors the pre-existing `_build_filter`
#    convention in tests/test_deep_memory_filters.py and VectorStore.search()'s `filter` kwarg.
#    Lesson `channel` is NOT indexed (plan: "Post-fetch filter on page") so it is asserted at
#    the response-shape level instead of via a call-arg assertion.
# 5. [Note]: T-10 (UI hook default page size) and T-12 (GraphView empty-state component) require
#    frontend hook/component test scaffolding that does not exist yet for code not yet written
#    (useKnowledgeScroll hook, GraphView.tsx) -- out of scope for a pure-unit Test Writer pass.
#    See the bottom of this file for what IS covered today for those IDs.
"""
Tests for GET/DELETE /queue/admin/{knowledge,lessons,memories}* cursor-scroll contract.

Covers:
- T-1: First knowledge page -- envelope shape, `has_more`, `next_cursor` presence.
- T-2: Second knowledge page via cursor -- no overlap with page 1; empty cursor ends pagination.
- T-3: `limit=0` rejected with 422.
- T-4: `limit=201` rejected with 422.
- T-5: `scope=` filter reaches the archivist as a Qdrant filter on the indexed `scope` field.
- T-5b: `channel=` filter on lessons is applied post-fetch (no Qdrant index), response items
        filtered accordingly.
- T-5c: `service=` filter on memories reaches the archivist as a Qdrant filter on the indexed
        `service` field.
- T-6: `GET /admin/lessons/{id}` -- 200 for known id, 404 for missing id.
- T-7: `DELETE /admin/lessons/{id}` for an id beyond the old 500-item scan window still succeeds
       (uses get_lesson, not list_lessons(limit=500)).
- T-8: `Archivist.list_knowledge(limit=500)` in-process semantics are UNCHANGED by this plan.
- T-11: `GET /admin/lessons` and `GET /admin/memories` no longer dump the full collection --
        default envelope with `limit` default 50.
- T-13 (partial/regression): `GET /api/cognitive-graph` requests `limit=600` per collection
        (was 500) from cognitive_graph.py -- this is a route-level probe, not the full UI
        "≤600 per type" assertion (that also needs the neuron-fanout logic verified visually).
"""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


# =========================================================================
# Fixtures
# =========================================================================

def _knowledge_page(start: int, count: int, scope: str = "ownership") -> list[dict]:
    return [
        {"id": f"know-{i}", "payload": {"topic": f"topic-{i}", "scope": scope, "fact": f"fact {i}"}}
        for i in range(start, start + count)
    ]


@pytest.fixture
def mock_archivist():
    """AsyncMock Archivist with scroll_knowledge/scroll_lessons/scroll_memories + legacy methods."""
    archivist = AsyncMock()
    archivist.scroll_knowledge = AsyncMock(
        return_value={"items": _knowledge_page(0, 50), "next_offset": "cursor-page-2"}
    )
    archivist.scroll_lessons = AsyncMock(return_value={"items": [], "next_offset": None})
    archivist.scroll_memories = AsyncMock(return_value={"items": [], "next_offset": None})
    archivist.get_lesson = AsyncMock(return_value=None)
    archivist.delete_lesson = AsyncMock(return_value=True)
    archivist.list_lessons = AsyncMock(return_value=[])
    archivist.list_memories = AsyncMock(return_value=[])
    archivist.list_knowledge = AsyncMock(return_value=[])
    return archivist


@pytest.fixture
def client(mock_archivist):
    """FastAPI TestClient with the queue router and patched get_archivist."""
    from src.routes.queue import router

    app = FastAPI()
    app.include_router(router)

    async def _get_archivist():
        return mock_archivist

    with patch("src.routes.queue.get_archivist", _get_archivist):
        yield TestClient(app)


# =========================================================================
# T-1: First knowledge page
# =========================================================================

class TestFirstKnowledgePage:
    def test_returns_envelope_with_items_has_more_next_cursor(self, client, mock_archivist):
        resp = client.get("/queue/admin/knowledge", params={"limit": 50})
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "has_more" in data
        assert isinstance(data["has_more"], bool)
        assert len(data["items"]) <= 50
        # next_offset was truthy ("cursor-page-2") -- has_more must be True and next_cursor present
        assert data["has_more"] is True
        assert data.get("next_cursor")

    def test_no_cursor_means_first_page(self, client, mock_archivist):
        client.get("/queue/admin/knowledge", params={"limit": 50})
        call_kwargs = mock_archivist.scroll_knowledge.call_args.kwargs
        offset_arg = call_kwargs.get("offset") if "offset" in call_kwargs else call_kwargs.get("cursor")
        assert offset_arg is None

    def test_last_page_has_more_false_and_no_next_cursor(self, client, mock_archivist):
        mock_archivist.scroll_knowledge.return_value = {
            "items": _knowledge_page(0, 10),
            "next_offset": None,
        }
        resp = client.get("/queue/admin/knowledge", params={"limit": 50})
        data = resp.json()
        assert data["has_more"] is False
        assert not data.get("next_cursor")


# =========================================================================
# T-2: Second page via cursor
# =========================================================================

class TestSecondKnowledgePage:
    def test_second_page_has_no_overlap_with_first_page(self, client, mock_archivist):
        """Simulates two sequential calls and checks the returned item id sets are disjoint."""
        page1_items = _knowledge_page(0, 50)
        page2_items = _knowledge_page(50, 25)

        def _side_effect(*args, **kwargs):
            offset = kwargs.get("offset") or kwargs.get("cursor")
            if offset in (None, ""):
                return {"items": page1_items, "next_offset": "cursor-page-2"}
            return {"items": page2_items, "next_offset": None}

        mock_archivist.scroll_knowledge.side_effect = _side_effect

        resp1 = client.get("/queue/admin/knowledge", params={"limit": 50})
        data1 = resp1.json()
        cursor = data1["next_cursor"]
        assert cursor

        resp2 = client.get("/queue/admin/knowledge", params={"limit": 50, "cursor": cursor})
        data2 = resp2.json()

        ids1 = {item["id"] for item in data1["items"]}
        ids2 = {item["id"] for item in data2["items"]}
        assert ids1.isdisjoint(ids2)
        assert data2["has_more"] is False

    def test_empty_cursor_response_ends_pagination(self, client, mock_archivist):
        mock_archivist.scroll_knowledge.return_value = {"items": [], "next_offset": None}
        resp = client.get("/queue/admin/knowledge", params={"limit": 50, "cursor": "cursor-page-99"})
        data = resp.json()
        assert data["items"] == []
        assert data["has_more"] is False


# =========================================================================
# T-3 / T-4: limit validation
# =========================================================================

class TestKnowledgeLimitValidation:
    def test_limit_zero_rejected(self, client):
        resp = client.get("/queue/admin/knowledge", params={"limit": 0})
        assert resp.status_code == 422

    def test_limit_201_rejected(self, client):
        resp = client.get("/queue/admin/knowledge", params={"limit": 201})
        assert resp.status_code == 422

    def test_limit_200_accepted(self, client, mock_archivist):
        resp = client.get("/queue/admin/knowledge", params={"limit": 200})
        assert resp.status_code == 200

    def test_limit_1_accepted(self, client, mock_archivist):
        resp = client.get("/queue/admin/knowledge", params={"limit": 1})
        assert resp.status_code == 200


# =========================================================================
# T-5 / T-5c: indexed-field filters (Qdrant filter passthrough)
# =========================================================================

class TestIndexedFieldFilters:
    def test_knowledge_scope_filter_builds_qdrant_filter(self, client, mock_archivist):
        resp = client.get("/queue/admin/knowledge", params={"limit": 50, "scope": "ownership"})
        assert resp.status_code == 200
        call_kwargs = mock_archivist.scroll_knowledge.call_args.kwargs
        passed_filter = call_kwargs.get("filter")
        assert passed_filter is not None, (
            "Expected a Qdrant filter dict for the indexed `scope` field; "
            f"got call kwargs: {call_kwargs}"
        )
        conditions = passed_filter.get("must", [])
        assert any(
            c.get("key") == "scope" and c.get("match", {}).get("value") == "ownership"
            for c in conditions
        ), f"scope=ownership condition not found in filter: {passed_filter}"

    def test_memories_service_filter_builds_qdrant_filter(self, client, mock_archivist):
        resp = client.get("/queue/admin/memories", params={"limit": 50, "service": "darwin-brain"})
        assert resp.status_code == 200
        call_kwargs = mock_archivist.scroll_memories.call_args.kwargs
        passed_filter = call_kwargs.get("filter")
        assert passed_filter is not None, (
            "Expected a Qdrant filter dict for the indexed `service` field; "
            f"got call kwargs: {call_kwargs}"
        )
        conditions = passed_filter.get("must", [])
        assert any(
            c.get("key") == "service" and c.get("match", {}).get("value") == "darwin-brain"
            for c in conditions
        ), f"service=darwin-brain condition not found in filter: {passed_filter}"

    def test_knowledge_no_scope_omits_filter(self, client, mock_archivist):
        client.get("/queue/admin/knowledge", params={"limit": 50})
        call_kwargs = mock_archivist.scroll_knowledge.call_args.kwargs
        assert not call_kwargs.get("filter")


# =========================================================================
# T-5b: lesson channel filter (post-fetch, not Qdrant-indexed)
# =========================================================================

class TestChannelFilterPostFetch:
    def test_channel_filter_applied_after_fetch(self, client, mock_archivist):
        """Lessons have no `channel` payload index -- filtering must happen on the returned
        page's items, not via a Qdrant filter dict. Sparse/empty results on a page are an
        accepted limitation per the plan."""
        mock_archivist.scroll_lessons.return_value = {
            "items": [
                {"id": "l-1", "payload": {"title": "a", "channel": "external"}},
                {"id": "l-2", "payload": {"title": "b", "channel": "experience"}},
                {"id": "l-3", "payload": {"title": "c", "channel": "external"}},
            ],
            "next_offset": None,
        }
        resp = client.get("/queue/admin/lessons", params={"limit": 50, "channel": "experience"})
        assert resp.status_code == 200
        data = resp.json()
        assert all(item["payload"]["channel"] == "experience" for item in data["items"])
        assert len(data["items"]) == 1
        assert data["items"][0]["id"] == "l-2"

    def test_no_channel_filter_returns_all_channels(self, client, mock_archivist):
        mock_archivist.scroll_lessons.return_value = {
            "items": [
                {"id": "l-1", "payload": {"title": "a", "channel": "external"}},
                {"id": "l-2", "payload": {"title": "b", "channel": "experience"}},
            ],
            "next_offset": None,
        }
        resp = client.get("/queue/admin/lessons", params={"limit": 50})
        data = resp.json()
        assert len(data["items"]) == 2


# =========================================================================
# T-6: GET lesson by id
# =========================================================================

class TestGetLessonById:
    def test_known_lesson_returns_200_with_payload(self, client, mock_archivist):
        mock_archivist.get_lesson.return_value = {
            "id": "lesson-abc",
            "payload": {"title": "Known lesson", "channel": "external"},
        }
        resp = client.get("/queue/admin/lessons/lesson-abc")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "lesson-abc"
        mock_archivist.get_lesson.assert_called_once_with("lesson-abc")

    def test_missing_lesson_returns_404(self, client, mock_archivist):
        mock_archivist.get_lesson.return_value = None
        resp = client.get("/queue/admin/lessons/does-not-exist")
        assert resp.status_code == 404


# =========================================================================
# T-7: Delete beyond old 500-scan window
# =========================================================================

class TestDeleteLessonBeyond500:
    def test_delete_uses_get_lesson_not_full_list_scan(self, client, mock_archivist):
        """A lesson that would NOT be in the first 500 of list_lessons() must still delete
        successfully -- the route must use get_lesson(id), not list_lessons(limit=500)."""
        mock_archivist.get_lesson.return_value = {
            "id": "lesson-501st",
            "payload": {"title": "Beyond the old 500 scan window"},
        }
        # Deliberately leave list_lessons empty/short to prove it is NOT consulted for this id.
        mock_archivist.list_lessons.return_value = _knowledge_page(0, 5)

        resp = client.delete("/queue/admin/lessons/lesson-501st")
        assert resp.status_code == 200
        assert resp.json().get("status") == "deleted"
        mock_archivist.delete_lesson.assert_called_once_with("lesson-501st")
        mock_archivist.list_lessons.assert_not_called()

    def test_delete_missing_lesson_still_404s(self, client, mock_archivist):
        mock_archivist.get_lesson.return_value = None
        resp = client.delete("/queue/admin/lessons/nonexistent")
        assert resp.status_code == 404
        mock_archivist.delete_lesson.assert_not_called()


# =========================================================================
# T-8: Archivist.list_knowledge(limit=500) in-process semantics UNCHANGED
# =========================================================================

@pytest.mark.asyncio
class TestListKnowledgeUnchanged:
    """Direct Archivist-level test (not via REST) -- Step 2 must not alter list_*() truncation
    semantics used by the cognitive_graph in-process sample path."""

    async def test_list_knowledge_truncates_at_limit_across_multiple_pages(self):
        from src.agents.archivist import Archivist

        archivist = Archivist.__new__(Archivist)
        archivist._knowledge_ready = True

        mock_vs = AsyncMock()
        # 3 pages of 256 = 768 raw points; limit=500 must truncate to exactly 500.
        page_a = (_knowledge_page(0, 256), "offset-1")
        page_b = (_knowledge_page(256, 256), "offset-2")
        page_c = (_knowledge_page(512, 256), None)
        mock_vs.scroll = AsyncMock(side_effect=[page_a, page_b, page_c])
        archivist._vector_store = mock_vs

        result = await archivist.list_knowledge(limit=500)

        assert len(result) == 500
        assert result[0]["id"] == "know-0"
        assert result[-1]["id"] == "know-499"

    async def test_list_knowledge_default_still_fetches_all(self):
        from src.agents.archivist import Archivist

        archivist = Archivist.__new__(Archivist)
        archivist._knowledge_ready = True

        mock_vs = AsyncMock()
        mock_vs.scroll = AsyncMock(
            side_effect=[
                (_knowledge_page(0, 10), None),
            ]
        )
        archivist._vector_store = mock_vs

        result = await archivist.list_knowledge()  # limit=0 default -- fetch all
        assert len(result) == 10


# =========================================================================
# T-11: Lessons/memories REST no longer dump all
# =========================================================================

class TestLessonsMemoriesEnvelope:
    def test_lessons_default_returns_envelope_not_bare_array(self, client, mock_archivist):
        resp = client.get("/queue/admin/lessons")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, dict), "Response must be an envelope object, not a bare array"
        assert "items" in data and "has_more" in data

    def test_memories_default_returns_envelope_not_bare_array(self, client, mock_archivist):
        resp = client.get("/queue/admin/memories")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, dict), "Response must be an envelope object, not a bare array"
        assert "items" in data and "has_more" in data

    def test_lessons_default_limit_is_50(self, client, mock_archivist):
        client.get("/queue/admin/lessons")
        call_kwargs = mock_archivist.scroll_lessons.call_args.kwargs
        assert call_kwargs.get("limit") == 50

    def test_memories_default_limit_is_50(self, client, mock_archivist):
        client.get("/queue/admin/memories")
        call_kwargs = mock_archivist.scroll_memories.call_args.kwargs
        assert call_kwargs.get("limit") == 50


# =========================================================================
# T-13 (partial): Cortex cold-start budget raised to 600
# =========================================================================

@pytest.mark.asyncio
class TestCognitiveGraphBudget:
    """Route-level probe for the Step 6a budget bump. Does NOT cover the frontend
    ring-rendering guarantee (needs a live Cortex/Sigma harness) -- see file header note."""

    async def test_cognitive_graph_requests_limit_600_per_collection(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from src.routes.cognitive_graph import router

        mock_archivist = AsyncMock()
        mock_archivist.list_lessons = AsyncMock(return_value=[])
        mock_archivist.list_memories = AsyncMock(return_value=[])
        mock_archivist.list_knowledge = AsyncMock(return_value=[])

        app = FastAPI()
        app.include_router(router)

        async def _get_archivist():
            return mock_archivist

        async def _get_pulse_tracker():
            return None

        async def _get_brain():
            return None

        with patch("src.routes.cognitive_graph.get_archivist", _get_archivist), \
             patch("src.routes.cognitive_graph.get_pulse_tracker", _get_pulse_tracker), \
             patch("src.routes.cognitive_graph.get_brain", _get_brain):
            test_client = TestClient(app)
            resp = test_client.get("/api/cognitive-graph")

        assert resp.status_code == 200
        for mocked in (mock_archivist.list_lessons, mock_archivist.list_memories, mock_archivist.list_knowledge):
            mocked.assert_called_once()
            call_kwargs = mocked.call_args.kwargs
            limit_arg = call_kwargs.get("limit") if "limit" in call_kwargs else (
                mocked.call_args.args[0] if mocked.call_args.args else None
            )
            assert limit_arg == 600, f"Expected limit=600 (budget-raised cold start), got {limit_arg}"


# =========================================================================
# Flagged: T-10, T-12 -- require frontend hook/component scaffolding
# =========================================================================
#
# T-10 (UI default is not 100-cap -- getKnowledge()/useKnowledgeScroll hook):
#   The hook (`useKnowledgeScroll`) and the updated `client.ts`/`types.ts` scroll-envelope
#   types are Step 4 deliverables that do not exist in the codebase yet. A pure-unit test
#   cannot import them without guessing the hook's exported name/shape ahead of the executor's
#   implementation. Once `useKnowledgeScroll` (or equivalent) lands, add a Vitest test using
#   `@tanstack/react-query`'s QueryClientProvider + renderHook (see the project's existing
#   hook-test conventions, if any) asserting: (a) first call uses PAGE_SIZE=50 with no cursor,
#   (b) `fetchNextPage()` passes the prior page's `next_cursor`, mirroring
#   ui/src/__tests__ coverage style for useReportSearch's sibling hooks.
#
# T-12 (KG tab empty when store None -- GraphView.tsx):
#   `GraphView.tsx` is a new Step 5 component that does not exist yet. Its BACKEND contract
#   ("[] when store unavailable") is already covered by the pre-existing
#   tests/test_knowledge_graph_api.py::TestServicesEndpoint::test_returns_empty_when_store_unavailable.
#   Once GraphView.tsx exists, add a React Testing Library render test asserting it shows an
#   empty state (not a crash) when `getKGServices()` resolves to `[]`.
