# BlackBoard/tests/test_deep_memory_rerank.py
# @ai-rules:
# 1. [Constraint]: Tests Archivist.rerank() and handle_consult_deep_memory reranking integration.
# 2. [Pattern]: Uses pytest + pytest-asyncio. Mocks RankServiceAsyncClient for API isolation.
# 3. [Gotcha]: Archivist.__new__() bypasses __init__; set all required attrs manually.
# 4. [Pattern]: Tests written against plan spec (T-1 through T-5, T-17, T-18). Implementation in parallel.
"""
Tests for Vertex Reranking integration in deep memory.

Spec IDs: T-1 (reorder), T-2 (fallback), T-3 (disabled gate),
T-4 (per-source text extraction), T-5 (concurrent gather),
T-17 (count mismatch), T-18 (cold-start).
"""
from __future__ import annotations

import asyncio
import logging
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_archivist(**overrides):
    """Create an Archivist via __new__ with rerank-relevant attrs."""
    from src.agents.archivist import Archivist

    a = Archivist.__new__(Archivist)
    a._initialized = True
    a._knowledge_ready = False
    a.pulse_port = None
    a.project = "test-project"
    a.location = "global"
    a._rank_client = overrides.get("rank_client", None)
    a._ranker_model = overrides.get("ranker_model", "semantic-ranker-default@latest")
    a._ranker_location = overrides.get("ranker_location", "global")
    a._ranker_config = overrides.get("ranker_config", "default_ranking_config")
    a._rank_consecutive_failures = overrides.get("rank_consecutive_failures", 0)
    a._rank_circuit_open_until = overrides.get("rank_circuit_open_until", 0.0)
    a._vector_store = overrides.get("vector_store", AsyncMock())
    # Fix ranking_config_path to be synchronous (it's a classmethod/staticmethod on real client)
    if a._rank_client is not None and hasattr(a._rank_client, 'ranking_config_path'):
        a._rank_client.ranking_config_path = MagicMock(
            return_value="projects/test-project/locations/global/rankingConfigs/default_ranking_config"
        )
    return a


def _make_ranking_response(records_in_order: list[str]):
    """Build a mock RankResponse with records in the given id order."""
    rec = MagicMock()
    recs = []
    for rid in records_in_order:
        r = MagicMock()
        r.id = rid
        recs.append(r)
    rec.records = recs
    return rec


def _knowledge_results():
    return [
        {"id": "k1", "score": 0.8, "payload": {"fact": "Redis uses port 6379"}},
        {"id": "k2", "score": 0.7, "payload": {"fact": "Brain polls every 5s"}},
        {"id": "k3", "score": 0.6, "payload": {"fact": "Archivist embeds at 768d"}},
    ]


def _lessons_results():
    return [
        {"id": "l1", "score": 0.9, "payload": {"title": "Pipeline timeout", "pattern": "Retry after 5min"}},
        {"id": "l2", "score": 0.7, "payload": {"title": "OOM kills", "pattern": "Bump memory limit"}},
    ]


def _events_results():
    return [
        {"id": "e1", "score": 0.85, "payload": {"symptom": "Pod CrashLoop", "root_cause": "Missing secret", "fix_action": "Created secret"}},
        {"id": "e2", "score": 0.6, "payload": {"symptom": "Build failure", "root_cause": "Flaky test", "fix_action": "Retested"}},
    ]


