# BlackBoard/tests/test_gemini_grounding.py
# @ai-rules:
# 1. [Constraint]: Tests GeminiAdapter's per-call search_enabled/grounding_corpus kwargs (NOT adapter
#    state -- removed post-codereview to fix a cross-event singleton race), _build_config tool
#    construction, generate_stream .retrieved_context extraction, and Brain._resolve_grounding_mode.
# 2. [Pattern]: Uses pytest + pytest-asyncio. Patches google.genai.Client to avoid real Vertex AI calls.
# 3. [Gotcha]: _build_config has THREE branches: (1) if tools, (2) elif search_enabled, (3) elif grounding_corpus.
#    Grounding must also be appended inside the 'if tools' branch when both are active.
# 4. [Pattern]: Tests written against plan spec (T-10 through T-15, T-19), reconciled post-codereview
#    to call real production code (Brain._resolve_grounding_mode, GeminiAdapter.generate_stream) instead
#    of re-deriving the logic locally -- the codereview flagged the local-recompute pattern as a
#    false-confidence test gap (the exact logic these tests must catch a regression in).
"""
Tests for RAG Engine grounding in GeminiAdapter and Brain call site.

Spec IDs: T-10 (grounding in if-tools branch), T-11 (elif branch, tools=None),
T-12 (disabled when None), T-13 (.retrieved_context extraction),
T-14 (function-calling unaffected), T-15 (ClaudeAdapter no-op),
T-19 (RAG_GROUNDING_ENABLED=false).
"""
from __future__ import annotations

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_adapter():
    """Create GeminiAdapter with mocked google.genai client."""
    with patch("google.genai.Client"):
        from src.agents.llm.gemini_client import GeminiAdapter
        return GeminiAdapter(
            project="test-project",
            location="us-central1",
            model_name="gemini-3.1-pro-preview-customtools",
        )


def _sample_tool_schemas():
    """Minimal tool schemas for testing _build_config with tools."""
    return [
        {
            "name": "classify_event",
            "description": "Classify the event domain",
            "input_schema": {
                "type": "object",
                "properties": {"domain": {"type": "string"}},
            },
        },
        {
            "name": "close_event",
            "description": "Close the event",
            "input_schema": {
                "type": "object",
                "properties": {"reason": {"type": "string"}},
            },
        },
    ]


def _make_chunk(text=None, function_calls=None, candidates=None, usage_metadata=None):
    """Build a mock streaming chunk mimicking google.genai's GenerateContentResponse chunk shape."""
    chunk = MagicMock()
    chunk.text = text
    chunk.function_calls = function_calls
    chunk.candidates = candidates or []
    chunk.usage_metadata = usage_metadata
    return chunk


class _MockGenaiStream:
    """Real async iterator over pre-built chunks (matches tests/test_stream_timeout.py's MockStream)."""

    def __init__(self, chunks: list):
        self._chunks = list(chunks)
        self._i = 0

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self._i >= len(self._chunks):
            raise StopAsyncIteration
        c = self._chunks[self._i]
        self._i += 1
        return c


async def _consume_stream(adapter, **kwargs):
    """Call the real generate_stream() and collect all yielded chunks."""
    chunks = []
    async for c in adapter.generate_stream(**kwargs):
        chunks.append(c)
    return chunks


