# tests/test_knowledge_graph.py
# @ai-rules:
# 1. [Purpose]: Tests for KnowledgeGraphStore adapter (src/memory/knowledge_graph.py).
# 2. [Pattern]: pytest + pytest-asyncio. AsyncMock for asyncpg pool/connection.
# 3. [Constraint]: All KG methods are fail-open — never raise, return None/False/empty on failure.
"""
Tests for KnowledgeGraphStore — the Postgres adjacency table adapter.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.mark.asyncio
class TestUpsertEntities:
    """T-1, T-2, T-3: upsert_entities behavior."""

    async def test_upsert_creates_rows(self):
        """T-1: Upsert executes INSERT ON CONFLICT for entities and relationships."""
        from src.memory.knowledge_graph import KnowledgeGraphStore

        store = KnowledgeGraphStore.__new__(KnowledgeGraphStore)
        store._url = "postgresql://test:5432/kg"
        store._pool = MagicMock()
        store._initialized = True

        mock_conn = AsyncMock()
        mock_cm = AsyncMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_cm.__aexit__ = AsyncMock(return_value=False)
        store._pool.acquire.return_value = mock_cm

        entities = [
            {"type": "Service", "id": "service:darwin-brain", "properties": {"version": "1.0"}},
            {"type": "Event", "id": "event:evt-abc12345", "properties": {"domain": "complicated"}},
        ]
        relationships = [
            {
                "from_type": "Event",
                "from_id": "event:evt-abc12345",
                "rel_type": "AFFECTED",
                "to_type": "Service",
                "to_id": "service:darwin-brain",
            },
        ]

        await store.upsert_entities(entities, relationships)

        assert mock_conn.execute.call_count >= 3  # 2 entities + 1 relationship

    async def test_upsert_is_idempotent(self):
        """T-2: Same entity twice — ON CONFLICT UPDATE last_seen."""
        from src.memory.knowledge_graph import KnowledgeGraphStore

        store = KnowledgeGraphStore.__new__(KnowledgeGraphStore)
        store._url = "postgresql://test:5432/kg"
        store._pool = MagicMock()
        store._initialized = True

        mock_conn = AsyncMock()
        mock_cm = AsyncMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_cm.__aexit__ = AsyncMock(return_value=False)
        store._pool.acquire.return_value = mock_cm

        entity = {"type": "Service", "id": "service:darwin-brain", "properties": {}}
        await store.upsert_entities([entity, entity], [])

        # Each entity gets one INSERT call (ON CONFLICT handles dedup in DB)
        assert mock_conn.execute.call_count == 2
        for call in mock_conn.execute.call_args_list:
            assert "ON CONFLICT" in call.args[0]

    async def test_connection_failure_is_fail_open(self):
        """T-3: Connection error returns None, logs warning, no exception."""
        from src.memory.knowledge_graph import KnowledgeGraphStore

        store = KnowledgeGraphStore.__new__(KnowledgeGraphStore)
        store._url = "postgresql://test:5432/kg"
        store._pool = AsyncMock()
        store._initialized = True

        store._pool.acquire.side_effect = ConnectionError("connection refused")

        entities = [{"type": "Service", "id": "service:test", "properties": {}}]
        result = await store.upsert_entities(entities, [])

        assert result is None


@pytest.mark.asyncio
class TestLazyInit:
    """T-4: No connection on construction."""

    async def test_no_connection_on_construction(self):
        """T-4: Constructing the store does NOT create a pool."""
        from src.memory.knowledge_graph import KnowledgeGraphStore

        store = KnowledgeGraphStore(url="postgresql://test:5432/kg")
        assert store._pool is None
        assert store._initialized is False


@pytest.mark.asyncio
class TestHealthCheck:
    """T-5: health_check returns status."""

    async def test_health_check_returns_true_when_connected(self):
        """T-5: Connected Postgres returns True."""
        from src.memory.knowledge_graph import KnowledgeGraphStore

        store = KnowledgeGraphStore.__new__(KnowledgeGraphStore)
        store._url = "postgresql://test:5432/kg"
        store._pool = MagicMock()
        store._initialized = True

        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(return_value={"ok": 1})
        mock_cm = AsyncMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_cm.__aexit__ = AsyncMock(return_value=False)
        store._pool.acquire.return_value = mock_cm

        result = await store.health_check()
        assert result is True

    async def test_health_check_returns_false_on_failure(self):
        """T-5b: health_check returns False on error."""
        from src.memory.knowledge_graph import KnowledgeGraphStore

        store = KnowledgeGraphStore.__new__(KnowledgeGraphStore)
        store._url = "postgresql://test:5432/kg"
        store._pool = AsyncMock()
        store._initialized = True

        store._pool.acquire.side_effect = Exception("connection lost")

        result = await store.health_check()
        assert result is False