# ===========================================================================
# T-1: Reranking reorders per-collection results
# ===========================================================================
@pytest.mark.asyncio
class TestRerankReorders:
    async def test_knowledge_reordered_by_api_relevance(self):
        """T-1: Results reordered by API relevance score, original dicts preserved via id-correlation."""
        mock_client = AsyncMock()
        mock_client.ranking_config_path.return_value = "projects/test/locations/global/rankingConfigs/default"
        mock_client.rank.return_value = _make_ranking_response(["2", "0", "1"])

        archivist = _make_archivist(rank_client=mock_client)
        original = _knowledge_results()

        reranked = await archivist.rerank("redis configuration", original, "knowledge")

        assert len(reranked) == 3
        assert reranked[0] is original[2], "API ranked id=2 first → third original result"
        assert reranked[1] is original[0], "API ranked id=0 second → first original result"
        assert reranked[2] is original[1], "API ranked id=1 third → second original result"

    async def test_lessons_reordered(self):
        """T-1: Lessons collection also reordered correctly."""
        mock_client = AsyncMock()
        mock_client.ranking_config_path.return_value = "projects/test/locations/global/rankingConfigs/default"
        mock_client.rank.return_value = _make_ranking_response(["1", "0"])

        archivist = _make_archivist(rank_client=mock_client)
        original = _lessons_results()

        reranked = await archivist.rerank("memory issues", original, "lessons")

        assert len(reranked) == 2
        assert reranked[0] is original[1]
        assert reranked[1] is original[0]


# ===========================================================================
# T-2: Reranking graceful fallback on API error/timeout
# ===========================================================================
@pytest.mark.asyncio
class TestRerankFallback:
    async def test_fallback_on_api_error(self):
        """T-2: API error → original order preserved, warning logged."""
        mock_client = AsyncMock()
        mock_client.ranking_config_path.return_value = "projects/test/locations/global/rankingConfigs/default"
        mock_client.rank.side_effect = Exception("500 Internal Server Error")

        archivist = _make_archivist(rank_client=mock_client)
        original = _knowledge_results()

        with patch("src.agents.archivist.logger") as mock_logger:
            result = await archivist.rerank("test query", original, "knowledge")

        assert result is original, "Must return original list on error"
        mock_logger.warning.assert_called()

    async def test_fallback_on_timeout(self):
        """T-2: Timeout → original order preserved, no exception raised."""
        mock_client = AsyncMock()
        mock_client.ranking_config_path.return_value = "projects/test/locations/global/rankingConfigs/default"

        async def slow_rank(*args, **kwargs):
            await asyncio.sleep(10)

        mock_client.rank.side_effect = slow_rank

        archivist = _make_archivist(rank_client=mock_client)
        original = _events_results()

        result = await archivist.rerank("timeout test", original, "events")

        assert result is original, "Must return original on timeout"

    async def test_fallback_on_init_failure(self):
        """T-2: _ensure_rank_client fails → original order, warning logged."""
        archivist = _make_archivist(rank_client=None)

        with patch.object(archivist, "_ensure_rank_client", side_effect=Exception("DNS resolution failed")):
            with patch("src.agents.archivist.logger") as mock_logger:
                result = await archivist.rerank("test", _knowledge_results(), "knowledge")

        assert len(result) == 3
        mock_logger.warning.assert_called()

    async def test_empty_results_returns_unchanged(self):
        """T-2 edge: Empty input returns empty without calling API."""
        mock_client = AsyncMock()
        archivist = _make_archivist(rank_client=mock_client)

        result = await archivist.rerank("test", [], "knowledge")

        assert result == []
        mock_client.rank.assert_not_called()


# ===========================================================================
# T-3: Reranking disabled when env var empty
# ===========================================================================
@pytest.mark.asyncio
class TestRerankDisabledGate:
    async def test_disabled_when_model_empty(self):
        """T-3: VERTEX_RANKER_MODEL='' → no rerank call, original flow."""
        mock_client = AsyncMock()
        archivist = _make_archivist(rank_client=mock_client, ranker_model="")
        original = _knowledge_results()

        result = await archivist.rerank("test", original, "knowledge")

        assert result is original, "Must return original when ranker model is empty"
        mock_client.rank.assert_not_called()