# ===========================================================================
# T-10: Grounding tool attached via per-call kwargs (if tools branch)
# ===========================================================================
@pytest.mark.asyncio
class TestGroundingWithTools:
    async def test_retrieval_tool_alongside_function_declarations(self):
        """T-10: grounding_corpus kwarg + tools=[...] -> both function_declarations and retrieval present."""
        corpus = "projects/cnv-ai-insights/locations/us-central1/ragCorpora/12345"
        adapter = _make_adapter()

        config = adapter._build_config(
            system_prompt="test",
            tools=_sample_tool_schemas(),
            temperature=0.8,
            top_p=0.95,
            max_output_tokens=65000,
            grounding_corpus=corpus,
        )

        tool_objects = config.tools or []
        has_func = any(
            t.function_declarations is not None and len(t.function_declarations) > 0
            for t in tool_objects
        )
        has_retrieval = any(t.retrieval is not None for t in tool_objects)

        assert has_func, "Function declarations must be present"
        assert has_retrieval, "Retrieval tool must be present when grounding corpus is set"

    async def test_retrieval_tool_has_correct_corpus(self):
        """T-10: Retrieval tool references the correct corpus path."""
        corpus = "projects/cnv-ai-insights/locations/us-central1/ragCorpora/99999"
        adapter = _make_adapter()

        config = adapter._build_config(
            system_prompt="test",
            tools=_sample_tool_schemas(),
            temperature=0.8,
            top_p=0.95,
            max_output_tokens=65000,
            grounding_corpus=corpus,
        )

        retrieval_tools = [t for t in (config.tools or []) if t.retrieval is not None]
        assert len(retrieval_tools) == 1

        rag_store = retrieval_tools[0].retrieval.vertex_rag_store
        assert rag_store is not None
        assert len(rag_store.rag_resources) == 1
        assert rag_store.rag_resources[0].rag_corpus == corpus

    async def test_no_store_context_in_brain_grounding(self):
        """T-10: Brain grounding (non-Live API) must NOT include store_context."""
        corpus = "projects/cnv-ai-insights/locations/us-central1/ragCorpora/12345"
        adapter = _make_adapter()

        config = adapter._build_config(
            system_prompt="test",
            tools=_sample_tool_schemas(),
            temperature=0.8,
            top_p=0.95,
            max_output_tokens=65000,
            grounding_corpus=corpus,
        )

        retrieval_tools = [t for t in (config.tools or []) if t.retrieval is not None]
        if retrieval_tools:
            rag_store = retrieval_tools[0].retrieval.vertex_rag_store
            store_ctx = getattr(rag_store, "store_context", None)
            assert store_ctx is None or store_ctx is False, (
                "Brain (non-Live API) must not set store_context=True"
            )


# ===========================================================================
# T-11: Grounding tool attached (elif branch, tools=None)
# ===========================================================================
@pytest.mark.asyncio
class TestGroundingWithoutTools:
    async def test_retrieval_only_when_no_tools_no_search(self):
        """T-11: tools=None + search disabled + grounding set -> retrieval-only tool."""
        corpus = "projects/test/locations/us-central1/ragCorpora/777"
        adapter = _make_adapter()

        config = adapter._build_config(
            system_prompt="test",
            tools=None,
            temperature=0.8,
            top_p=0.95,
            max_output_tokens=65000,
            search_enabled=False,
            grounding_corpus=corpus,
        )

        tool_objects = config.tools or []
        assert len(tool_objects) >= 1, "At least one tool (retrieval) must be present"

        has_retrieval = any(t.retrieval is not None for t in tool_objects)
        assert has_retrieval, "Retrieval tool must be in the elif branch"

        has_func = any(
            t.function_declarations is not None and len(t.function_declarations) > 0
            for t in tool_objects
        )
        assert not has_func, "No function declarations when tools=None"


# ===========================================================================
# T-12: Grounding disabled when corpus is None/empty
# ===========================================================================
@pytest.mark.asyncio
class TestGroundingDisabled:
    async def test_no_retrieval_when_corpus_none(self):
        """T-12: grounding_corpus=None -> no retrieval tool."""
        adapter = _make_adapter()

        config = adapter._build_config(
            system_prompt="test",
            tools=None,
            temperature=0.8,
            top_p=0.95,
            max_output_tokens=65000,
            grounding_corpus=None,
        )

        tool_objects = config.tools or []
        has_retrieval = any(t.retrieval is not None for t in tool_objects)
        assert not has_retrieval, "No retrieval when corpus is None"

    async def test_no_retrieval_when_corpus_empty_string(self):
        """T-12: grounding_corpus='' -> no retrieval tool."""
        adapter = _make_adapter()

        config = adapter._build_config(
            system_prompt="test",
            tools=_sample_tool_schemas(),
            temperature=0.8,
            top_p=0.95,
            max_output_tokens=65000,
            grounding_corpus="",
        )

        tool_objects = config.tools or []
        has_retrieval = any(t.retrieval is not None for t in tool_objects)
        assert not has_retrieval, "No retrieval when corpus is empty string"

    async def test_setter_methods_removed(self):
        """T-12: set_search_enabled/set_grounding_corpus were removed -- fixed the singleton
        adapter-state race (codereview finding). Behavior is now call-scoped only."""
        adapter = _make_adapter()
        assert not hasattr(adapter, "set_search_enabled")
        assert not hasattr(adapter, "set_grounding_corpus")
        assert not hasattr(adapter, "_search_enabled")
        assert not hasattr(adapter, "_grounding_corpus")

    async def test_build_config_self_enforces_mutual_exclusion(self):
        """Codereview Run #2 finding: _build_config() must not rely solely on the caller
        (Brain._resolve_grounding_mode) to prevent the untested 3-way tool combination --
        it must self-enforce the invariant, mirroring LiveAPIAdapter._build_live_tools()."""
        adapter = _make_adapter()

        config = adapter._build_config(
            system_prompt="test",
            tools=_sample_tool_schemas(),
            temperature=0.8,
            top_p=0.95,
            max_output_tokens=65000,
            search_enabled=True,
            grounding_corpus="projects/test/locations/us-central1/ragCorpora/123",
        )

        tool_objects = config.tools or []
        has_search = any(getattr(t, "google_search", None) is not None for t in tool_objects)
        has_retrieval = any(t.retrieval is not None for t in tool_objects)
        has_func = any(
            t.function_declarations is not None and len(t.function_declarations) > 0
            for t in tool_objects
        )

        assert has_search, "search_enabled=True must still produce google_search"
        assert has_func, "Function declarations always present"
        assert not has_retrieval, (
            "grounding_corpus must be dropped when search_enabled=True, even if a caller "
            "passes both -- the 3-way combo must never be assembled regardless of caller discipline"
        )


