# tests/test_brain_graph_integration.py
# @ai-rules:
# 1. [Purpose]: Tests for Brain's KG integration points: graph recall in _build_system_prompt,
#    has_graph_edges in _extract_context_flags, post-agent enrichment.
# 2. [Pattern]: Module-level mocks for graph_recall, entity_extractor. Binds Brain methods to stubs.
# 3. [Constraint]: Does NOT test graph_recall internals — only that Brain calls it correctly.
# 4. [Gotcha]: Brain methods like _get_graph_recall, _check_graph_edges must be bound to stubs
#    since _build_system_prompt calls self._get_graph_recall().
"""
Tests for Brain ↔ Knowledge Graph integration.

Validates: pre-generation recall injection, has_graph_edges flag, post-agent
graph enrichment. Tests the Brain's interaction with graph_recall and
KnowledgeGraphStore, not the modules themselves.
"""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.memory.knowledge_graph import KnowledgeGraphStore


def _make_event_stub(
    source: str = "chat",
    service: str = "kubevirt-plugin",
    brain_phase: str = "triage",
    subject_type: str = "service",
    conversation: list | None = None,
):
    """Minimal EventDocument-like stub for Brain methods."""
    evidence = SimpleNamespace(
        kargo_context=None,
        github_context=None,
    )
    inner_event = SimpleNamespace(evidence=evidence)
    return SimpleNamespace(
        id="evt-test0001",
        source=source,
        service=service,
        brain_phase=brain_phase,
        subject_type=subject_type,
        event=inner_event,
        conversation=conversation or [],
        active_plan=None,
        slack_thread_ts=None,
    )


def _make_brain_stub(kg_store=None):
    """Build a Brain-like object with mocked _skill_loader, blackboard, and KG store.

    Binds actual Brain methods that reference self._get_graph_recall etc.
    to the stub so _build_system_prompt works.
    """
    from src.agents.brain import Brain

    loader = MagicMock()
    loader.resolve_dependencies_with_paths.return_value = [
        ("always/identity.md", "# Identity"),
    ]
    loader.get_all_paths_for_phase.return_value = []
    loader.find_paths_by_tag.return_value = []
    loader.get_tag_type.side_effect = lambda p: "skill"
    loader.available_phases.return_value = ["always"]
    loader.get_with_meta.return_value = None

    blackboard = AsyncMock()
    blackboard.get_active_events = AsyncMock(return_value=[])
    blackboard.get_recent_closed_for_service = AsyncMock(return_value=[])

    archivist_mock = MagicMock()
    archivist_mock.kg_store = kg_store

    brain = SimpleNamespace(
        _skill_loader=loader,
        _build_event_state_header=lambda event, ctx: "## EVENT STATE HEADER",
        _post_agent_recall=AsyncMock(return_value=None),
        blackboard=blackboard,
        _waiting_for_user={},
        agents={"_archivist_memory": archivist_mock},
        _recall_lessons={},
        _graph_enrich_tasks=set(),
        _enriched_turns=set(),
    )

    # Bind actual Brain methods to the stub so self.method() works
    brain._get_graph_recall = Brain._get_graph_recall.__get__(brain, type(brain))
    brain._check_graph_edges = Brain._check_graph_edges.__get__(brain, type(brain))
    brain._enrich_graph_from_agent = Brain._enrich_graph_from_agent.__get__(brain, type(brain))
    brain._schedule_graph_enrichment = Brain._schedule_graph_enrichment.__get__(brain, type(brain))
    brain._format_recall_block = Brain._format_recall_block.__get__(brain, type(brain))

    return brain


@pytest.mark.asyncio
class TestPreGenerationRecall:
    """T-B1, T-B2: _build_system_prompt graph recall integration."""

    @patch("src.agents.graph_recall.get_graph_context", new_callable=AsyncMock)
    async def test_calls_graph_recall_when_kg_available(self, mock_get_graph_context):
        """T-B1: get_graph_context called with correct args when kg_store is available."""
        mock_get_graph_context.return_value = (
            '<prior_knowledge source="knowledge_graph" volatile="true">\n'
            "Service: kubevirt-plugin\n"
            "Related: Event evt-abc12345 (AFFECTED)\n"
            "</prior_knowledge>"
        )

        kg_store = MagicMock(spec=KnowledgeGraphStore)
        brain = _make_brain_stub(kg_store=kg_store)

        from src.agents.brain import Brain
        prompt = await Brain._build_system_prompt(
            brain, _make_event_stub(service="kubevirt-plugin"),
            ["always"], context_flags=None,
        )

        mock_get_graph_context.assert_called_once()
        assert "prior_knowledge" in prompt

    @patch("src.agents.graph_recall.get_graph_context", new_callable=AsyncMock)
    async def test_skips_graph_recall_for_general_service(self, mock_get_graph_context):
        """T-B2: No KG call made when service is "general"."""
        brain = _make_brain_stub()

        from src.agents.brain import Brain
        await Brain._build_system_prompt(
            brain, _make_event_stub(service="general"),
            ["always"], context_flags=None,
        )

        mock_get_graph_context.assert_not_called()