# ===========================================================================
# T-4: Per-source text extraction correctness
# ===========================================================================
@pytest.mark.asyncio
class TestPerSourceTextExtraction:
    async def test_knowledge_extracts_fact(self):
        """T-4: Knowledge source extracts 'fact' field from payload."""
        mock_client = AsyncMock()
        mock_client.ranking_config_path.return_value = "projects/test/locations/global/rankingConfigs/default"
        mock_client.rank.return_value = _make_ranking_response(["0"])

        archivist = _make_archivist(rank_client=mock_client)
        results = [{"id": "k1", "score": 0.8, "payload": {"fact": "Redis cluster mode"}}]

        await archivist.rerank("redis", results, "knowledge")

        call_args = mock_client.rank.call_args
        rank_request = call_args[0][0] if call_args[0] else call_args.kwargs.get("request", call_args[0][0])
        records = rank_request.records if hasattr(rank_request, "records") else []
        assert any("Redis cluster mode" in (r.content or "") for r in records)

    async def test_lessons_extracts_title_and_pattern(self):
        """T-4: Lessons source extracts 'title' + 'pattern' fields."""
        mock_client = AsyncMock()
        mock_client.ranking_config_path.return_value = "projects/test/locations/global/rankingConfigs/default"
        mock_client.rank.return_value = _make_ranking_response(["0"])

        archivist = _make_archivist(rank_client=mock_client)
        results = [{"id": "l1", "score": 0.9, "payload": {"title": "OOM", "pattern": "Bump limits"}}]

        await archivist.rerank("memory", results, "lessons")

        call_args = mock_client.rank.call_args
        rank_request = call_args[0][0] if call_args[0] else call_args.kwargs.get("request", call_args[0][0])
        records = rank_request.records if hasattr(rank_request, "records") else []
        assert any("OOM" in (r.content or "") and "Bump limits" in (r.content or "") for r in records)

    async def test_events_extracts_symptom_root_cause_fix(self):
        """T-4: Events source extracts 'symptom' + 'root_cause' + 'fix_action'."""
        mock_client = AsyncMock()
        mock_client.ranking_config_path.return_value = "projects/test/locations/global/rankingConfigs/default"
        mock_client.rank.return_value = _make_ranking_response(["0"])

        archivist = _make_archivist(rank_client=mock_client)
        results = [{"id": "e1", "score": 0.85, "payload": {
            "symptom": "CrashLoop", "root_cause": "Missing secret", "fix_action": "Created secret",
        }}]

        await archivist.rerank("crash", results, "events")

        call_args = mock_client.rank.call_args
        rank_request = call_args[0][0] if call_args[0] else call_args.kwargs.get("request", call_args[0][0])
        records = rank_request.records if hasattr(rank_request, "records") else []
        content = records[0].content if records else ""
        assert "CrashLoop" in content
        assert "Missing secret" in content
        assert "Created secret" in content

    async def test_null_payload_handled(self):
        """T-4 edge: Explicit None payload → empty string extraction, no crash."""
        mock_client = AsyncMock()
        mock_client.ranking_config_path.return_value = "projects/test/locations/global/rankingConfigs/default"
        mock_client.rank.return_value = _make_ranking_response(["0"])

        archivist = _make_archivist(rank_client=mock_client)
        results = [{"id": "x1", "score": 0.5, "payload": None}]

        result = await archivist.rerank("test", results, "knowledge")
        assert len(result) == 1


