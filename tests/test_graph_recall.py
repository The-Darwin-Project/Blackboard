# tests/test_graph_recall.py
# @ai-rules:
# 1. [Purpose]: Tests for graph_recall.get_graph_context (src/agents/graph_recall.py).
# 2. [Pattern]: pytest + pytest-asyncio. AsyncMock for KnowledgeGraphStore methods.
# 3. [Constraint]: All graph recall paths are fail-open — return None on failure, never raise.
# 4. [Gotcha]: Tests written against planned interface, not implementation. May need
#    import path adjustment once the module is created by the code executor.
"""
Tests for graph_recall.get_graph_context — the KG → SI injection bridge.

Validates the contract: service context in → formatted <prior_knowledge> fence
or None. All failure modes return None (fail-open).
"""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest


def _make_kg_store_stub(query_result: list | None = None, has_entity_result: bool = True):
    """Create a KnowledgeGraphStore-like stub with controllable query_related."""
    store = MagicMock()
    store.query_related = AsyncMock(return_value=query_result or [])
    store.has_entity = AsyncMock(return_value=has_entity_result)
    return store


def _make_related_entities(count: int = 3) -> list[dict]:
    """Generate N related entity rows matching query_related() output shape."""
    entities = []
    for i in range(count):
        entities.append({
            "entity_type": "Event",
            "entity_id": f"event:evt-{i:08x}",
            "properties": {"domain": "complicated", "summary": f"Event {i} summary"},
            "rel_type": "AFFECTED",
        })
    return entities


@pytest.mark.asyncio
class TestGetGraphContextHappyPath:
    """T-R1: get_graph_context returns formatted fence when graph has data."""

    async def test_returns_prior_knowledge_fence_with_entities(self):
        """T-R1: Output contains <prior_knowledge source="knowledge_graph" and entity data."""
        from src.agents.graph_recall import get_graph_context

        entities = _make_related_entities(3)
        store = _make_kg_store_stub(query_result=entities)

        result = await get_graph_context(
            kg_store=store,
            service="kubevirt-plugin",
            event_source="aligner",
            domain="complicated",
        )

        assert result is not None
        assert '<prior_knowledge source="knowledge_graph"' in result
        assert "event:evt-00000000" in result
        store.query_related.assert_called_once()
        call_args = store.query_related.call_args
        assert call_args[0][0] == "Service"
        assert "kubevirt-plugin" in call_args[0][1]


@pytest.mark.asyncio
class TestGetGraphContextEmpty:
    """T-R2: get_graph_context returns None when graph returns empty."""

    async def test_returns_none_on_empty_graph(self):
        """T-R2: Empty query_related result → None (triggers Qdrant fallback)."""
        from src.agents.graph_recall import get_graph_context

        store = _make_kg_store_stub(query_result=[])

        result = await get_graph_context(
            kg_store=store,
            service="kubevirt-plugin",
        )

        assert result is None


@pytest.mark.asyncio
class TestGetGraphContextTimeout:
    """T-R3: get_graph_context returns None on timeout."""

    async def test_returns_none_on_timeout(self):
        """T-R3: asyncio.TimeoutError → None, does not raise."""
        from src.agents.graph_recall import get_graph_context

        store = _make_kg_store_stub()
        store.query_related = AsyncMock(side_effect=asyncio.TimeoutError())

        result = await get_graph_context(
            kg_store=store,
            service="kubevirt-plugin",
        )

        assert result is None


@pytest.mark.asyncio
class TestGetGraphContextConnectionFailure:
    """T-R4: get_graph_context returns None on KG connection failure."""

    async def test_returns_none_on_connection_error(self):
        """T-R4: Any exception → None (fail-open)."""
        from src.agents.graph_recall import get_graph_context

        store = _make_kg_store_stub()
        store.query_related = AsyncMock(side_effect=ConnectionError("connection refused"))

        result = await get_graph_context(
            kg_store=store,
            service="kubevirt-plugin",
        )

        assert result is None

    async def test_returns_none_on_generic_exception(self):
        """T-R4b: RuntimeError variant → None."""
        from src.agents.graph_recall import get_graph_context

        store = _make_kg_store_stub()
        store.query_related = AsyncMock(side_effect=RuntimeError("pool closed"))

        result = await get_graph_context(
            kg_store=store,
            service="kubevirt-plugin",
        )

        assert result is None


@pytest.mark.asyncio
class TestGetGraphContextOutputCap:
    """T-R5: Output capped at ~8000 chars (~2000 tokens)."""

    async def test_output_truncated_for_many_entities(self):
        """T-R5: Large graph result is truncated to ~8000 chars."""
        from src.agents.graph_recall import get_graph_context

        entities = _make_related_entities(200)
        store = _make_kg_store_stub(query_result=entities)

        result = await get_graph_context(
            kg_store=store,
            service="kubevirt-plugin",
        )

        assert result is not None
        assert len(result) <= 9000  # ~8000 + fence overhead


@pytest.mark.asyncio
class TestGetGraphContextServiceSkip:
    """T-R6: Service "general" and "system" are skipped."""

    async def test_general_service_returns_none(self):
        """T-R6a: service="general" → None, no KG query made."""
        from src.agents.graph_recall import get_graph_context

        store = _make_kg_store_stub(query_result=_make_related_entities(5))

        result = await get_graph_context(
            kg_store=store,
            service="general",
        )

        assert result is None
        store.query_related.assert_not_called()

    async def test_system_service_returns_none(self):
        """T-R6b: service="system" → None, no KG query made."""
        from src.agents.graph_recall import get_graph_context

        store = _make_kg_store_stub(query_result=_make_related_entities(5))

        result = await get_graph_context(
            kg_store=store,
            service="system",
        )

        assert result is None
        store.query_related.assert_not_called()

    async def test_none_kg_store_returns_none(self):
        """Edge case: kg_store=None → None, no crash."""
        from src.agents.graph_recall import get_graph_context

        result = await get_graph_context(
            kg_store=None,
            service="kubevirt-plugin",
        )

        assert result is None
