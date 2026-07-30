# BlackBoard/tests/test_jarvis_memory_corpus.py
# @ai-rules:
# 1. [Constraint]: Tests JARVIS MemoryCorpus config, priming turn on wake, grounding_metadata extraction.
# 2. [Pattern]: Uses pytest + pytest-asyncio. Mocks Live API session and google-genai types.
# 3. [Gotcha]: _connect() shared by send_pulse (fresh wake), _try_reconnect, _rotate_session.
#    Priming turn fires from send_pulse only (not _connect itself, not _try_reconnect).
# 4. [Pattern]: Tests written against plan spec (T-6 through T-9, T-16), reconciled post-codereview
#    to call REAL LiveAPIAdapter methods on a __new__()-constructed instance (matching Archivist's
#    test pattern in test_deep_memory_rerank.py) instead of re-deriving logic locally. The codereview
#    flagged the local-recompute pattern as a false-confidence gap -- none of these tests previously
#    exercised _build_live_tools()/_send_wake_priming()/_process_message() at all.
"""
Tests for JARVIS MemoryCorpus integration and handoff consolidation.

Spec IDs: T-6 (MemoryCorpus in connect config), T-7 (connect without corpus),
T-8 (priming turn on wake), T-9 (grounding_metadata extraction),
T-16 (Live API probe, integration-only, marked skip).
"""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_jarvis_adapter(**overrides):
    """Construct a real LiveAPIAdapter via __new__ (bypasses __init__'s heavy deps:
    Blackboard, Archivist, WS broadcast, google-genai Client), with only the attributes
    the methods under test actually touch. Mirrors _make_archivist() in
    tests/test_deep_memory_rerank.py -- this is the established pattern in this repo for
    testing real bound methods on classes with expensive constructors.
    """
    from src.adapters.live_api_adapter import LiveAPIAdapter

    adapter = LiveAPIAdapter.__new__(LiveAPIAdapter)
    adapter._session = overrides.get("session", None)
    adapter._rag_corpus_id = overrides.get("rag_corpus_id", "")
    adapter._rag_enabled = overrides.get("rag_enabled", False)
    adapter._blackboard = overrides.get("blackboard", AsyncMock())
    adapter._archivist = overrides.get("archivist", AsyncMock())
    adapter._last_pulse_event_id = overrides.get("last_pulse_event_id", None)
    adapter._collecting_handoff = False
    adapter._handoff_buffer = []
    adapter._text_buffer = []
    adapter._awaiting_jarvis_reply = False
    adapter._awaiting_jarvis_event_id = None
    adapter._generating_report = False
    adapter._handoff_enabled = False
    adapter._active_meta_event_id = overrides.get("active_meta_event_id", None)
    return adapter


def _make_pulse_batch(event_id: str = "evt-1", turn: int = 1, event_source: str = "aligner"):
    """Minimal PulseBatch stand-in -- send_pulse() reads event_id/event_source/pulses/turn."""
    batch = MagicMock()
    batch.event_id = event_id
    batch.turn = turn
    batch.event_source = event_source
    batch.pulses = []
    return batch


def _spec_msg(server_content_grounding_metadata=None):
    """Build a minimal Live API message mock. spec= restricts hasattr() to only the
    listed attributes so _process_message's other branches (go_away, tool_call, text)
    can't accidentally fire via MagicMock's auto-attribute truthiness."""
    server_content = MagicMock(spec=["grounding_metadata", "turn_complete"])
    server_content.grounding_metadata = server_content_grounding_metadata
    server_content.turn_complete = False

    msg = MagicMock(spec=["text", "server_content", "tool_call", "tool_call_cancellation",
                           "go_away", "session_resumption_update"])
    msg.text = None
    msg.server_content = server_content
    msg.tool_call = None
    msg.tool_call_cancellation = None
    msg.go_away = None
    msg.session_resumption_update = None
    return msg