# ===========================================================================
# T-13: .retrieved_context chunks extracted alongside .web (real generate_stream())
# ===========================================================================
@pytest.mark.asyncio
class TestRetrievedContextExtraction:
    async def test_web_and_rag_chunks_both_extracted(self):
        """T-13: Mixed .web + .retrieved_context -> both types in grounding_metadata.chunks with source tag."""
        web_chunk = MagicMock()
        web_chunk.web = MagicMock(title="K8s docs", uri="https://k8s.io/docs")
        web_chunk.retrieved_context = None

        rag_chunk = MagicMock()
        rag_chunk.web = None
        rag_chunk.retrieved_context = MagicMock(title="Internal runbook", uri="rag://corpus/runbook-42")

        gm = MagicMock()
        gm.grounding_chunks = [web_chunk, rag_chunk]
        gm.web_search_queries = ["kubernetes pod scheduling"]
        gm.retrieval_queries = ["internal deployment runbook"]

        candidate = MagicMock()
        candidate.content = None
        candidate.grounding_metadata = gm

        adapter = _make_adapter()
        stream = _MockGenaiStream([
            _make_chunk(candidates=[candidate]),
            _make_chunk(function_calls=[MagicMock(name="x", args={})]),
        ])
        adapter._client.aio.models.generate_content_stream = AsyncMock(return_value=stream)

        chunks = await _consume_stream(
            adapter, system_prompt="s", contents="c", grounding_corpus="projects/p/locations/l/ragCorpora/1",
        )
        done_chunk = chunks[-1]
        assert done_chunk.grounding_metadata is not None
        gm_out = done_chunk.grounding_metadata
        assert len(gm_out["chunks"]) == 2
        assert gm_out["chunks"][0]["source"] == "search"
        assert gm_out["chunks"][0]["title"] == "K8s docs"
        assert gm_out["chunks"][1]["source"] == "rag"
        assert gm_out["chunks"][1]["title"] == "Internal runbook"
        assert len(gm_out["queries"]) == 2

    async def test_rag_only_chunks(self):
        """T-13: Only .retrieved_context chunks (no web) -> all tagged as 'rag'."""
        rag_chunk = MagicMock()
        rag_chunk.web = None
        rag_chunk.retrieved_context = MagicMock(title="Corp policy", uri="rag://corpus/policy-1")

        gm = MagicMock()
        gm.grounding_chunks = [rag_chunk]
        gm.web_search_queries = None
        gm.retrieval_queries = ["corporate security policy"]

        candidate = MagicMock()
        candidate.content = None
        candidate.grounding_metadata = gm

        adapter = _make_adapter()
        stream = _MockGenaiStream([
            _make_chunk(candidates=[candidate]),
            _make_chunk(function_calls=[MagicMock(name="x", args={})]),
        ])
        adapter._client.aio.models.generate_content_stream = AsyncMock(return_value=stream)

        chunks = await _consume_stream(
            adapter, system_prompt="s", contents="c", grounding_corpus="projects/p/locations/l/ragCorpora/1",
        )
        gm_out = chunks[-1].grounding_metadata
        assert len(gm_out["chunks"]) == 1
        assert gm_out["chunks"][0]["source"] == "rag"
        assert gm_out["queries"] == ["corporate security policy"]

    async def test_no_grounding_chunks_yields_empty(self):
        """T-13: No grounding_metadata -> grounding_metadata is None on the done chunk, no error."""
        adapter = _make_adapter()
        stream = _MockGenaiStream([
            _make_chunk(text="hello"),
        ])
        adapter._client.aio.models.generate_content_stream = AsyncMock(return_value=stream)

        chunks = await _consume_stream(adapter, system_prompt="s", contents="c")
        assert chunks[-1].grounding_metadata is None

    async def test_chunk_count_capped_and_fields_truncated(self):
        """Defense-in-depth: unbounded grounding_chunks count/size must be capped (codereview finding)."""
        from src.agents.llm.gemini_client import _MAX_GROUNDING_CHUNKS, _MAX_GROUNDING_FIELD_LEN

        many_chunks = []
        for i in range(_MAX_GROUNDING_CHUNKS + 15):
            c = MagicMock()
            c.web = MagicMock(title="x" * (_MAX_GROUNDING_FIELD_LEN + 500), uri="https://example.com/" + str(i))
            c.retrieved_context = None
            many_chunks.append(c)

        gm = MagicMock()
        gm.grounding_chunks = many_chunks
        gm.web_search_queries = []
        gm.retrieval_queries = []

        candidate = MagicMock()
        candidate.content = None
        candidate.grounding_metadata = gm

        adapter = _make_adapter()
        stream_mock = AsyncMock()
        stream_mock.__aiter__.return_value = iter([_make_chunk(candidates=[candidate])])
        adapter._client.aio.models.generate_content_stream = AsyncMock(return_value=stream_mock)

        chunks = await _consume_stream(adapter, system_prompt="s", contents="c")
        gm_out = chunks[-1].grounding_metadata
        assert len(gm_out["chunks"]) == _MAX_GROUNDING_CHUNKS
        assert len(gm_out["chunks"][0]["title"]) == _MAX_GROUNDING_FIELD_LEN