# ===========================================================================
# T-5: Concurrent reranking via gather
# ===========================================================================
@pytest.mark.asyncio
class TestConcurrentReranking:
    async def test_three_collections_reranked_concurrently_via_real_handler(self):
        """T-5 (codereview fix): the prior version of this test monkeypatched
        archivist.rerank and called asyncio.gather() directly in the test body --
        it proved Python's gather semantics, not the production integration. This
        version drives the REAL handle_consult_deep_memory() -> real Archivist.rerank()
        x3 gather call site, with an artificial per-call delay on the mocked Ranking
        API, and asserts wall-clock time proves concurrent (not sequential) execution."""
        from src.agents.handlers_lookup import handle_consult_deep_memory

        mock_client = AsyncMock()
        mock_client.ranking_config_path.return_value = "projects/test/locations/global/rankingConfigs/default"

        async def slow_rank(request):
            await asyncio.sleep(0.05)
            ids = [r.id for r in request.records]
            return _make_ranking_response(ids)

        mock_client.rank.side_effect = slow_rank
        archivist = _make_archivist(rank_client=mock_client, ranker_model="semantic-ranker-default@latest")
        archivist.embed_query = AsyncMock(return_value=None)
        archivist.search_knowledge = AsyncMock(return_value=_knowledge_results())
        archivist.search_lessons = AsyncMock(return_value=_lessons_results())
        archivist.search = AsyncMock(return_value=_events_results())

        ctx = _make_tool_ctx(_make_event_stub(), archivist)

        start = time.monotonic()
        result = await handle_consult_deep_memory(ctx, "evt-1", {"query": "test"}, None)
        elapsed = time.monotonic() - start

        assert result is True
        assert mock_client.rank.call_count == 3
        assert elapsed < 0.15, (
            f"3 collections x 50ms each must run concurrently via gather (~50ms total), "
            f"took {elapsed:.3f}s -- sequential execution would take ~150ms"
        )


# ===========================================================================
# T-17: Rerank count mismatch reconciliation
# ===========================================================================
@pytest.mark.asyncio
class TestRerankCountMismatch:
    async def test_missing_entries_appended(self):
        """T-17: API returns fewer records → missing appended in original order."""
        mock_client = AsyncMock()
        mock_client.ranking_config_path.return_value = "projects/test/locations/global/rankingConfigs/default"
        mock_client.rank.return_value = _make_ranking_response(["2", "0"])

        archivist = _make_archivist(rank_client=mock_client)
        original = _knowledge_results()

        with patch("src.agents.archivist.logger") as mock_logger:
            result = await archivist.rerank("test", original, "knowledge")

        assert len(result) == 3, "All original results must be preserved"
        assert result[0] is original[2], "API-ranked first"
        assert result[1] is original[0], "API-ranked second"
        assert result[2] is original[1], "Missing id=1 appended from original"
        mock_logger.warning.assert_called()

    async def test_empty_api_response_returns_all_original(self):
        """T-17 edge: API returns 0 records → all original appended."""
        mock_client = AsyncMock()
        mock_client.ranking_config_path.return_value = "projects/test/locations/global/rankingConfigs/default"
        mock_client.rank.return_value = _make_ranking_response([])

        archivist = _make_archivist(rank_client=mock_client)
        original = _lessons_results()

        with patch("src.agents.archivist.logger") as mock_logger:
            result = await archivist.rerank("test", original, "lessons")

        assert len(result) == len(original)
        mock_logger.warning.assert_called()


# ===========================================================================
# Codereview fix: duplicate-id defense in id-correlation reconstruction
# ===========================================================================
@pytest.mark.asyncio
class TestRerankDuplicateIdDefense:
    async def test_duplicate_id_does_not_silently_drop_an_item(self):
        """Codereview finding: a duplicate id in the API response must not inflate the
        reranked count past a real dropped item -- membership is tracked via a `seen` set,
        not len(reranked), so [id=0, id=0] for original [0, 1] still appends the missing id=1."""
        mock_client = AsyncMock()
        mock_client.ranking_config_path.return_value = "projects/test/locations/global/rankingConfigs/default"
        mock_client.rank.return_value = _make_ranking_response(["0", "0"])

        archivist = _make_archivist(rank_client=mock_client)
        original = _knowledge_results()[:2]  # [id=k1, id=k2] -> rids "0","1"

        with patch("src.agents.archivist.logger") as mock_logger:
            result = await archivist.rerank("test", original, "knowledge")

        assert len(result) == 2, "Duplicate id must not cause a dropped item"
        assert original[0] in result
        assert original[1] in result, "id=1 (never returned by the API) must be appended, not lost"
        assert result.count(original[0]) == 1, "Duplicate id must not duplicate the result entry either"
        mock_logger.warning.assert_called()

    async def test_record_building_crash_falls_back_to_original_order(self):
        """Codereview finding: a non-string 'fact' payload (e.g. int/list/dict) must not raise
        uncaught -- the record-building loop lives inside the same try/except as the API call."""
        mock_client = AsyncMock()
        mock_client.ranking_config_path.return_value = "projects/test/locations/global/rankingConfigs/default"
        mock_client.rank.return_value = _make_ranking_response(["0"])

        archivist = _make_archivist(rank_client=mock_client)
        original = [{"id": "k1", "score": 0.8, "payload": {"fact": 12345}}]  # non-string fact

        with patch("src.agents.archivist.logger") as mock_logger:
            result = await archivist.rerank("test", original, "knowledge")

        # Coerced to str -- no crash, and since the mocked API accepted it, order is API-driven.
        assert len(result) == 1
        assert result[0] is original[0]