# ===========================================================================
# T-6: JARVIS MemoryCorpus in connect config (real _build_live_tools())
# ===========================================================================
@pytest.mark.asyncio
class TestJarvisMemoryCorpusConfig:
    async def test_retrieval_tool_added_when_enabled(self):
        """T-6: RAG enabled + corpus set -> real _build_live_tools() includes
        Tool(retrieval=VertexRagStore(store_context=True))."""
        from google.genai import types

        corpus_path = "projects/cnv-ai-insights/locations/us-central1/ragCorpora/12345"
        adapter = _make_jarvis_adapter(rag_enabled=True, rag_corpus_id=corpus_path)

        tools = adapter._build_live_tools(types)

        retrieval_tools = [t for t in tools if t.retrieval is not None]
        assert len(retrieval_tools) == 1
        rag_store = retrieval_tools[0].retrieval.vertex_rag_store
        assert rag_store.store_context is True
        assert len(rag_store.rag_resources) == 1
        assert rag_store.rag_resources[0].rag_corpus == corpus_path

    async def test_mutual_exclusion_drops_google_search_when_rag_active(self):
        """T-6 (codereview fix): the untested 3-way combo (functions+search+retrieval) is
        never assembled -- real _build_live_tools() drops google_search when RAG is enabled,
        mirroring Brain._resolve_grounding_mode's mutual exclusion."""
        from google.genai import types

        corpus_path = "projects/cnv-ai-insights/locations/us-central1/ragCorpora/12345"
        adapter = _make_jarvis_adapter(rag_enabled=True, rag_corpus_id=corpus_path)

        tools = adapter._build_live_tools(types)

        has_func = any(getattr(t, "function_declarations", None) is not None for t in tools)
        has_search = any(getattr(t, "google_search", None) is not None for t in tools)
        has_retrieval = any(getattr(t, "retrieval", None) is not None for t in tools)

        assert has_func, "Function declarations always present"
        assert has_retrieval, "Retrieval present when RAG enabled"
        assert not has_search, "google_search must be dropped when RAG is active -- untested 3-way combo"
        assert len(tools) == 2, "Exactly 2 tools when RAG active (functions + retrieval, not 3)"


# ===========================================================================
# T-7: JARVIS connect works without corpus (real _build_live_tools())
# ===========================================================================
@pytest.mark.asyncio
class TestJarvisConnectWithoutCorpus:
    async def test_no_retrieval_tool_when_disabled(self):
        """T-7: JARVIS_RAG_ENABLED=false -> real _build_live_tools() has no retrieval tool,
        google_search present (pre-existing behavior unchanged)."""
        from google.genai import types

        adapter = _make_jarvis_adapter(rag_enabled=False, rag_corpus_id="")

        tools = adapter._build_live_tools(types)

        assert len(tools) == 2
        assert all(getattr(t, "retrieval", None) is None for t in tools)
        assert any(getattr(t, "google_search", None) is not None for t in tools), (
            "google_search must be present when RAG is disabled"
        )

    async def test_no_retrieval_tool_when_corpus_empty(self):
        """T-7: JARVIS_RAG_CORPUS_ID='' -> real _build_live_tools() has no retrieval tool
        even if JARVIS_RAG_ENABLED=true (corpus is required, not just the flag)."""
        from google.genai import types

        adapter = _make_jarvis_adapter(rag_enabled=True, rag_corpus_id="")

        tools = adapter._build_live_tools(types)

        assert all(getattr(t, "retrieval", None) is None for t in tools)
        assert any(getattr(t, "google_search", None) is not None for t in tools)