# ===========================================================================
# T-14: Function-calling unaffected by grounding
# ===========================================================================
@pytest.mark.asyncio
class TestFunctionCallingWithGrounding:
    async def test_function_declarations_preserved(self):
        """T-14: Tools + grounding -> function calling schemas still present and correct."""
        corpus = "projects/test/locations/us-central1/ragCorpora/123"
        adapter = _make_adapter()

        schemas = _sample_tool_schemas()
        config = adapter._build_config(
            system_prompt="test",
            tools=schemas,
            temperature=0.8,
            top_p=0.95,
            max_output_tokens=65000,
            grounding_corpus=corpus,
        )

        func_tools = [
            t for t in (config.tools or [])
            if t.function_declarations is not None and len(t.function_declarations) > 0
        ]
        assert len(func_tools) == 1, "Exactly one function_declarations Tool"

        declarations = func_tools[0].function_declarations
        names = [d.name for d in declarations]
        assert "classify_event" in names
        assert "close_event" in names

    async def test_automatic_function_calling_disabled(self):
        """T-14: automatic_function_calling still disabled when grounding is added."""
        corpus = "projects/test/locations/us-central1/ragCorpora/123"
        adapter = _make_adapter()

        config = adapter._build_config(
            system_prompt="test",
            tools=_sample_tool_schemas(),
            temperature=0.8,
            top_p=0.95,
            max_output_tokens=65000,
            grounding_corpus=corpus,
        )

        assert config.automatic_function_calling is not None
        assert config.automatic_function_calling.disable is True

    async def test_search_and_grounding_mutual_exclusion_at_brain_level(self):
        """T-14: want_search=True -> want_grounding=False, via the REAL Brain._resolve_grounding_mode."""
        from src.agents.brain import Brain

        want_search, grounding_corpus = Brain._resolve_grounding_mode(
            search_enabled=True,
            brain_phase="triage",
            rag_grounding_enabled=True,
            rag_grounding_corpus="projects/test/locations/us-central1/ragCorpora/123",
        )

        assert want_search is True, "Triage phase enables search"
        assert grounding_corpus is None, "Mutual exclusion: search takes priority, grounding suppressed"

    async def test_grounding_fires_on_verify_phase(self):
        """T-14: brain_phase='verify' -> want_search=False, grounding_corpus set, via real Brain method."""
        from src.agents.brain import Brain

        corpus = "projects/test/locations/us-central1/ragCorpora/123"
        want_search, grounding_corpus = Brain._resolve_grounding_mode(
            search_enabled=True,
            brain_phase="verify",
            rag_grounding_enabled=True,
            rag_grounding_corpus=corpus,
        )

        assert want_search is False, "Verify phase does not enable search"
        assert grounding_corpus == corpus, "Grounding fires on non-search phases"

    async def test_dispatch_phase_also_enables_search_over_grounding(self):
        """T-14: dispatch phase behaves like triage -- search wins, grounding suppressed."""
        from src.agents.brain import Brain

        want_search, grounding_corpus = Brain._resolve_grounding_mode(
            search_enabled=True,
            brain_phase="dispatch",
            rag_grounding_enabled=True,
            rag_grounding_corpus="projects/test/locations/us-central1/ragCorpora/123",
        )

        assert want_search is True
        assert grounding_corpus is None