# ===========================================================================
# T-3/T-5 (codereview fix): handler-level integration -- real handle_consult_deep_memory()
# ===========================================================================

def _make_tool_ctx(event, archivist):
    """Minimal ToolContext stand-in exposing only what handle_consult_deep_memory calls."""
    ctx = MagicMock()
    bb = AsyncMock()
    bb.get_event = AsyncMock(return_value=event)
    ctx.get_blackboard = MagicMock(return_value=bb)
    ctx.next_turn_number = AsyncMock(return_value=1)
    ctx.append_and_broadcast = AsyncMock()
    ctx.get_agent_instance = MagicMock(return_value=archivist)
    return ctx


def _make_event_stub():
    ev = MagicMock()
    ev.conversation = []
    ev.service = None
    ev.source = "chat"
    return ev


@pytest.mark.asyncio
class TestHandleConsultDeepMemoryRerankIntegration:
    async def test_disabled_gate_at_handler_level_no_rerank_api_call(self):
        """T-3: VERTEX_RANKER_MODEL='' -> handle_consult_deep_memory's real gather(rerank x3)
        still calls archivist.rerank() (method always exists on the class), but rerank()
        internally no-ops (no API call) -- verified via a REAL Archivist instance, not a mock
        that fakes hasattr(archivist, "rerank") away."""
        from src.agents.handlers_lookup import handle_consult_deep_memory

        mock_client = AsyncMock()
        archivist = _make_archivist(rank_client=mock_client, ranker_model="")  # disabled
        archivist.embed_query = AsyncMock(return_value=None)
        archivist.search_knowledge = AsyncMock(return_value=_knowledge_results())
        archivist.search_lessons = AsyncMock(return_value=[])
        archivist.search = AsyncMock(return_value=[])

        ctx = _make_tool_ctx(_make_event_stub(), archivist)

        result = await handle_consult_deep_memory(ctx, "evt-1", {"query": "redis config"}, None)

        assert result is True  # has_results -> re-invoke LLM
        mock_client.rank.assert_not_called(), "Ranking API must never be called when disabled"
        ctx.append_and_broadcast.assert_awaited_once()
        turn = ctx.append_and_broadcast.await_args.args[1]
        assert "Redis" in turn.evidence or "Reference Facts" in turn.evidence

    async def test_gather_fallback_when_rerank_raises_unexpectedly(self):
        """Codereview finding (defense-in-depth): even though Archivist.rerank() is
        documented to never raise, the real handle_consult_deep_memory() gather call site
        now uses return_exceptions=True + per-collection fallback -- a hypothetical future
        regression in rerank() degrades only the affected collection, not the whole handler."""
        from src.agents.handlers_lookup import handle_consult_deep_memory

        archivist = MagicMock()
        archivist.embed_query = AsyncMock(return_value=None)
        archivist.search_knowledge = AsyncMock(return_value=_knowledge_results())
        archivist.search_lessons = AsyncMock(return_value=_lessons_results())
        archivist.search = AsyncMock(return_value=_events_results())

        async def flaky_rerank(query, results, source_type):
            if source_type == "lessons":
                raise RuntimeError("unexpected regression")
            return results

        archivist.rerank = flaky_rerank

        ctx = _make_tool_ctx(_make_event_stub(), archivist)

        result = await handle_consult_deep_memory(ctx, "evt-1", {"query": "test"}, None)

        assert result is True, "Handler must not crash when one collection's rerank raises"
        turn = ctx.append_and_broadcast.await_args.args[1]
        assert "Reference Facts" in turn.evidence
        assert "Lessons Learned" in turn.evidence, "Lessons must still render via original-order fallback"
        assert "Past Events" in turn.evidence

    async def test_three_collections_reranked_via_real_gather(self):
        """T-5: handle_consult_deep_memory's real asyncio.gather(rerank x3) call site --
        verified end-to-end through a REAL Archivist.rerank(), not a monkeypatched stand-in."""
        from src.agents.handlers_lookup import handle_consult_deep_memory

        mock_client = AsyncMock()
        mock_client.ranking_config_path.return_value = "projects/test/locations/global/rankingConfigs/default"

        async def fake_rank(request):
            # Reverse order for whichever collection is being ranked (bounded record count).
            ids = [r.id for r in request.records]
            return _make_ranking_response(list(reversed(ids)))

        mock_client.rank.side_effect = fake_rank
        archivist = _make_archivist(rank_client=mock_client, ranker_model="semantic-ranker-default@latest")
        archivist.embed_query = AsyncMock(return_value=None)
        archivist.search_knowledge = AsyncMock(return_value=_knowledge_results())
        archivist.search_lessons = AsyncMock(return_value=_lessons_results())
        archivist.search = AsyncMock(return_value=_events_results())

        ctx = _make_tool_ctx(_make_event_stub(), archivist)

        result = await handle_consult_deep_memory(ctx, "evt-1", {"query": "test"}, None)

        assert result is True
        assert mock_client.rank.call_count == 3, "All 3 collections must be reranked via the real gather call site"
        turn = ctx.append_and_broadcast.await_args.args[1]
        assert "Reference Facts" in turn.evidence
        assert "Lessons Learned" in turn.evidence
        assert "Past Events" in turn.evidence


