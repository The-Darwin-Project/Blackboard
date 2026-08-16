# tests/test_knowledge_graph_api.py
# @ai-rules:
# 1. [Pattern]: Tests for KG REST endpoints + list_services/get_service_detail store methods.
# 2. [Pattern]: unittest.mock.patch on get_kg_store at the router import site (not Depends-based DI).
# 3. [Pattern]: Unit tests for store methods use AsyncMock pool/connection (same as test_knowledge_graph.py).
# 4. [Constraint]: No real Postgres. Store is mocked at function call boundary for endpoint tests.
# 5. [Constraint]: All KG methods are fail-open — test graceful empty responses.
"""
Tests for Knowledge Graph REST API endpoints and supporting store methods.

Covers:
- GET /api/knowledge-graph/services
- GET /api/knowledge-graph/services/{entity_id}
- GET /api/knowledge-graph/stats
- KnowledgeGraphStore.list_services()
- KnowledgeGraphStore.get_service_detail()
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


# =========================================================================
# Fixture Data — 3 services, 5 relationships
# =========================================================================

FIXTURE_SERVICES = [
    {
        "entity_id": "service:darwin-brain",
        "properties": {"version": "3.2", "namespace": "darwin"},
        "last_seen": "2026-08-15T10:00:00+00:00",
        "relationship_count": 3,
    },
    {
        "entity_id": "service:darwin-aligner",
        "properties": {"version": "1.1", "namespace": "darwin"},
        "last_seen": "2026-08-14T08:30:00+00:00",
        "relationship_count": 1,
    },
    {
        "entity_id": "service:release-console",
        "properties": {"namespace": "cnv-fbc-konflux"},
        "last_seen": "2026-08-13T15:00:00+00:00",
        "relationship_count": 1,
    },
]

FIXTURE_RELATIONSHIPS = [
    {
        "rel_type": "AFFECTED",
        "entity_type": "Event",
        "entity_id": "event:evt-abc12345",
        "direction": "incoming",
        "properties": {},
    },
    {
        "rel_type": "APPLIED_TO",
        "entity_type": "Fix",
        "entity_id": "fix:helm-bump-v3.2",
        "direction": "incoming",
        "properties": {},
    },
    {
        "rel_type": "RESOLVED_BY",
        "entity_type": "Fix",
        "entity_id": "fix:helm-bump-v3.2",
        "direction": "outgoing",
        "properties": {},
    },
]

FIXTURE_SERVICE_DETAIL = {
    "entity_id": "service:darwin-brain",
    "properties": {"version": "3.2", "namespace": "darwin"},
    "last_seen": "2026-08-15T10:00:00+00:00",
    "relationships": FIXTURE_RELATIONSHIPS,
}

FIXTURE_STATS = {
    "entities": {"Service": 3, "Event": 5, "Fix": 2},
    "relationships": {"AFFECTED": 3, "APPLIED_TO": 1, "RESOLVED_BY": 1},
    "last_updated": "2026-08-15T10:00:00+00:00",
}


# =========================================================================
# Fixtures
# =========================================================================

@pytest.fixture
def mock_kg_store():
    """Mock KnowledgeGraphStore with fixture data."""
    store = AsyncMock()
    store.list_services = AsyncMock(return_value=FIXTURE_SERVICES)
    store.get_service_detail = AsyncMock(return_value=FIXTURE_SERVICE_DETAIL)
    store.health_check = AsyncMock(return_value=True)
    store._ensure_initialized = AsyncMock(return_value=True)
    mock_conn = AsyncMock()
    mock_conn.fetch = AsyncMock(return_value=[])
    mock_conn.fetchrow = AsyncMock(return_value=None)
    mock_cm = AsyncMock()
    mock_cm.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_cm.__aexit__ = AsyncMock(return_value=False)
    store._pool = MagicMock()
    store._pool.acquire = MagicMock(return_value=mock_cm)
    return store


@pytest.fixture
def client(mock_kg_store):
    """FastAPI TestClient with the KG router and patched get_kg_store."""
    from src.routes.knowledge_graph_api import router

    app = FastAPI()
    app.include_router(router)
    with patch("src.routes.knowledge_graph_api.get_kg_store", new_callable=lambda: lambda: AsyncMock(return_value=mock_kg_store)):
        yield TestClient(app)


@pytest.fixture
def patched_client(mock_kg_store):
    """TestClient that patches get_kg_store for the lifetime of the test."""
    from src.routes.knowledge_graph_api import router

    app = FastAPI()
    app.include_router(router)

    async def _mock_get_kg_store():
        return mock_kg_store

    with patch("src.routes.knowledge_graph_api.get_kg_store", _mock_get_kg_store):
        yield TestClient(app)


# =========================================================================
# Store Unit Tests: list_services
# =========================================================================

@pytest.mark.asyncio
class TestListServicesStore:
    """Unit tests for KnowledgeGraphStore.list_services()."""

    async def test_returns_services_with_correct_shape(self):
        """list_services returns dicts with entity_id, properties, last_seen, relationship_count."""
        from src.memory.knowledge_graph import KnowledgeGraphStore

        store = KnowledgeGraphStore.__new__(KnowledgeGraphStore)
        store._url = "postgresql://test:5432/kg"
        store._pool = MagicMock()
        store._initialized = True

        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(return_value=[
            {
                "entity_id": "service:darwin-brain",
                "properties": {"version": "3.2"},
                "last_seen": "2026-08-15T10:00:00+00:00",
                "relationship_count": 3,
            },
            {
                "entity_id": "service:darwin-aligner",
                "properties": {"version": "1.1"},
                "last_seen": "2026-08-14T08:30:00+00:00",
                "relationship_count": 1,
            },
        ])
        mock_cm = AsyncMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_cm.__aexit__ = AsyncMock(return_value=False)
        store._pool.acquire.return_value = mock_cm

        result = await store.list_services()

        assert isinstance(result, list)
        assert len(result) == 2
        for svc in result:
            assert "entity_id" in svc
            assert "properties" in svc
            assert "last_seen" in svc
            assert "relationship_count" in svc
        assert result[0]["entity_id"] == "service:darwin-brain"
        assert result[0]["relationship_count"] == 3

    async def test_returns_empty_on_connection_failure(self):
        """list_services returns [] when pool.acquire raises (fail-open)."""
        from src.memory.knowledge_graph import KnowledgeGraphStore

        store = KnowledgeGraphStore.__new__(KnowledgeGraphStore)
        store._url = "postgresql://test:5432/kg"
        store._pool = AsyncMock()
        store._initialized = True

        store._pool.acquire.side_effect = ConnectionError("connection refused")

        result = await store.list_services()
        assert result == []

    async def test_returns_empty_when_not_initialized(self):
        """list_services returns [] when store has no URL (Postgres unconfigured)."""
        from src.memory.knowledge_graph import KnowledgeGraphStore

        store = KnowledgeGraphStore(url="")

        result = await store.list_services()
        assert result == []


# =========================================================================
# Store Unit Tests: get_service_detail
# =========================================================================

@pytest.mark.asyncio
class TestGetServiceDetailStore:
    """Unit tests for KnowledgeGraphStore.get_service_detail()."""

    async def test_returns_entity_with_relationships(self):
        """get_service_detail returns entity dict + relationships for known entity."""
        from src.memory.knowledge_graph import KnowledgeGraphStore

        store = KnowledgeGraphStore.__new__(KnowledgeGraphStore)
        store._url = "postgresql://test:5432/kg"
        store._pool = MagicMock()
        store._initialized = True

        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(return_value={
            "entity_id": "service:darwin-brain",
            "properties": {"version": "3.2"},
            "last_seen": "2026-08-15T10:00:00+00:00",
        })
        mock_conn.fetch = AsyncMock(return_value=[
            {
                "entity_type": "Event",
                "entity_id": "event:evt-abc12345",
                "properties": {},
                "rel_type": "AFFECTED",
            },
        ])
        mock_cm = AsyncMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_cm.__aexit__ = AsyncMock(return_value=False)
        store._pool.acquire.return_value = mock_cm

        result = await store.get_service_detail("service:darwin-brain")

        assert result is not None
        assert result["entity_id"] == "service:darwin-brain"
        assert "properties" in result
        assert "last_seen" in result
        assert "relationships" in result
        assert isinstance(result["relationships"], list)

    async def test_returns_none_for_nonexistent_entity(self):
        """get_service_detail returns None when entity_id not found."""
        from src.memory.knowledge_graph import KnowledgeGraphStore

        store = KnowledgeGraphStore.__new__(KnowledgeGraphStore)
        store._url = "postgresql://test:5432/kg"
        store._pool = MagicMock()
        store._initialized = True

        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(return_value=None)
        mock_cm = AsyncMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_cm.__aexit__ = AsyncMock(return_value=False)
        store._pool.acquire.return_value = mock_cm

        result = await store.get_service_detail("service:nonexistent")
        assert result is None

    async def test_returns_none_on_connection_failure(self):
        """get_service_detail returns None on pool error (fail-open)."""
        from src.memory.knowledge_graph import KnowledgeGraphStore

        store = KnowledgeGraphStore.__new__(KnowledgeGraphStore)
        store._url = "postgresql://test:5432/kg"
        store._pool = AsyncMock()
        store._initialized = True

        store._pool.acquire.side_effect = Exception("connection lost")

        result = await store.get_service_detail("service:darwin-brain")
        assert result is None

    async def test_returns_none_when_not_initialized(self):
        """get_service_detail returns None when store has no URL."""
        from src.memory.knowledge_graph import KnowledgeGraphStore

        store = KnowledgeGraphStore(url="")

        result = await store.get_service_detail("service:darwin-brain")
        assert result is None


# =========================================================================
# Endpoint Tests: GET /api/knowledge-graph/services
# =========================================================================

class TestServicesEndpoint:
    """Tests for GET /api/knowledge-graph/services."""

    def test_returns_json_array(self, patched_client, mock_kg_store):
        """Endpoint returns list of services as JSON array."""
        resp = patched_client.get("/api/knowledge-graph/services")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) == 3
        mock_kg_store.list_services.assert_called_once()

    def test_response_shape(self, patched_client, mock_kg_store):
        """Each service in the response has required fields."""
        resp = patched_client.get("/api/knowledge-graph/services")
        data = resp.json()
        for svc in data:
            assert "entity_id" in svc
            assert "properties" in svc
            assert "last_seen" in svc
            assert "relationship_count" in svc

    def test_returns_empty_when_store_unavailable(self):
        """Returns [] when store is None (Postgres unavailable, fail-open)."""
        from src.routes.knowledge_graph_api import router

        app = FastAPI()
        app.include_router(router)

        async def _return_none():
            return None

        with patch("src.routes.knowledge_graph_api.get_kg_store", _return_none):
            empty_client = TestClient(app)
            resp = empty_client.get("/api/knowledge-graph/services")
            assert resp.status_code == 200
            assert resp.json() == []

    def test_returns_empty_when_store_returns_empty(self, patched_client, mock_kg_store):
        """Returns [] when store.list_services() returns empty list."""
        mock_kg_store.list_services = AsyncMock(return_value=[])
        resp = patched_client.get("/api/knowledge-graph/services")
        assert resp.status_code == 200
        assert resp.json() == []


# =========================================================================
# Endpoint Tests: GET /api/knowledge-graph/services/{entity_id}
# =========================================================================

class TestServiceDetailEndpoint:
    """Tests for GET /api/knowledge-graph/services/{entity_id}."""

    def test_returns_service_detail(self, patched_client, mock_kg_store):
        """Endpoint returns entity + relationships for known service."""
        resp = patched_client.get("/api/knowledge-graph/services/service:darwin-brain")
        assert resp.status_code == 200
        data = resp.json()
        assert data["entity_id"] == "service:darwin-brain"
        assert "properties" in data
        assert "last_seen" in data
        assert "relationships" in data
        assert isinstance(data["relationships"], list)
        assert len(data["relationships"]) == 3

    def test_direction_passes_through_store_value(self, patched_client, mock_kg_store):
        """Relationship `direction` must be the store's SQL UNION value, not
        recomputed from entity_type. All three fixture relationships have
        entity_type != "Service", so a buggy recompute (entity_type != "Service"
        -> "outgoing") would flatten every direction to "outgoing" -- this
        would not catch that regression since it only asserts on shape/count.
        """
        resp = patched_client.get("/api/knowledge-graph/services/service:darwin-brain")
        assert resp.status_code == 200
        rels = resp.json()["relationships"]
        directions_by_rel_type = {r["rel_type"]: r["direction"] for r in rels}
        assert directions_by_rel_type == {
            "AFFECTED": "incoming",
            "APPLIED_TO": "incoming",
            "RESOLVED_BY": "outgoing",
        }

    def test_returns_404_for_unknown_entity(self, patched_client, mock_kg_store):
        """Endpoint returns 404 when entity doesn't exist."""
        mock_kg_store.get_service_detail = AsyncMock(return_value=None)
        resp = patched_client.get("/api/knowledge-graph/services/service:nonexistent")
        assert resp.status_code == 404

    def test_returns_404_when_store_unavailable(self):
        """Returns 404 when store is None (Postgres unavailable)."""
        from src.routes.knowledge_graph_api import router

        app = FastAPI()
        app.include_router(router)

        async def _return_none():
            return None

        with patch("src.routes.knowledge_graph_api.get_kg_store", _return_none):
            empty_client = TestClient(app)
            resp = empty_client.get("/api/knowledge-graph/services/service:darwin-brain")
            assert resp.status_code == 404

    def test_url_encoded_entity_id(self, patched_client, mock_kg_store):
        """Entity ID with special chars is properly decoded."""
        resp = patched_client.get("/api/knowledge-graph/services/service%3Adarwin-brain")
        assert resp.status_code == 200
        mock_kg_store.get_service_detail.assert_called_once_with(
            "service:darwin-brain"
        )


