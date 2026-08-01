# tests/test_lesson_hygiene.py
# @ai-rules:
# 1. [Purpose]: Validates lesson tool-name hygiene — no Brain tool identifiers leak into Qdrant lessons or RECALL SI.
# 2. [Pattern]: Tests written from plan spec, independent of implementation. Two tiers: mapped→behavior, unmapped→stripped.
# 3. [Constraint]: Do NOT import from implementation until executor creates it. Tests expected to fail until reconciliation.
# 4. [Gotcha]: _sanitize_lesson_text is a module-level function, not a method. _strip_tool_names is in brain.py (separate module).
"""
Lesson tool-name hygiene tests.

Validates the 4-layer defense:
  Layer 3: _sanitize_lesson_text in archivist.py (Tier 1 mapping + Tier 2 strip)
  Layer 4: _strip_tool_names in brain.py (defense-in-depth before SI injection)

T-1 through T-10 from plan spec table.
"""
from __future__ import annotations

from unittest.mock import AsyncMock

import pytest


# ---------------------------------------------------------------------------
# Layer 3 — archivist._sanitize_lesson_text
# ---------------------------------------------------------------------------

class TestSanitizeLessonText:
    """Tier 1 (mapped replacement) and Tier 2 (unmapped strip) sanitizer."""

    @pytest.fixture(autouse=True)
    def _import_sanitizer(self):
        from src.agents.archivist import _sanitize_lesson_text, _TOOL_TO_BEHAVIOR
        self.sanitize = _sanitize_lesson_text
        self.mapping = _TOOL_TO_BEHAVIOR

    # T-1: single mapped tool name replaced with behavioral equivalent
    def test_single_mapped_tool_replaced(self):
        result = self.sanitize("Use record_observation to track")
        assert "record_observation" not in result
        assert "recording a metric" in result

    # T-2: multiple tool names in one string
    def test_multiple_tool_names_replaced(self):
        result = self.sanitize("Call defer_event then wait_for_user")
        assert "defer_event" not in result
        assert "wait_for_user" not in result
        assert "parking with a timer" in result
        assert "parking for human response" in result

    # T-3: text without tool names passes through unchanged
    def test_no_tool_names_unchanged(self):
        text = "Classify the domain first"
        result = self.sanitize(text)
        assert result == text

    # T-6: keyword list — each keyword sanitized individually
    def test_keywords_sanitized(self):
        keywords = ["defer_event", "flow"]
        sanitized = [self.sanitize(kw) for kw in keywords]
        assert "defer_event" not in sanitized[0]
        assert "parking with a timer" in sanitized[0]
        assert sanitized[1] == "flow"

    # T-8: title field sanitized
    def test_title_sanitized(self):
        result = self.sanitize("Repeated classify_event Calls")
        assert "classify_event" not in result
        assert "classifying the domain" in result

    # T-9a: mapped tool in mapping gets behavioral replacement
    def test_mapped_tool_gets_behavioral_replacement(self):
        result = self.sanitize("use inspect_event here")
        assert "inspect_event" not in result
        assert "inspecting event state" in result

    # T-9b: truly unmapped tool gets stripped via fallback tier
    def test_unmapped_tool_stripped_fallback(self):
        """A tool name in _ALL_TOOL_NAMES but NOT in _TOOL_TO_BEHAVIOR gets stripped."""
        from src.agents.archivist import _ALL_TOOL_NAMES

        unmapped = None
        for name in _ALL_TOOL_NAMES:
            if name not in self.mapping:
                unmapped = name
                break

        if unmapped is None:
            pytest.skip("All tool names are mapped — no fallback tier to test")

        result = self.sanitize(f"use {unmapped} here")
        assert unmapped not in result

    # Tier 1 must use word-boundary matching (no partial match on substrings)
    def test_word_boundary_no_partial_match(self):
        result = self.sanitize("observation is a plain word, not a tool name")
        assert result == "observation is a plain word, not a tool name"

    def test_empty_string(self):
        assert self.sanitize("") == ""


# ---------------------------------------------------------------------------
# Layer 4 — brain._strip_tool_names (defense-in-depth)
# ---------------------------------------------------------------------------