# ===========================================================================
# Codereview fix: circuit breaker opens after N consecutive failures, skipping
# the Ranking API entirely (no 2s timeout tax) until cooldown expires
# ===========================================================================
@pytest.mark.asyncio
class TestRerankCircuitBreaker:
    async def test_circuit_opens_after_threshold_consecutive_failures(self):
        """After _RANK_CIRCUIT_THRESHOLD consecutive failures, the circuit opens and
        _rank_circuit_open_until moves into the future."""
        from src.agents.archivist import _RANK_CIRCUIT_THRESHOLD

        mock_client = AsyncMock()
        mock_client.ranking_config_path.return_value = "projects/test/locations/global/rankingConfigs/default"
        mock_client.rank.side_effect = Exception("503 Service Unavailable")

        archivist = _make_archivist(rank_client=mock_client)

        before = time.time()
        for _ in range(_RANK_CIRCUIT_THRESHOLD):
            await archivist.rerank("test", _knowledge_results(), "knowledge")

        assert archivist._rank_consecutive_failures >= _RANK_CIRCUIT_THRESHOLD
        assert archivist._rank_circuit_open_until > before

    async def test_open_circuit_skips_api_call_entirely(self):
        """While the circuit is open, rerank() must not call the Ranking API at all --
        this is the whole point (no timeout tax during a sustained outage)."""
        mock_client = AsyncMock()
        archivist = _make_archivist(rank_client=mock_client, rank_circuit_open_until=time.time() + 60)
        original = _knowledge_results()

        result = await archivist.rerank("test", original, "knowledge")

        assert result is original
        mock_client.rank.assert_not_called()

    async def test_success_resets_consecutive_failure_count(self):
        """A successful rerank call resets the failure counter -- the circuit
        self-heals rather than staying degraded forever after transient errors."""
        mock_client = AsyncMock()
        mock_client.ranking_config_path.return_value = "projects/test/locations/global/rankingConfigs/default"
        mock_client.rank.return_value = _make_ranking_response(["0"])

        archivist = _make_archivist(rank_client=mock_client, rank_consecutive_failures=2)

        await archivist.rerank("test", [_knowledge_results()[0]], "knowledge")

        assert archivist._rank_consecutive_failures == 0

    async def test_circuit_closes_after_cooldown_expires(self):
        """Once _rank_circuit_open_until is in the past, rerank() resumes calling
        the API normally -- the circuit self-heals rather than staying open forever."""
        mock_client = AsyncMock()
        mock_client.ranking_config_path.return_value = "projects/test/locations/global/rankingConfigs/default"
        mock_client.rank.return_value = _make_ranking_response(["0"])

        archivist = _make_archivist(rank_client=mock_client, rank_circuit_open_until=time.time() - 1)

        await archivist.rerank("test", [_knowledge_results()[0]], "knowledge")

        mock_client.rank.assert_called_once()


