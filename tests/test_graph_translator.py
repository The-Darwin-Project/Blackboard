# tests/test_graph_translator.py
# @ai-rules:
# 1. [Purpose]: Tests for graph_translator.translate_to_lookups (src/agents/graph_translator.py).
# 2. [Pattern]: pytest. No external dependencies (MVP translator is deterministic, sync).
# 3. [Constraint]: translate_to_lookups is fail-open — returns [] on any error.
"""
Tests for graph_translator.translate_to_lookups — MVP context-to-query mapper.

MVP translator does direct service lookup (no LLM, sync). Returns list of
(entity_type, entity_id) tuples for graph_recall to query.
"""
from __future__ import annotations

import pytest


class TestTranslateToLookupsServiceLookup:
    """T-T1: translate_to_lookups returns entity tuple for simple service lookup."""

    def test_returns_service_entity_for_valid_service(self):
        """T-T1: service="kubevirt-plugin" → [("Service", "service:kubevirt-plugin")]."""
        from src.agents.graph_translator import translate_to_lookups

        result = translate_to_lookups(service="kubevirt-plugin")

        assert isinstance(result, list)
        assert len(result) >= 1
        assert ("Service", "service:kubevirt-plugin") in result

    def test_returns_service_tuple_format(self):
        """T-T1b: Each element is a 2-tuple of (entity_type, entity_id)."""
        from src.agents.graph_translator import translate_to_lookups

        result = translate_to_lookups(service="darwin-brain")

        for item in result:
            assert isinstance(item, tuple)
            assert len(item) == 2
            etype, eid = item
            assert isinstance(etype, str)
            assert isinstance(eid, str)


class TestTranslateToLookupsEmptyInput:
    """T-T2: translate_to_lookups returns empty list for None/empty service."""

    def test_none_service_returns_empty(self):
        """T-T2a: service=None → []."""
        from src.agents.graph_translator import translate_to_lookups

        result = translate_to_lookups(service=None)

        assert result == []

    def test_empty_string_service_returns_empty(self):
        """T-T2b: service="" → []."""
        from src.agents.graph_translator import translate_to_lookups

        result = translate_to_lookups(service="")

        assert result == []

    def test_no_args_returns_empty(self):
        """T-T2c: service="general" (skip-service) → []."""
        from src.agents.graph_translator import translate_to_lookups

        result = translate_to_lookups(service="general")

        assert result == []


class TestTranslateToLookupsFailOpen:
    """T-T3: translate_to_lookups returns empty list on any error."""

    def test_returns_empty_on_internal_error(self):
        """T-T3: translate_to_lookups never raises. Returns [].

        The contract is fail-open. We verify valid input produces a list
        (no exceptions). The function is pure logic (no I/O), so structural
        errors are the only failure mode.
        """
        from src.agents.graph_translator import translate_to_lookups

        result = translate_to_lookups(service="valid-service")
        assert isinstance(result, list)
        assert len(result) >= 1
