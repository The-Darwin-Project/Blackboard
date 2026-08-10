# tests/test_entity_extractor.py
# @ai-rules:
# 1. [Purpose]: Tests for entity_extractor.py (T-6..T-8) and archivist KG integration (T-9..T-12).
# 2. [Pattern]: pytest + pytest-asyncio. AsyncMock for LLM adapter. Archivist.__new__() bypass pattern.
# 3. [Constraint]: Written from plan spec independently of implementation. Expected to fail until reconciliation.
# 4. [Gotcha]: extract_entities returns empty model on ANY error (timeout, parse, etc.) — never raises.
"""
Tests for entity extraction and archivist knowledge graph integration.

Covers:
  T-6: extract_entities returns structured KnowledgeGraphEntities from valid LLM JSON
  T-7: extract_entities returns empty model on TimeoutError
  T-8: extract_entities handles events with service=None (Event node only)
  T-9: archive_event calls entity extraction + upsert
  T-10: _archive_event_fallback calls entity extraction + upsert
  T-11: KG write failure doesn't break Qdrant archive
  T-12: backfill_knowledge_graph skips events already in graph
"""
from __future__ import annotations

import asyncio
import json
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# T-6, T-7, T-8: extract_entities unit tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestExtractEntities:
    """Unit tests for src.agents.entity_extractor.extract_entities."""

    async def test_returns_structured_entities_from_valid_llm_json(self):
        """T-6: Mocked LLM returning valid JSON produces KnowledgeGraphEntities."""
        from src.agents.entity_extractor import extract_entities

        mock_response = MagicMock()
        mock_response.text = json.dumps({
            "entities": [
                {"type": "service", "id": "darwin-brain", "properties": {"version": "2.0"}},
                {"type": "event", "id": "evt-abc12345", "properties": {"domain": "complicated"}},
            ],
            "relationships": [
                {
                    "from_type": "event",
                    "from_id": "evt-abc12345",
                    "rel_type": "AFFECTED",
                    "to_type": "service",
                    "to_id": "darwin-brain",
                },
            ],
        })

        with patch("src.agents.entity_extractor._get_client") as mock_get_client:
            mock_client = MagicMock()
            mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_client

            result = await extract_entities(
                event_summary={"symptom": "high CPU", "root_cause": "memory leak", "fix_action": "restart"},
                service="darwin-brain",
            )

        assert len(result.entities) == 2
        assert len(result.relationships) == 1
        assert result.entities[0].type == "service"
        assert result.relationships[0].rel_type == "AFFECTED"

    async def test_timeout_returns_empty_model(self):
        """T-7: TimeoutError from LLM returns empty KnowledgeGraphEntities."""
        from src.agents.entity_extractor import extract_entities

        with patch("src.agents.entity_extractor._get_client") as mock_get_client:
            mock_client = MagicMock()
            mock_client.aio.models.generate_content = AsyncMock(side_effect=asyncio.TimeoutError())
            mock_get_client.return_value = mock_client

            result = await extract_entities(
                event_summary={"symptom": "test", "root_cause": "test", "fix_action": "test"},
                service="some-service",
            )

        assert result.entities == []
        assert result.relationships == []

    async def test_no_service_extracts_event_only(self):
        """T-8: service=None produces Event entity only, no Service node."""
        from src.agents.entity_extractor import extract_entities

        mock_response = MagicMock()
        mock_response.text = json.dumps({
            "entities": [
                {"type": "event", "id": "evt-xyz99999", "properties": {"domain": "clear"}},
            ],
            "relationships": [],
        })

        with patch("src.agents.entity_extractor._get_client") as mock_get_client:
            mock_client = MagicMock()
            mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_client

            result = await extract_entities(
                event_summary={"symptom": "scheduled maintenance", "root_cause": "n/a", "fix_action": "none"},
                service=None,
            )

        assert len(result.entities) == 1
        assert result.entities[0].type == "event"
        service_nodes = [e for e in result.entities if e.type == "service"]
        assert len(service_nodes) == 0

    async def test_invalid_json_returns_empty_model(self):
        """Complement: malformed LLM output returns empty model (fail-open contract)."""
        from src.agents.entity_extractor import extract_entities

        mock_response = MagicMock()
        mock_response.text = "This is not JSON at all"

        with patch("src.agents.entity_extractor._get_client") as mock_get_client:
            mock_client = MagicMock()
            mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_client

            result = await extract_entities(
                event_summary={"symptom": "test"},
                service="some-service",
            )

        assert result.entities == []
        assert result.relationships == []