# ===========================================================================
# Codereview fix: rerank() redacts PII/secrets before sending to the external
# Ranking API (query and per-record content), mirroring the JARVIS Live API path
# ===========================================================================
@pytest.mark.asyncio
class TestRerankPiiRedaction:
    async def test_content_and_query_redacted_before_api_call(self):
        """Both the query and per-record content must be redacted before they leave
        the process to Google's external Discovery Engine Ranking API."""
        mock_client = AsyncMock()
        mock_client.ranking_config_path.return_value = "projects/test/locations/global/rankingConfigs/default"
        mock_client.rank.return_value = _make_ranking_response(["0"])

        archivist = _make_archivist(rank_client=mock_client)
        results = [{"id": "k1", "score": 0.8, "payload": {"fact": "Contact alice@example.com about 10.0.0.5"}}]

        await archivist.rerank("email me at bob@example.com", results, "knowledge")

        call_args = mock_client.rank.call_args
        rank_request = call_args[0][0]
        assert "alice@example.com" not in rank_request.records[0].content
        assert "10.0.0.5" not in rank_request.records[0].content
        assert "[redacted-email]" in rank_request.records[0].content
        assert "[redacted-ip]" in rank_request.records[0].content
        assert "bob@example.com" not in rank_request.query
        assert "[redacted-email]" in rank_request.query


# ===========================================================================
# T-18: Rerank cold-start (client None)
# ===========================================================================
@pytest.mark.asyncio
class TestRerankColdStart:
    async def test_cold_start_initializes_client(self):
        """T-18: First call with _rank_client=None → _ensure_rank_client called, rerank succeeds."""
        mock_client = AsyncMock()
        mock_client.ranking_config_path = MagicMock(
            return_value="projects/test-project/locations/global/rankingConfigs/default_ranking_config"
        )
        mock_client.rank.return_value = _make_ranking_response(["0", "1"])

        archivist = _make_archivist(rank_client=None)

        async def fake_ensure():
            archivist._rank_client = mock_client

        with patch.object(archivist, "_ensure_rank_client", side_effect=fake_ensure):
            result = await archivist.rerank("test", _lessons_results(), "lessons")

        assert len(result) == 2
        mock_client.rank.assert_called_once()

    async def test_cold_start_already_initialized_skips(self):
        """T-18: Second call with _rank_client set → _ensure_rank_client still called but short-circuits."""
        mock_client = AsyncMock()
        mock_client.ranking_config_path.return_value = "projects/test/locations/global/rankingConfigs/default"
        mock_client.rank.return_value = _make_ranking_response(["0"])

        archivist = _make_archivist(rank_client=mock_client)

        result = await archivist.rerank("test", [_knowledge_results()[0]], "knowledge")

        assert len(result) == 1
        mock_client.rank.assert_called_once()