class TestStripToolNames:
    """Defense-in-depth filter applied in _format_recall_block and _post_agent_recall."""

    @pytest.fixture(autouse=True)
    def _import_strip(self):
        from src.agents.brain import _strip_tool_names
        self.strip = _strip_tool_names

    # T-5: strips surviving tool name from text
    def test_strip_known_tool_name(self):
        result = self.strip("use classify_event")
        assert "classify_event" not in result

    def test_strip_multiple_tool_names(self):
        result = self.strip("call record_observation then defer_event")
        assert "record_observation" not in result
        assert "defer_event" not in result

    def test_no_tool_names_unchanged(self):
        text = "normal behavioral description"
        result = self.strip(text)
        assert result == text

    # T-7: recall block formatted from _post_agent_recall would be clean
    def test_recall_block_format_cleaned(self):
        """Simulates the pattern text that _post_agent_recall formats into SI."""
        raw_lesson = "- Repeated record_observation Spirals: Use record_observation sparingly"
        result = self.strip(raw_lesson)
        assert "record_observation" not in result

    def test_title_in_recall_block_cleaned(self):
        """Title field also gets stripped (e.g. 'Repeated classify_event Calls')."""
        raw = "classify_event loop detected"
        result = self.strip(raw)
        assert "classify_event" not in result


# ---------------------------------------------------------------------------
# T-4 — Integration: store_lesson sanitizes before Qdrant upsert
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestStoreLessonSanitization:
    """Verify store_lesson applies _sanitize_lesson_text before Qdrant upsert."""

    async def test_pattern_sanitized_before_upsert(self):
        from src.agents.archivist import Archivist

        archivist = Archivist.__new__(Archivist)
        archivist._initialized = True
        archivist._knowledge_ready = False
        archivist.pulse_port = None

        mock_vs = AsyncMock()
        mock_vs.search.return_value = []  # no dedup match
        mock_vs.upsert.return_value = None
        archivist._vector_store = mock_vs

        fake_vector = [0.1] * 768
        archivist._embed = AsyncMock(return_value=fake_vector)

        await archivist.store_lesson(
            title="Observation Spirals",
            pattern="Use record_observation sparingly to avoid loops",
            anti_pattern="Calling defer_event in a tight loop",
            fix_action="Switch to wait_for_user instead",
            keywords=["record_observation", "spiral"],
        )

        mock_vs.upsert.assert_called_once()
        call_args = mock_vs.upsert.call_args
        collection = call_args.kwargs.get("collection")
        payload = call_args.kwargs.get("payload")

        assert collection == "darwin_lessons"
        assert payload is not None

        assert "record_observation" not in payload["pattern"]
        assert "recording a metric" in payload["pattern"]
        assert "defer_event" not in payload["anti_pattern"]
        assert "wait_for_user" not in payload["fix_action"]
        assert "record_observation" not in payload["keywords"]


# ---------------------------------------------------------------------------
# T-10 — Coverage: mapping + fallback covers ALL BRAIN_TOOL_SCHEMAS names
# ---------------------------------------------------------------------------

class TestToolNameCoverage:
    """Every tool in BRAIN_TOOL_SCHEMAS must be handled (mapped or fallback-stripped)."""

    def test_all_brain_tools_covered(self):
        from src.agents.archivist import _TOOL_TO_BEHAVIOR, _ALL_TOOL_NAMES
        from src.agents.llm.types import BRAIN_TOOL_SCHEMAS

        schema_names = {t["name"] for t in BRAIN_TOOL_SCHEMAS}

        # _ALL_TOOL_NAMES must be a superset of BRAIN_TOOL_SCHEMAS names
        missing = schema_names - _ALL_TOOL_NAMES
        assert not missing, (
            f"BRAIN_TOOL_SCHEMAS names not in _ALL_TOOL_NAMES: {missing}. "
            f"Add them to ensure Tier 2 fallback covers all tools."
        )

    def test_mapping_keys_are_valid_tool_names(self):
        """Every key in _TOOL_TO_BEHAVIOR must be a real BRAIN_TOOL_SCHEMAS name."""
        from src.agents.archivist import _TOOL_TO_BEHAVIOR
        from src.agents.llm.types import BRAIN_TOOL_SCHEMAS

        schema_names = {t["name"] for t in BRAIN_TOOL_SCHEMAS}
        phantom = set(_TOOL_TO_BEHAVIOR.keys()) - schema_names
        assert not phantom, (
            f"_TOOL_TO_BEHAVIOR has keys not in BRAIN_TOOL_SCHEMAS: {phantom}. "
            f"Remove or rename these entries (likely misspelled)."
        )

    def test_mapping_values_are_behavioral_not_tool_names(self):
        """Behavioral descriptions must not themselves contain tool names."""
        from src.agents.archivist import _TOOL_TO_BEHAVIOR, _ALL_TOOL_NAMES

        for tool_name, behavior in _TOOL_TO_BEHAVIOR.items():
            for name in _ALL_TOOL_NAMES:
                assert name not in behavior, (
                    f"_TOOL_TO_BEHAVIOR['{tool_name}'] value '{behavior}' "
                    f"contains tool name '{name}' — must be behavioral only."
                )