# ---------------------------------------------------------------------------
# T-9, T-10, T-11: Archivist integration with KG
# ---------------------------------------------------------------------------

def _make_mock_event(event_id: str = "evt-test1234", service: str = "darwin-brain"):
    """Factory for a minimal mock EventDocument."""
    mock_event = MagicMock()
    mock_event.id = event_id
    mock_event.service = service
    mock_event.source = "chat"

    mock_turn = MagicMock()
    mock_turn.action = "message"
    mock_turn.actor = "user"
    mock_turn.timestamp = time.time() - 300
    mock_turn.thoughts = "test thought"
    mock_turn.evidence = None
    mock_turn.result = None
    mock_turn.plan = None
    mock_event.conversation = [mock_turn]

    mock_input = MagicMock()
    mock_input.reason = "test event"
    mock_input.evidence = MagicMock()
    mock_input.evidence.brain_domain = "complicated"
    mock_input.evidence.domain = "complicated"
    mock_event.event = mock_input

    return mock_event


@pytest.mark.asyncio
class TestArchivistKGIntegration:
    """T-9, T-10, T-11: archive_event and _archive_event_fallback call entity extraction."""

    async def test_archive_event_calls_entity_extraction(self):
        """T-9: archive_event calls extract_entities then upsert_entities."""
        from src.agents.archivist import Archivist

        archivist = Archivist.__new__(Archivist)
        archivist._initialized = True
        archivist._knowledge_ready = False
        archivist.pulse_port = None

        mock_vs = AsyncMock()
        mock_vs.upsert.return_value = None
        archivist._vector_store = mock_vs
        archivist._embed = AsyncMock(return_value=[0.1] * 768)

        mock_claude = AsyncMock()
        mock_response = MagicMock()
        mock_response.function_call = MagicMock()
        mock_response.function_call.args = {
            "symptom": "high cpu",
            "root_cause": "memory leak",
            "fix_action": "restart pod",
            "keywords": ["cpu"],
            "outcome": "resolved",
            "reference_facts": [],
        }
        mock_response.usage = MagicMock()
        mock_claude.generate.return_value = mock_response
        archivist._get_claude_adapter = AsyncMock(return_value=mock_claude)

        mock_kg_store = AsyncMock()
        mock_kg_store.upsert_entities.return_value = None
        archivist._kg_store = mock_kg_store

        mock_kg_entities = MagicMock()
        mock_kg_entities.entities = [{"type": "service", "id": "darwin-brain", "properties": {}}]
        mock_kg_entities.relationships = []

        event = _make_mock_event()

        with patch("src.agents.entity_extractor.extract_entities", new_callable=AsyncMock) as mock_extract:
            mock_extract.return_value = mock_kg_entities
            await archivist.archive_event(event)

            mock_extract.assert_called_once()
            mock_kg_store.upsert_entities.assert_called_once_with(
                mock_kg_entities.entities, mock_kg_entities.relationships
            )

    async def test_archive_event_fallback_calls_entity_extraction(self):
        """T-10: _archive_event_fallback also calls extract_entities + upsert."""
        from src.agents.archivist import Archivist

        archivist = Archivist.__new__(Archivist)
        archivist._initialized = True
        archivist._knowledge_ready = False
        archivist.pulse_port = None

        mock_vs = AsyncMock()
        mock_vs.upsert.return_value = None
        archivist._vector_store = mock_vs
        archivist._embed = AsyncMock(return_value=[0.1] * 768)

        mock_adapter = AsyncMock()
        mock_response = MagicMock()
        mock_response.text = json.dumps({
            "symptom": "slow query",
            "root_cause": "missing index",
            "fix_action": "add index",
            "keywords": ["postgres"],
            "outcome": "resolved",
            "reference_facts": [],
        })
        mock_response.usage = MagicMock()
        mock_adapter.generate.return_value = mock_response
        archivist._get_adapter = AsyncMock(return_value=mock_adapter)

        mock_kg_store = AsyncMock()
        mock_kg_store.upsert_entities.return_value = None
        archivist._kg_store = mock_kg_store

        mock_kg_entities = MagicMock()
        mock_kg_entities.entities = [{"type": "event", "id": "evt-test1234", "properties": {}}]
        mock_kg_entities.relationships = []

        event = _make_mock_event()

        with patch("src.agents.entity_extractor.extract_entities", new_callable=AsyncMock) as mock_extract:
            mock_extract.return_value = mock_kg_entities
            await archivist._archive_event_fallback(event, "conversation text here", duration=300)

            mock_extract.assert_called_once()
            mock_kg_store.upsert_entities.assert_called_once()

    async def test_kg_failure_does_not_break_qdrant_archive(self):
        """T-11: KG upsert failure does NOT prevent Qdrant vector archive."""
        from src.agents.archivist import Archivist

        archivist = Archivist.__new__(Archivist)
        archivist._initialized = True
        archivist._knowledge_ready = False
        archivist.pulse_port = None

        mock_vs = AsyncMock()
        mock_vs.upsert.return_value = None
        archivist._vector_store = mock_vs
        archivist._embed = AsyncMock(return_value=[0.1] * 768)

        mock_claude = AsyncMock()
        mock_response = MagicMock()
        mock_response.function_call = MagicMock()
        mock_response.function_call.args = {
            "symptom": "test",
            "root_cause": "test",
            "fix_action": "test",
            "keywords": [],
            "outcome": "resolved",
            "reference_facts": [],
        }
        mock_response.usage = MagicMock()
        mock_claude.generate.return_value = mock_response
        archivist._get_claude_adapter = AsyncMock(return_value=mock_claude)

        mock_kg_store = AsyncMock()
        mock_kg_store.upsert_entities.side_effect = RuntimeError("Memgraph crashed")
        archivist._kg_store = mock_kg_store

        mock_kg_entities = MagicMock()
        mock_kg_entities.entities = [{"type": "service", "id": "test", "properties": {}}]
        mock_kg_entities.relationships = []

        event = _make_mock_event()

        with patch("src.agents.entity_extractor.extract_entities", new_callable=AsyncMock) as mock_extract:
            mock_extract.return_value = mock_kg_entities
            await archivist.archive_event(event)

        mock_vs.upsert.assert_called_once()