@pytest.mark.asyncio
class TestHasGraphEdgesFlag:
    """T-B3, T-B4, T-B5: has_graph_edges in _extract_context_flags."""

    async def test_flag_true_when_entity_exists(self):
        """T-B3: has_graph_edges=True when kg_store.has_entity() returns True."""
        kg_store = MagicMock(spec=KnowledgeGraphStore)
        kg_store.has_entity = AsyncMock(return_value=True)

        brain = _make_brain_stub(kg_store=kg_store)
        event = _make_event_stub(service="kubevirt-plugin")

        from src.agents.brain import Brain
        flags = await Brain._extract_context_flags(brain, event)

        assert flags["has_graph_edges"] is True
        kg_store.has_entity.assert_called_once_with(
            "Service", "service:kubevirt-plugin"
        )

    async def test_flag_false_when_entity_missing(self):
        """T-B4: has_graph_edges=False when kg_store.has_entity() returns False."""
        kg_store = MagicMock(spec=KnowledgeGraphStore)
        kg_store.has_entity = AsyncMock(return_value=False)

        brain = _make_brain_stub(kg_store=kg_store)
        event = _make_event_stub(service="kubevirt-plugin")

        from src.agents.brain import Brain
        flags = await Brain._extract_context_flags(brain, event)

        assert flags["has_graph_edges"] is False

    async def test_flag_false_when_kg_store_none(self):
        """T-B5: has_graph_edges=False when kg_store is None (no crash)."""
        brain = _make_brain_stub(kg_store=None)
        event = _make_event_stub(service="kubevirt-plugin")

        from src.agents.brain import Brain
        flags = await Brain._extract_context_flags(brain, event)

        assert flags["has_graph_edges"] is False