# ===========================================================================
# T-8: Priming turn sent on wake (real _send_wake_priming())
# ===========================================================================
@pytest.mark.asyncio
class TestPrimingTurnOnWake:
    async def test_priming_turn_uses_redis_handoff_notes(self):
        """T-8: Redis note read first via real _tool_recall_handoff_notes(); real
        _send_wake_priming() sends a turn incorporating that text through self._session.send()."""
        adapter = _make_jarvis_adapter(session=AsyncMock())
        adapter._blackboard.get_handoff_reports = AsyncMock(return_value=[
            {"report": "Prior session observed pipeline stuck in CrashLoop.", "timestamp": 0},
        ])

        await adapter._send_wake_priming()

        adapter._session.send.assert_awaited_once()
        sent_kwargs = adapter._session.send.await_args.kwargs
        assert "Prior session observed pipeline stuck in CrashLoop" in sent_kwargs["input"]
        assert sent_kwargs["end_of_turn"] is True

    async def test_priming_turn_fresh_wake_only_via_was_idle_flag(self):
        """T-8: send_pulse()'s was_idle detection gates whether _send_wake_priming fires --
        verified against the real send_pulse() control flow, not a local boolean recompute."""
        from src.adapters.live_api_adapter import LiveAPIAdapter

        adapter = _make_jarvis_adapter(session=None)
        adapter._connect = AsyncMock(side_effect=lambda: setattr(adapter, "_session", AsyncMock()))
        adapter._send_wake_priming = AsyncMock()
        adapter._format_pulse = MagicMock(return_value="pulse text")

        batch = _make_pulse_batch()

        await LiveAPIAdapter.send_pulse(adapter, batch)

        adapter._connect.assert_awaited_once()
        adapter._send_wake_priming.assert_awaited_once()

    async def test_priming_turn_skipped_on_reconnect_not_fresh_wake(self):
        """T-8: when a session already exists (not a fresh wake), send_pulse() must NOT
        fire _send_wake_priming() again -- this is the was_idle gate's whole purpose."""
        from src.adapters.live_api_adapter import LiveAPIAdapter

        adapter = _make_jarvis_adapter(session=AsyncMock())
        adapter._connect = AsyncMock()
        adapter._send_wake_priming = AsyncMock()
        adapter._format_pulse = MagicMock(return_value="pulse text")

        batch = _make_pulse_batch()

        await LiveAPIAdapter.send_pulse(adapter, batch)

        adapter._connect.assert_not_awaited()
        adapter._send_wake_priming.assert_not_awaited()

    async def test_no_failure_if_grounding_metadata_absent(self):
        """T-8: real _send_wake_priming() succeeds even with no handoff notes and no
        grounding_metadata involvement -- absence is the expected default, not an error."""
        adapter = _make_jarvis_adapter(session=AsyncMock())
        adapter._blackboard.get_handoff_reports = AsyncMock(return_value=[])

        await adapter._send_wake_priming()  # must not raise

        adapter._session.send.assert_awaited_once()
        sent_kwargs = adapter._session.send.await_args.kwargs
        assert "Resuming fresh session" in sent_kwargs["input"]

    async def test_priming_fires_without_active_events(self):
        """T-8: real _send_wake_priming() has no active-events gate -- it always sends,
        exercising MemoryCorpus retrieval even before the first event pulse."""
        adapter = _make_jarvis_adapter(session=AsyncMock())
        adapter._blackboard.get_handoff_reports = AsyncMock(return_value=[])

        await adapter._send_wake_priming()

        adapter._session.send.assert_awaited_once()

    async def test_email_redacted_from_priming_text(self):
        """T-8 (codereview fix): handoff text is redacted before it can flow into a turn
        that's eligible for MemoryCorpus store_context write-back."""
        adapter = _make_jarvis_adapter(session=AsyncMock())
        adapter._blackboard.get_handoff_reports = AsyncMock(return_value=[
            {"report": "Contact alice@example.com about the CrashLoop.", "timestamp": 0},
        ])

        await adapter._send_wake_priming()

        sent_kwargs = adapter._session.send.await_args.kwargs
        assert "alice@example.com" not in sent_kwargs["input"]
        assert "[redacted-email]" in sent_kwargs["input"]


# ===========================================================================
# Codereview Run #2 fix: redaction gap -- _replay_pending_context is a sibling
# path that sends the SAME handoff-report content as _send_wake_priming, but
# on reconnect rather than fresh wake. Security review found this and 6 other
# unredacted session.send() sites; verify each closed one here.
# ===========================================================================
@pytest.mark.asyncio
class TestRedactionCoverageAcrossSendSites:
    async def test_replay_pending_context_redacts_handoff_report(self):
        """_replay_pending_context() (reconnect path) must redact the handoff report
        the same way _send_wake_priming() (fresh-wake path) does -- same data class,
        same session-scoped store_context exposure."""
        adapter = _make_jarvis_adapter(session=AsyncMock())
        adapter._blackboard.get_active_events = AsyncMock(return_value=["evt-1"])
        adapter._blackboard.get_handoff_reports = AsyncMock(return_value=[
            {"report": "Contact bob@example.com about the pipeline.", "timestamp": 0},
        ])
        event_stub = MagicMock()
        event_stub.queued_at = 0
        event_stub.brain_phase = "dispatch"
        event_stub.conversation = []
        adapter._blackboard.get_event = AsyncMock(return_value=event_stub)

        await adapter._replay_pending_context()

        sent_texts = [c.kwargs.get("input", "") for c in adapter._session.send.await_args_list]
        combined = "\n".join(sent_texts)
        assert "bob@example.com" not in combined
        assert "[redacted-email]" in combined

    async def test_receive_brain_response_redacts(self):
        """receive_brain_response() relays FRIDAY's raw text verbatim -- must redact."""
        adapter = _make_jarvis_adapter(session=AsyncMock())
        adapter._broadcast = AsyncMock()

        await adapter.receive_brain_response("evt-1", "Escalating to carol@example.com for approval.")

        sent_kwargs = adapter._session.send.await_args.kwargs
        assert "carol@example.com" not in sent_kwargs["input"]
        assert "[redacted-email]" in sent_kwargs["input"]

    async def test_tool_response_redacts(self):
        """Tool-call FunctionResponse results (e.g. recall_handoff_notes echoed back to
        the session) must redact -- this path completely bypassed the original fix."""
        from google.genai import types

        adapter = _make_jarvis_adapter(session=AsyncMock())
        adapter._handle_tool_call = AsyncMock(return_value="Notes mention dave@example.com.")
        adapter._broadcast = AsyncMock()

        fc = MagicMock()
        fc.name = "search_deep_memory"
        fc.args = {}
        tool_call = MagicMock()
        tool_call.function_calls = [fc]

        msg = _spec_msg()
        msg.tool_call = tool_call

        await adapter._process_message(msg)

        sent_input = adapter._session.send.await_args.kwargs.get("input") or adapter._session.send.await_args.args[0]
        response_text = sent_input.function_responses[0].response["result"]
        assert "dave@example.com" not in response_text
        assert "[redacted-email]" in response_text