# =========================================================================
# Endpoint Tests: GET /api/knowledge-graph/stats
# =========================================================================

class TestStatsEndpoint:
    """Tests for GET /api/knowledge-graph/stats."""

    def test_returns_entity_and_relationship_counts(self, mock_kg_store):
        """Endpoint returns counts grouped by type."""
        from src.routes.knowledge_graph_api import router

        mock_kg_store.get_stats = AsyncMock(return_value={
            "entities": {"Service": 3, "Event": 5, "Fix": 2},
            "relationships": {"AFFECTED": 3, "APPLIED_TO": 1, "RESOLVED_BY": 1},
            "last_updated": "2026-08-15T10:00:00+00:00",
        })

        app = FastAPI()
        app.include_router(router)

        async def _return_store():
            return mock_kg_store

        with patch("src.routes.knowledge_graph_api.get_kg_store", _return_store):
            stats_client = TestClient(app)
            resp = stats_client.get("/api/knowledge-graph/stats")

        assert resp.status_code == 200
        data = resp.json()
        assert "entities" in data
        assert "relationships" in data
        assert data["entities"]["Service"] == 3
        assert data["relationships"]["AFFECTED"] == 3

    def test_returns_empty_stats_when_store_unavailable(self):
        """Returns zero counts when store is None."""
        from src.routes.knowledge_graph_api import router

        app = FastAPI()
        app.include_router(router)

        async def _return_none():
            return None

        with patch("src.routes.knowledge_graph_api.get_kg_store", _return_none):
            empty_client = TestClient(app)
            resp = empty_client.get("/api/knowledge-graph/stats")
            assert resp.status_code == 200
            data = resp.json()
            assert data["entities"] == {} or data.get("entities", {}) == {}
            assert data["relationships"] == {} or data.get("relationships", {}) == {}
