# tests/test_knowledge_graph.py
# @ai-rules:
# 1. [Purpose]: Tests for KnowledgeGraphStore adapter (src/memory/knowledge_graph.py).
# 2. [Pattern]: pytest + pytest-asyncio. AsyncMock for neo4j driver session/transaction.
# 3. [Constraint]: Tests written from plan spec T-1..T-5. Do NOT import implementation internals.
# 4. [Gotcha]: All KG methods are fail-open — never raise, return None/False/empty on failure.
"""
Tests for KnowledgeGraphStore — the Memgraph/Neo4j adapter.

Covers:
  T-1: Upsert creates new nodes via Cypher MERGE
  T-2: Upsert is idempotent (ON MATCH SET last_seen)
  T-3: Connection failure is fail-open (returns None, no exception)
  T-4: Lazy init — no connection attempt until first method call
  T-5: Health check returns True when connected
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.mark.asyncio
class TestUpsertEntities:
    """T-1, T-2, T-3: upsert_entities behavior."""

    async def test_upsert_creates_nodes_with_merge(self):
        """T-1: Upsert executes Cypher MERGE with correct params for entities and relationships."""
        from src.memory.knowledge_graph import KnowledgeGraphStore

        store = KnowledgeGraphStore.__new__(KnowledgeGraphStore)
        store._url = "bolt://test:7687"
        store._driver = MagicMock()
        store._initialized = True

        mock_session = AsyncMock()
        mock_session.run = AsyncMock()
        store._driver.session.return_value = AsyncMock(
            __aenter__=AsyncMock(return_value=mock_session),
            __aexit__=AsyncMock(return_value=False),
        )

        entities = [
            {"type": "service", "id": "darwin-brain", "properties": {"version": "1.0"}},
            {"type": "event", "id": "evt-abc12345", "properties": {"domain": "complicated"}},
        ]
        relationships = [
            {
                "from_type": "event",
                "from_id": "evt-abc12345",
                "rel_type": "AFFECTED",
                "to_type": "service",
                "to_id": "darwin-brain",
            },
        ]

        await store.upsert_entities(entities, relationships)

        assert mock_session.run.call_count >= 3  # 2 entities + 1 relationship
        calls = [str(c) for c in mock_session.run.call_args_list]
        merge_calls = [c for c in calls if "MERGE" in c.upper()]
        assert len(merge_calls) >= 3

    async def test_upsert_is_idempotent(self):
        """T-2: Same entity twice results in ON MATCH SET update, not duplicate."""
        from src.memory.knowledge_graph import KnowledgeGraphStore

        store = KnowledgeGraphStore.__new__(KnowledgeGraphStore)
        store._url = "bolt://test:7687"
        store._driver = MagicMock()
        store._initialized = True

        mock_session = AsyncMock()
        mock_session.run = AsyncMock()
        store._driver.session.return_value = AsyncMock(
            __aenter__=AsyncMock(return_value=mock_session),
            __aexit__=AsyncMock(return_value=False),
        )

        entity = {"type": "service", "id": "darwin-brain", "properties": {"version": "1.0"}}

        await store.upsert_entities([entity, entity], [])

        cypher_calls = [str(c) for c in mock_session.run.call_args_list]
        for call_str in cypher_calls:
            if "MERGE" in call_str.upper():
                assert "last_seen" in call_str.lower() or "ON MATCH" in call_str.upper() or "SET" in call_str.upper()

    async def test_connection_failure_is_fail_open(self):
        """T-3: ConnectionError returns None, logs warning, does not raise."""
        from src.memory.knowledge_graph import KnowledgeGraphStore

        store = KnowledgeGraphStore.__new__(KnowledgeGraphStore)
        store._driver = AsyncMock()
        store._initialized = True

        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_session.execute_write = AsyncMock(side_effect=ConnectionError("Memgraph unavailable"))
        store._driver.session.return_value = mock_session

        entities = [{"type": "service", "id": "test-svc", "properties": {}}]

        result = await store.upsert_entities(entities, [])

        assert result is None


@pytest.mark.asyncio
class TestLazyInit:
    """T-4: KnowledgeGraphStore defers connection to first method call."""

    async def test_no_connection_on_construction(self):
        """T-4: Constructing the store does NOT trigger a driver connection."""
        from src.memory.knowledge_graph import KnowledgeGraphStore

        store = KnowledgeGraphStore(url="bolt://test:7687")

        assert store._driver is None
        assert store._initialized is False


@pytest.mark.asyncio
class TestHealthCheck:
    """T-5: health_check returns status."""

    async def test_health_check_returns_true_when_connected(self):
        """T-5: Connected Memgraph returns True."""
        from src.memory.knowledge_graph import KnowledgeGraphStore

        store = KnowledgeGraphStore.__new__(KnowledgeGraphStore)
        store._url = "bolt://test:7687"
        store._driver = MagicMock()
        store._initialized = True

        mock_record = {"ok": 1}
        mock_result = AsyncMock()
        mock_result.single = AsyncMock(return_value=mock_record)
        mock_session = AsyncMock()
        mock_session.run = AsyncMock(return_value=mock_result)
        store._driver.session.return_value = AsyncMock(
            __aenter__=AsyncMock(return_value=mock_session),
            __aexit__=AsyncMock(return_value=False),
        )

        result = await store.health_check()
        assert result is True

    async def test_health_check_returns_false_on_failure(self):
        """Complement to T-5: health_check returns False on connection error (fail-open)."""
        from src.memory.knowledge_graph import KnowledgeGraphStore

        store = KnowledgeGraphStore.__new__(KnowledgeGraphStore)
        store._url = "bolt://test:7687"
        store._driver = AsyncMock()
        store._initialized = True

        mock_session = AsyncMock()
        mock_session.run = AsyncMock(side_effect=Exception("connection lost"))
        store._driver.session.return_value = mock_session

        result = await store.health_check()
        assert result is False
        store._driver = AsyncMock()
        store._initialized = True

        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_session.run = AsyncMock(side_effect=ConnectionError("timeout"))
        store._driver.session.return_value = mock_session

        result = await store.health_check()

        assert result is False