# ===========================================================================
# T-15: ClaudeAdapter no-op (accepts and ignores search_enabled/grounding_corpus)
# ===========================================================================
@pytest.mark.asyncio
class TestClaudeAdapterNoOp:
    async def test_claude_generate_stream_accepts_grounding_kwargs_without_error(self):
        """T-15: ClaudeAdapter.generate_stream(search_enabled=True, grounding_corpus=...) never raises --
        confirms the Brain call site can pass these kwargs unconditionally without an AttributeError,
        even though Claude has no Search/RAG-grounding equivalent."""
        with patch("anthropic.AsyncAnthropicVertex"):
            from src.agents.llm.claude_client import ClaudeAdapter
            adapter = ClaudeAdapter(project="p", location="l", model_name="claude-sonnet-5")

        fake_stream_cm = MagicMock()
        fake_message = MagicMock()
        fake_message.content = []
        fake_message.usage = None

        async def fake_text_stream():
            if False:
                yield  # pragma: no cover -- empty async generator

        fake_stream_cm.text_stream = fake_text_stream()
        fake_stream_cm.get_final_message = AsyncMock(return_value=fake_message)

        class _Ctx:
            async def __aenter__(self):
                return fake_stream_cm

            async def __aexit__(self, *a):
                return False

        adapter._client.messages.stream = MagicMock(return_value=_Ctx())

        chunks = []
        async for c in adapter.generate_stream(
            system_prompt="s", contents="c", search_enabled=True,
            grounding_corpus="projects/p/locations/l/ragCorpora/1",
        ):
            chunks.append(c)

        assert chunks[-1].done is True

    async def test_claude_generate_stream_accepts_thinking_level_without_error(self):
        """Codereview Run #2 finding (pre-existing, closed alongside this fix): Brain
        unconditionally passes thinking_level= to generate_stream() regardless of provider.
        Without accepting it, LLM_PROVIDER=claude would raise TypeError on every Brain LLM
        call -- a full outage. Verify ClaudeAdapter now accepts and ignores it."""
        with patch("anthropic.AsyncAnthropicVertex"):
            from src.agents.llm.claude_client import ClaudeAdapter
            adapter = ClaudeAdapter(project="p", location="l", model_name="claude-sonnet-5")

        fake_stream_cm = MagicMock()
        fake_message = MagicMock()
        fake_message.content = []
        fake_message.usage = None

        async def fake_text_stream():
            if False:
                yield  # pragma: no cover -- empty async generator

        fake_stream_cm.text_stream = fake_text_stream()
        fake_stream_cm.get_final_message = AsyncMock(return_value=fake_message)

        class _Ctx:
            async def __aenter__(self):
                return fake_stream_cm

            async def __aexit__(self, *a):
                return False

        adapter._client.messages.stream = MagicMock(return_value=_Ctx())

        chunks = []
        async for c in adapter.generate_stream(
            system_prompt="s", contents="c", thinking_level="high",
            search_enabled=True, grounding_corpus="projects/p/locations/l/ragCorpora/1",
        ):
            chunks.append(c)

        assert chunks[-1].done is True

    async def test_claude_adapter_has_no_grounding_state(self):
        """T-15: ClaudeAdapter never had set_search_enabled/set_grounding_corpus -- confirms the
        singleton-state race fixed in GeminiAdapter never applied to Claude in the first place."""
        with patch("anthropic.AsyncAnthropicVertex"):
            from src.agents.llm.claude_client import ClaudeAdapter
            adapter = ClaudeAdapter(project="p", location="l", model_name="claude-sonnet-5")

        assert not hasattr(adapter, "set_search_enabled")
        assert not hasattr(adapter, "set_grounding_corpus")


