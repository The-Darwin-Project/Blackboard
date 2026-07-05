# tests/test_generate_map.py
# @ai-rules:
# 1. [Constraint]: Tests for the phase-tool-map generator. No Redis, no HTTP.
# 2. [Pattern]: Boundary guard uses differential sys.modules check (before/after delta).
# 3. [Pattern]: Failure preservation uses unittest.mock to patch reconcile.py integration path.
"""Tests for phase-tool-map generation from GATE_REGISTRY."""
from __future__ import annotations

import json
import sys
from unittest.mock import MagicMock, patch

import pytest

from src.skill_reconciler.generate_map import (
    CORPUS_KEY,
    _load_gate_registry,
    generate_phase_tool_map,
)


class TestBoundaryGuard:
    """Generator must not leak src.agents imports into the process."""

    def test_no_agent_module_leak(self):
        before = {m for m in sys.modules if m.startswith("src.agents")}
        generate_phase_tool_map()
        after = {m for m in sys.modules if m.startswith("src.agents")}
        leaked = after - before
        assert not leaked, f"generate_phase_tool_map leaked: {leaked}"


class TestContentStructure:
    """Generated skill must have valid structure for BrainSkillLoader."""

    @pytest.fixture(autouse=True)
    def _generate(self):
        self.key, raw = generate_phase_tool_map()
        self.data = json.loads(raw)

    def test_corpus_key(self):
        assert self.key == "always/phase-tool-map.md"

    def test_valid_json_shape(self):
        assert "body" in self.data
        assert "frontmatter" in self.data
        assert "blob_sha" in self.data

    def test_blob_sha_generated(self):
        assert self.data["blob_sha"] == "generated"

    def test_tag_type_navigation(self):
        assert self.data["frontmatter"]["tag_type"] == "navigation"

    def test_frontmatter_tools(self):
        tools = set(self.data["frontmatter"]["tools"])
        expected = {
            "classify_event", "set_phase", "select_agent",
            "close_event", "defer_event", "report_incident",
        }
        assert tools == expected

    def test_body_has_mermaid(self):
        assert "```mermaid" in self.data["body"]

    def test_all_gate_ids_present(self):
        """Every gate_id from GATE_REGISTRY must appear in the generated body."""
        registry, _ = _load_gate_registry()
        body = self.data["body"]
        for gate in registry:
            assert gate.gate_id in body, f"Gate {gate.gate_id} missing from body"

    def test_gate_row_count_matches_registry(self):
        """Table data rows must equal GATE_REGISTRY length."""
        registry, _ = _load_gate_registry()
        body = self.data["body"]
        rows = [
            line for line in body.split("\n")
            if line.startswith("| ") and ("| strip |" in line or "| allow |" in line)
        ]
        assert len(rows) == len(registry)

    def test_pre_classification_annotation(self):
        """PRE_CLASSIFICATION row must annotate chat/slack-only wait_for_user."""
        body = self.data["body"]
        for line in body.split("\n"):
            if "PRE_CLASSIFICATION" in line and "| allow |" in line:
                assert "`wait_for_user`" in line and "(chat/slack only)" in line
                return
        pytest.fail("PRE_CLASSIFICATION allow row not found")


class TestIdempotency:
    """Consecutive calls must produce identical output."""

    def test_two_calls_identical(self):
        k1, v1 = generate_phase_tool_map()
        k2, v2 = generate_phase_tool_map()
        assert k1 == k2
        assert v1 == v2


class TestFailurePreservation:
    """When generator fails, reconciler preserves existing Redis value."""

    @patch(
        "src.skill_reconciler.reconcile.generate_phase_tool_map",
        side_effect=RuntimeError("boom"),
    )
    @patch("src.skill_reconciler.reconcile._fetch_tree", return_value=[])
    @patch("src.skill_reconciler.reconcile._fetch_commit_sha", return_value="newsha1")
    def test_fallback_reads_and_preserves(self, _sha, _tree, _gen):
        from src.skill_reconciler.constants import REDIS_KEY_CORPUS
        from src.skill_reconciler.reconcile import _reconcile

        preserved = json.dumps(
            {"body": "old content", "frontmatter": {"tag_type": "navigation"}, "blob_sha": "prev"}
        )
        mock_rdb = MagicMock()
        mock_rdb.hget.return_value = preserved

        def hkeys_side(key):
            return ["always/phase-tool-map.md"] if key == REDIS_KEY_CORPUS else []

        mock_rdb.hkeys.side_effect = hkeys_side
        mock_pipe = MagicMock()
        mock_rdb.pipeline.return_value = mock_pipe

        _reconcile(mock_rdb, MagicMock(), None)

        mock_rdb.hget.assert_called_once_with(REDIS_KEY_CORPUS, "always/phase-tool-map.md")

        corpus_calls = [
            c for c in mock_pipe.hset.call_args_list
            if c.args and c.args[0] == REDIS_KEY_CORPUS
        ]
        assert len(corpus_calls) == 1
        written = corpus_calls[0].kwargs.get("mapping", {})
        assert written.get("always/phase-tool-map.md") == preserved

    @patch(
        "src.skill_reconciler.reconcile.generate_phase_tool_map",
        side_effect=RuntimeError("boom"),
    )
    @patch("src.skill_reconciler.reconcile._fetch_tree", return_value=[])
    @patch("src.skill_reconciler.reconcile._fetch_commit_sha", return_value="newsha2")
    def test_no_existing_value_graceful(self, _sha, _tree, _gen):
        """When no previous Redis value exists, corpus stays empty for that key."""
        from src.skill_reconciler.constants import REDIS_KEY_CORPUS
        from src.skill_reconciler.reconcile import _reconcile

        mock_rdb = MagicMock()
        mock_rdb.hget.return_value = None
        mock_rdb.hkeys.return_value = []
        mock_pipe = MagicMock()
        mock_rdb.pipeline.return_value = mock_pipe

        _reconcile(mock_rdb, MagicMock(), None)

        corpus_calls = [
            c for c in mock_pipe.hset.call_args_list
            if c.args and c.args[0] == REDIS_KEY_CORPUS
        ]
        assert len(corpus_calls) == 0
