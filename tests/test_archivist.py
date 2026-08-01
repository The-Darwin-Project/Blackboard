# tests/test_archivist.py
# @ai-rules:
# 1. [Constraint]: No Qdrant, no real GenAI clients -- Archivist.__new__() + mocked
#    adapter/vector_store (mirrors test_deep_memory_rerank.py's _make_archivist pattern).
# 2. [Pattern]: Exercises _archive_event_fallback (Gemini path) rather than archive_event
#    (Claude tool-call path) -- fewer mocks needed for the same payload-shape assertion.
# 3. [Gotcha]: Not part of the plan's 22-row Test Specification Table (T-1..T-20, T-18b,
#    T-19b) -- supplementary coverage for Step 11's own verify criterion ("Archivist unit
#    test confirms payload includes the new fields"). incident_references/terminal_reason
#    are not yet written into the summary payload at authoring time; these tests target
#    the plan's described behavior and may need adjustment once Step 11 lands (exact
#    terminal_reason derivation -- likely the last close turn's `evidence` field, per the
#    same convention Step 11 specifies for the Cortex UI's client-side derivation).
"""Tests for Archivist's incident_references/terminal_reason archive payload
extension (GitHub #155/#156, plan Step 11)."""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.models import ConversationTurn, EventDocument, EventEvidence, EventInput


def _make_archivist(**overrides):
    """Create an Archivist via __new__ with only the attrs _archive_event_fallback
    touches (mirrors test_deep_memory_rerank.py's _make_archivist helper)."""
    from src.agents.archivist import Archivist

    a = Archivist.__new__(Archivist)
    a._initialized = True
    a._knowledge_ready = False
    a.pulse_port = None
    a.project = "test-project"
    a.location = "global"
    a._vector_store = overrides.get("vector_store", AsyncMock())
    a._client = overrides.get("client", None)
    a._adapter = overrides.get("adapter", None)
    a._claude_adapter = overrides.get("claude_adapter", None)
    a._rank_client = None
    a._ranker_model = ""
    a._ranker_location = "global"
    a._ranker_config = "default_ranking_config"
    a._rank_consecutive_failures = 0
    a._rank_circuit_open_until = 0.0
    return a


def _make_closed_event(incident_references=None, close_evidence="non_transient_confirmed"):
    evidence = EventEvidence(display_text="test", source_type="aligner", severity="info")
    return EventDocument(
        id="evt-archive-1",
        source="aligner",
        service="test-svc",
        event=EventInput(reason="anomaly", evidence=evidence),
        incident_references=incident_references,
        conversation=[
            ConversationTurn(turn=1, actor="brain", action="triage", thoughts="classified"),
            ConversationTurn(turn=2, actor="brain", action="close", thoughts="closed", evidence=close_evidence),
        ],
    )


def _wire_fallback_adapter(archivist, symptom="s", root_cause="rc", fix_action="fa"):
    archivist._embed = AsyncMock(return_value=[0.0] * 768)
    adapter = AsyncMock()
    response = MagicMock()
    response.text = json.dumps({"symptom": symptom, "root_cause": root_cause, "fix_action": fix_action})
    response.usage = MagicMock()
    adapter.generate = AsyncMock(return_value=response)
    archivist._get_adapter = AsyncMock(return_value=adapter)
    return archivist


class TestArchivePayloadIncludesIncidentReferencesAndTerminalReason:
    """Step 11 verify criterion: the Gemini-fallback archival payload written
    to Qdrant includes incident_references and the closing terminal_reason."""

    @pytest.mark.asyncio
    async def test_fallback_payload_includes_both_new_fields(self):
        archivist = _wire_fallback_adapter(_make_archivist())
        event = _make_closed_event(
            incident_references=["VMER-1234"], close_evidence="non_transient_confirmed",
        )

        await archivist._archive_event_fallback(event, "conversation text", 120)

        assert archivist._vector_store.upsert.await_count == 1
        _, kwargs = archivist._vector_store.upsert.call_args
        payload = kwargs["payload"]
        assert payload.get("incident_references") == ["VMER-1234"]
        assert payload.get("terminal_reason") == "non_transient_confirmed"

    @pytest.mark.asyncio
    async def test_fallback_payload_omits_incident_references_cleanly_when_absent(self):
        archivist = _wire_fallback_adapter(_make_archivist())
        event = _make_closed_event(incident_references=None, close_evidence="resolved")

        await archivist._archive_event_fallback(event, "conversation text", 60)

        _, kwargs = archivist._vector_store.upsert.call_args
        payload = kwargs["payload"]
        assert not payload.get("incident_references")
        assert payload.get("terminal_reason") == "resolved"
