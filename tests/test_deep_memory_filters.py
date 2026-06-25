# BlackBoard/tests/test_deep_memory_filters.py
# @ai-rules:
# 1. [Constraint]: Tests _safe_int, filter construction, dedup markers, and archivist passthrough.
# 2. [Pattern]: Uses pytest + pytest-asyncio. Mocks VectorStore for passthrough verification.
# 3. [Gotcha]: _safe_int must reject bool values (True/False are technically int subclass in Python).
"""
Tests for deep memory temporal/structured filtering feature.
Covers: _safe_int validation, filter construction logic, dedup marker format,
and Archivist.search filter passthrough to VectorStore.
"""
from __future__ import annotations

import time
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio

from src.agents.handler_utils import _safe_int


class TestSafeInt:
    """_safe_int must handle arbitrary LLM outputs gracefully."""

    def test_valid_integer(self):
        assert _safe_int(24) == 24

    def test_string_integer(self):
        assert _safe_int("60") == 60

    def test_float_truncates(self):
        assert _safe_int(60.5) == 60

    def test_float_string_rejects(self):
        assert _safe_int("60.5") is None

    def test_string_with_text(self):
        assert _safe_int("24 hours") is None

    def test_non_numeric_string(self):
        assert _safe_int("all") is None

    def test_empty_string(self):
        assert _safe_int("") is None

    def test_none(self):
        assert _safe_int(None) is None

    def test_zero_rejects(self):
        assert _safe_int(0) is None

    def test_negative_rejects(self):
        assert _safe_int(-5) is None

    def test_bool_true_rejects(self):
        assert _safe_int(True) is None

    def test_bool_false_rejects(self):
        assert _safe_int(False) is None

    def test_overflow_rejects(self):
        assert _safe_int(float("inf")) is None

    def test_default_returned(self):
        assert _safe_int(None, default=10) == 10
        assert _safe_int("bad", default=5) == 5


class TestFilterConstruction:
    """Filter dict construction from LLM args mirrors brain.py handler logic."""

    def _build_filter(self, time_range=None, min_dur=None, svc=None):
        """Replicates brain.py filter construction logic for isolated testing."""
        conditions: list[dict] = []
        if time_range:
            cutoff = time.time() - (time_range * 3600)
            conditions.append({"key": "closed_at", "range": {"gte": cutoff}})
        if min_dur:
            conditions.append({"key": "duration_seconds", "range": {"gte": min_dur * 60}})
        if svc:
            conditions.append({"key": "service", "match": {"value": svc}})
        return {"must": conditions} if conditions else None

    def test_no_filters_returns_none(self):
        assert self._build_filter() is None

    def test_time_range_only(self):
        frozen = 1750000000.0
        with patch("time.time", return_value=frozen):
            f = self._build_filter(time_range=24)
        assert f is not None
        assert len(f["must"]) == 1
        cond = f["must"][0]
        assert cond["key"] == "closed_at"
        assert cond["range"]["gte"] == frozen - (24 * 3600)

    def test_duration_only(self):
        f = self._build_filter(min_dur=30)
        assert f == {"must": [{"key": "duration_seconds", "range": {"gte": 1800}}]}

    def test_service_only(self):
        f = self._build_filter(svc="darwin-store")
        assert f == {"must": [{"key": "service", "match": {"value": "darwin-store"}}]}

    def test_all_filters_combined(self):
        f = self._build_filter(time_range=48, min_dur=60, svc="headhunter")
        assert f is not None
        assert len(f["must"]) == 3
        keys = [c["key"] for c in f["must"]]
        assert keys == ["closed_at", "duration_seconds", "service"]


class TestDedupMarker:
    """Dedup markers must distinguish different filter combinations."""

    def _build_marker(self, query, time_range=None, min_dur=None, svc=None):
        """Replicates brain.py dedup marker logic."""
        safe_query = query.replace('"', '\\"')
        filter_parts: list[str] = []
        if time_range:
            filter_parts.append(f"time={time_range}h")
        if min_dur:
            filter_parts.append(f"dur>={min_dur}m")
        if svc:
            filter_parts.append(f"svc={svc}")
        filter_tag = f" [{','.join(filter_parts)}]" if filter_parts else " [unfiltered]"
        return f'Deep Memory: "{safe_query}"{filter_tag}'

    def test_unfiltered_marker(self):
        m = self._build_marker("high cpu")
        assert m == 'Deep Memory: "high cpu" [unfiltered]'

    def test_time_filtered_marker(self):
        m = self._build_marker("pipeline failures", time_range=24)
        assert m == 'Deep Memory: "pipeline failures" [time=24h]'

    def test_full_filter_marker(self):
        m = self._build_marker("q", time_range=24, min_dur=30, svc="darwin")
        assert m == 'Deep Memory: "q" [time=24h,dur>=30m,svc=darwin]'

    def test_no_substring_collision(self):
        """Different filter combos must not match each other's markers."""
        m1 = self._build_marker("q", time_range=24)
        m2 = self._build_marker("q")
        assert m1 != m2
        assert m1 not in m2
        assert m2 not in m1

    def test_quotes_escaped(self):
        m = self._build_marker('query with "quotes"')
        assert '\\"' in m

    def test_marker_appears_in_evidence_header(self):
        """Dedup relies on marker being a substring of stored evidence.
        The evidence header must include the filter tag for dedup to work."""
        marker = self._build_marker("q")
        evidence_header = f'# Deep Memory: "q" [unfiltered]\n'
        assert marker in evidence_header

        marker_filtered = self._build_marker("q", time_range=24)
        evidence_filtered = f'# Deep Memory: "q" [time=24h]\n'
        assert marker_filtered in evidence_filtered


@pytest.mark.asyncio
class TestArchivistFilterPassthrough:
    """Verify Archivist.search passes filter kwarg to VectorStore.search."""

    async def test_filter_reaches_vector_store(self):
        from src.agents.archivist import Archivist

        archivist = Archivist.__new__(Archivist)
        archivist._initialized = True
        archivist._knowledge_ready = False
        archivist.pulse_port = None

        mock_vs = AsyncMock()
        mock_vs.search.return_value = [
            {"id": "1", "score": 0.9, "payload": {"symptom": "test"}}
        ]
        archivist._vector_store = mock_vs

        test_filter = {"must": [{"key": "service", "match": {"value": "foo"}}]}
        fake_vector = [0.1] * 768

        results = await archivist.search("test query", vector=fake_vector, filter=test_filter)

        mock_vs.search.assert_called_once()
        call_kwargs = mock_vs.search.call_args
        assert call_kwargs.kwargs.get("filter") == test_filter or call_kwargs[1].get("filter") == test_filter
        assert len(results) == 1

    async def test_none_filter_passes_through(self):
        from src.agents.archivist import Archivist

        archivist = Archivist.__new__(Archivist)
        archivist._initialized = True
        archivist._knowledge_ready = False
        archivist.pulse_port = None

        mock_vs = AsyncMock()
        mock_vs.search.return_value = []
        archivist._vector_store = mock_vs

        fake_vector = [0.1] * 768
        await archivist.search("test", vector=fake_vector, filter=None)

        call_kwargs = mock_vs.search.call_args
        passed_filter = call_kwargs.kwargs.get("filter") if call_kwargs.kwargs else call_kwargs[1].get("filter")
        assert passed_filter is None