# ---------------------------------------------------------------------------
# T-12: backfill_knowledge_graph skips existing entries
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestBackfillKnowledgeGraph:
    """T-12: backfill only calls extract for events missing from graph."""

    async def test_backfill_skips_existing_graph_entries(self):
        """T-12: Given 3 archived events, 1 missing from graph, extract called once."""
        from src.agents.archivist import Archivist

        archivist = Archivist.__new__(Archivist)
        archivist._initialized = True
        archivist._knowledge_ready = False
        archivist.pulse_port = None

        mock_vs = AsyncMock()
        mock_vs.scroll.return_value = (
            [
                {"id": "pt-1", "payload": {"event_id": "evt-aaa11111", "symptom": "a", "root_cause": "a", "fix_action": "a"}},
                {"id": "pt-2", "payload": {"event_id": "evt-bbb22222", "symptom": "b", "root_cause": "b", "fix_action": "b"}},
                {"id": "pt-3", "payload": {"event_id": "evt-ccc33333", "symptom": "c", "root_cause": "c", "fix_action": "c"}},
            ],
            None,  # no next page
        )
        archivist._vector_store = mock_vs

        mock_kg_store = AsyncMock()
        mock_kg_store.upsert_entities = AsyncMock(return_value=None)
        mock_kg_store.has_entity = AsyncMock(side_effect=[
            True,   # evt-aaa11111 exists
            True,   # evt-bbb22222 exists
            False,  # evt-ccc33333 missing — needs extraction
        ])
        archivist._kg_store = mock_kg_store

        mock_kg_entities = MagicMock()
        mock_kg_entities.entities = [{"type": "event", "id": "evt-ccc33333", "properties": {}}]
        mock_kg_entities.relationships = []

        archivist.get_memory = AsyncMock(return_value={
            "payload": {"event_id": "evt-ccc33333", "symptom": "c", "root_cause": "c", "fix_action": "c", "service": "test-svc"}
        })
        archivist._ensure_initialized = AsyncMock(return_value=True)

        with patch("src.agents.entity_extractor.extract_entities", new_callable=AsyncMock) as mock_extract:
            mock_extract.return_value = mock_kg_entities

            mock_blackboard = AsyncMock()
            mock_blackboard.get_closed_event_ids = AsyncMock(return_value=["evt-aaa11111", "evt-bbb22222", "evt-ccc33333"])
            count = await archivist.backfill_knowledge_graph(mock_blackboard)

            assert mock_extract.call_count == 1
            mock_kg_store.upsert_entities.assert_called_once()
            assert count == 1