@pytest.mark.asyncio
class TestPostAgentEnrichment:
    """T-B6, T-B7: Post-agent graph enrichment calls."""

    @patch("src.agents.entity_extractor.extract_entities", new_callable=AsyncMock)
    async def test_enrichment_calls_extract_and_upsert(self, mock_extract):
        """T-B6: _enrich_graph_from_agent calls extract_entities + kg_store.upsert_entities."""
        from src.agents.entity_extractor import KnowledgeGraphEntities, Entity, Relationship

        mock_extract.return_value = KnowledgeGraphEntities(
            entities=[
                Entity(type="Service", id="service:kubevirt-plugin", properties={"name": "kubevirt-plugin"}),
                Entity(type="Event", id="event:evt-test0001", properties={"domain": "complicated"}),
            ],
            relationships=[
                Relationship(
                    from_type="Event", from_id="event:evt-test0001",
                    rel_type="AFFECTED",
                    to_type="Service", to_id="service:kubevirt-plugin",
                ),
            ],
        )

        kg_store = MagicMock(spec=KnowledgeGraphStore)
        kg_store.upsert_entities = AsyncMock()

        brain = _make_brain_stub(kg_store=kg_store)

        agent_turn = SimpleNamespace(
            actor="developer",
            result="Fixed the pod crash loop by updating resource limits. The deployment was using 128Mi but needed 512Mi.",
            thoughts=None,
            action="result",
            taskForAgent=None,
        )
        event = _make_event_stub(
            service="kubevirt-plugin",
            conversation=[agent_turn],
        )
        event.domain = "complicated"

        from src.agents.brain import Brain
        await Brain._enrich_graph_from_agent(brain, event)

        mock_extract.assert_called_once()
        kg_store.upsert_entities.assert_called_once()

    @patch("src.agents.entity_extractor.extract_entities", new_callable=AsyncMock)
    async def test_enrichment_exception_does_not_propagate(self, mock_extract):
        """T-B7: Exception in enrichment is logged, not raised (fire-and-forget)."""
        mock_extract.side_effect = RuntimeError("extraction service unavailable")

        kg_store = MagicMock(spec=KnowledgeGraphStore)
        brain = _make_brain_stub(kg_store=kg_store)

        agent_turn = SimpleNamespace(
            actor="developer",
            result="Fixed the pod crash loop by updating resource limits. The deployment was using 128Mi.",
            thoughts=None,
            action="result",
            taskForAgent=None,
        )
        event = _make_event_stub(
            service="kubevirt-plugin",
            conversation=[agent_turn],
        )
        event.domain = "complicated"

        from src.agents.brain import Brain
        # Must NOT raise
        await Brain._enrich_graph_from_agent(brain, event)

    @patch("src.agents.entity_extractor.extract_entities", new_callable=AsyncMock)
    async def test_enrichment_upsert_failure_does_not_propagate(self, mock_extract):
        """T-B7b: kg_store.upsert_entities failure is fire-and-forget."""
        from src.agents.entity_extractor import KnowledgeGraphEntities

        mock_extract.return_value = KnowledgeGraphEntities(entities=[], relationships=[])

        kg_store = MagicMock(spec=KnowledgeGraphStore)
        kg_store.upsert_entities = AsyncMock(side_effect=ConnectionError("PG down"))

        brain = _make_brain_stub(kg_store=kg_store)

        agent_turn = SimpleNamespace(
            actor="developer",
            result="Fixed the pod crash loop by updating resource limits. The deployment was using 128Mi.",
            thoughts=None,
            action="result",
            taskForAgent=None,
        )
        event = _make_event_stub(
            service="kubevirt-plugin",
            conversation=[agent_turn],
        )
        event.domain = "complicated"

        from src.agents.brain import Brain
        # Must NOT raise
        await Brain._enrich_graph_from_agent(brain, event)

    @patch("src.agents.entity_extractor.extract_entities", new_callable=AsyncMock)
    async def test_enrichment_key_uses_identity_not_value_equality(self, mock_extract):
        """Regression: `.index(last_agent)` used value equality, so a field-for-field
        identical earlier turn would make it resolve to the wrong (earlier) turn_idx,
        corrupting the idempotency key. The fix scans by identity (`is`) from the end.
        """
        from src.agents.entity_extractor import KnowledgeGraphEntities

        mock_extract.return_value = KnowledgeGraphEntities(entities=[], relationships=[])

        kg_store = MagicMock(spec=KnowledgeGraphStore)
        kg_store.upsert_entities = AsyncMock()

        brain = _make_brain_stub(kg_store=kg_store)

        duplicate_text = (
            "Fixed the pod crash loop by updating resource limits. "
            "The deployment was using 128Mi but needed 512Mi."
        )
        earlier_turn = SimpleNamespace(
            actor="developer", result=duplicate_text, thoughts=None,
            action="result", taskForAgent=None,
        )
        later_turn = SimpleNamespace(
            actor="developer", result=duplicate_text, thoughts=None,
            action="result", taskForAgent=None,
        )
        # Sanity: value-equal but distinct objects -- this is what breaks .index().
        assert earlier_turn == later_turn
        assert earlier_turn is not later_turn

        event = _make_event_stub(
            service="kubevirt-plugin",
            conversation=[earlier_turn, later_turn],
        )
        event.domain = "complicated"

        from src.agents.brain import Brain
        await Brain._enrich_graph_from_agent(brain, event)

        # last_agent resolves to `later_turn` at index 1. The idempotency key must
        # reflect its true position, not index 0 where the value-equal duplicate sits.
        assert (event.id, 1) in brain._enriched_turns
        assert (event.id, 0) not in brain._enriched_turns


@pytest.mark.asyncio
class TestQdrantFallback:
    """T-B8: Qdrant fallback when graph context is None."""

    @patch("src.agents.graph_recall.get_graph_context", new_callable=AsyncMock)
    async def test_recall_still_works_when_graph_empty(self, mock_get_graph_context):
        """T-B8: When graph context is None, existing RECALL behavior unchanged."""
        mock_get_graph_context.return_value = None

        brain = _make_brain_stub()
        brain._post_agent_recall = AsyncMock(
            return_value="## RECALL\n- Lesson 1: Always check logs"
        )

        from src.agents.brain import Brain
        prompt = await Brain._build_system_prompt(
            brain, _make_event_stub(),
            ["always", "post-agent"], context_flags=None,
        )

        assert "prior_knowledge" not in prompt
        assert "RECALL" in prompt
        assert "Always check logs" in prompt