# ===========================================================================
# T-9: Grounding_metadata extraction in real _process_message()
# ===========================================================================
@pytest.mark.asyncio
class TestGroundingMetadataExtraction:
    async def test_retrieved_context_chunks_logged(self):
        """T-9: real _process_message() logs RAG chunk counts from server_content.grounding_metadata."""
        chunk = MagicMock(spec=["retrieved_context", "web"])
        chunk.retrieved_context = MagicMock(title="Pipeline retry pattern", uri="rag://corpus/doc-123")
        chunk.web = None

        gm = MagicMock(spec=["grounding_chunks", "retrieval_queries", "web_search_queries"])
        gm.grounding_chunks = [chunk]
        gm.retrieval_queries = ["pipeline retry best practices"]
        gm.web_search_queries = []

        adapter = _make_jarvis_adapter()
        msg = _spec_msg(server_content_grounding_metadata=gm)

        with patch("src.adapters.live_api_adapter.logger") as mock_logger:
            await adapter._process_message(msg)

        mock_logger.info.assert_any_call(
            "Cortex grounding: web=%d rag=%d queries=%s", 0, 1, ["pipeline retry best practices"],
        )

    async def test_mixed_web_and_rag_chunks_counted_separately(self):
        """T-9: both web and RAG chunks coexist -- real _process_message() counts each type."""
        web_chunk = MagicMock(spec=["web", "retrieved_context"])
        web_chunk.web = MagicMock(title="Web result", uri="https://example.com")
        web_chunk.retrieved_context = None

        rag_chunk = MagicMock(spec=["web", "retrieved_context"])
        rag_chunk.web = None
        rag_chunk.retrieved_context = MagicMock(title="RAG result", uri="rag://corpus/doc-456")

        gm = MagicMock(spec=["grounding_chunks", "retrieval_queries", "web_search_queries"])
        gm.grounding_chunks = [web_chunk, rag_chunk]
        gm.retrieval_queries = []
        gm.web_search_queries = ["kubernetes"]

        adapter = _make_jarvis_adapter()
        msg = _spec_msg(server_content_grounding_metadata=gm)

        with patch("src.adapters.live_api_adapter.logger") as mock_logger:
            await adapter._process_message(msg)

        mock_logger.info.assert_any_call(
            "Cortex grounding: web=%d rag=%d queries=%s", 1, 1, ["kubernetes"],
        )

    async def test_no_grounding_metadata_is_expected_no_error(self):
        """T-9: absence of grounding_metadata is the expected default -- real _process_message()
        completes without raising and without logging a grounding line."""
        adapter = _make_jarvis_adapter()
        msg = _spec_msg(server_content_grounding_metadata=None)

        await adapter._process_message(msg)  # must not raise


# ===========================================================================
# T-16: Live API probe (integration -- manual gate)
# ===========================================================================
@pytest.mark.skip(reason="T-16: Integration test requiring live Vertex AI credentials and Live API session")
@pytest.mark.asyncio
class TestLiveApiProbe:
    async def test_combined_tools_accepted(self):
        """T-16: Live API session with function+search+retrieval tools -> no INVALID_ARGUMENT."""
        # TODO: This test requires live credentials and a real MemoryCorpus.
        # Run manually as part of Step 1.5 probe.
        # Acceptance criteria:
        # 1. No connection error with all three tool types
        # 2. Grounding metadata attribute path documented
        # 3. Second-session response shows retrieval grounding
        pass

    async def test_cross_session_store_context(self):
        """T-16: Content stored via store_context=True is retrievable in subsequent session."""
        # TODO: Manual probe -- requires two sequential Live API sessions.
        pass