# ===========================================================================
# T-19: RAG_GROUNDING_ENABLED=false disables grounding (real Brain._resolve_grounding_mode)
# ===========================================================================
class TestGroundingEnvGate:
    def test_enabled_false_disables_grounding(self):
        """T-19: RAG_GROUNDING_ENABLED=false + corpus set -> grounding never fires."""
        from src.agents.brain import Brain

        rag_grounding_enabled = os.getenv("RAG_GROUNDING_ENABLED", "false").lower() == "true"
        want_search, grounding_corpus = Brain._resolve_grounding_mode(
            search_enabled=False,
            brain_phase="verify",
            rag_grounding_enabled=rag_grounding_enabled,
            rag_grounding_corpus="projects/test/locations/us-central1/ragCorpora/123",
        )

        assert grounding_corpus is None, "Grounding disabled when RAG_GROUNDING_ENABLED=false"

    def test_enabled_true_with_corpus_enables_grounding(self):
        """T-19: RAG_GROUNDING_ENABLED=true + corpus set + no search -> grounding fires."""
        from src.agents.brain import Brain

        corpus = "projects/test/locations/us-central1/ragCorpora/123"
        want_search, grounding_corpus = Brain._resolve_grounding_mode(
            search_enabled=False,
            brain_phase="verify",
            rag_grounding_enabled=True,
            rag_grounding_corpus=corpus,
        )

        assert grounding_corpus == corpus, "Grounding enabled when flag is true and corpus is set"

    def test_enabled_true_without_corpus_disables_grounding(self):
        """T-19: RAG_GROUNDING_ENABLED=true + corpus='' -> no grounding."""
        from src.agents.brain import Brain

        want_search, grounding_corpus = Brain._resolve_grounding_mode(
            search_enabled=False,
            brain_phase="verify",
            rag_grounding_enabled=True,
            rag_grounding_corpus="",
        )

        assert grounding_corpus is None, "Empty corpus disables grounding even when enabled=true"


# ===========================================================================
# Codereview Run #2 fix: resolved-redirect URL regains unbounded length,
# bypassing the adapter-layer _MAX_GROUNDING_FIELD_LEN cap on the pre-resolution uri
# ===========================================================================
@pytest.mark.asyncio
class TestResolvedUrlLengthCap:
    async def test_resolved_redirect_url_is_truncated(self):
        """Brain._resolve_grounding_urls() must re-cap the resolved uri -- httpx's
        client.head() redirect resolution replaces `uri` with the final URL, which
        is untrusted-size and was NOT covered by the adapter-layer truncation."""
        from unittest.mock import AsyncMock as _AsyncMock
        from src.agents.brain import Brain

        long_resolved_url = "https://example.com/" + ("x" * 1000)
        chunk = {
            "title": "Test",
            "uri": "https://vertexaisearch.cloud.google.com/grounding-api-redirect/abc123",
            "source": "search",
        }

        mock_response = MagicMock()
        mock_response.url = long_resolved_url

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = _AsyncMock()
            mock_client.head = _AsyncMock(return_value=mock_response)
            mock_client_cls.return_value.__aenter__ = _AsyncMock(return_value=mock_client)
            mock_client_cls.return_value.__aexit__ = _AsyncMock(return_value=False)

            result = await Brain._resolve_grounding_urls([chunk])

        from src.agents.llm.gemini_client import _MAX_GROUNDING_FIELD_LEN
        assert len(result[0]["uri"]) <= _MAX_GROUNDING_FIELD_LEN, (
            "Resolved redirect URL must be capped -- it bypasses the adapter-layer truncation"
        )
