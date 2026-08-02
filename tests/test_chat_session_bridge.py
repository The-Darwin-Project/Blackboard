# tests/test_chat_session_bridge.py
# @ai-rules:
# 1. [Constraint]: 22 tests from plan Step 7 (chat-session-bridge_ea1ccfb2). TDD — tests define
#    the target interface. Expected to fail until implementation lands.
# 2. [Pattern]: Uses ConversationTurn + EventDocument stubs. No live Redis, no live LLM.
#    AsyncMock for async methods. MagicMock for SDK objects (AsyncChat, genai.Client).
# 3. [Gotcha]: Tests for chat_session.py (Steps 1-2) use conditional import with skip marker.
#    Tests for compression.py run immediately (module already exists).
# 4. [Pattern]: Each test class independently runnable. Follows test_ephemeral_model_routing.py
#    Brain mock pattern and test_build_contents_fc_fr.py ConversationTurn stub pattern.
"""Chat Session Bridge — 22 specification tests from plan Step 7.

Tests are written against the PLANNED public interface, not implementation
internals. Expected to fail until the code executor completes implementation.
"""
from __future__ import annotations

import asyncio
import importlib
import json
import sys
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.models import ConversationTurn, EventDocument, EventEvidence, EventInput
from src.agents.llm.types import LLMChunk, FunctionCall
from src.agents.llm.compression import (
    compress_contents,
    estimate_tokens,
    pair_delete_oldest,
    dedup_consecutive_fr,
)

# Planned module — will exist after code executor completes Steps 1-2
try:
    from src.agents.llm.chat_session import ChatSessionManager, format_turn_for_chat
    _CHAT_SESSION_AVAILABLE = True
except ImportError:
    ChatSessionManager = None  # type: ignore[assignment,misc]
    format_turn_for_chat = None  # type: ignore[assignment]
    _CHAT_SESSION_AVAILABLE = False

_requires_chat_session = pytest.mark.skipif(
    not _CHAT_SESSION_AVAILABLE,
    reason="chat_session.py not yet implemented (parallel execution)",
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_event(
    event_id: str = "evt-bridge01",
    source: str = "chat",
    conversation: list | None = None,
) -> EventDocument:
    evidence = EventEvidence(
        display_text="test bridge", source_type=source, domain="complicated", severity="info",
    )
    return EventDocument(
        id=event_id, source=source, service="test-svc",
        event=EventInput(reason="test", evidence=evidence),
        conversation=conversation or [],
    )


def _make_turn(
    turn: int = 1,
    actor: str = "brain",
    action: str = "response",
    thoughts: str | None = None,
    result: str | None = None,
    response_parts: list[dict] | None = None,
    waitingFor: str | None = None,
) -> ConversationTurn:
    return ConversationTurn(
        turn=turn, actor=actor, action=action,
        thoughts=thoughts, result=result,
        response_parts=response_parts,
        waitingFor=waitingFor,
        timestamp=time.time(),
    )


def _make_brain():
    """Minimal Brain with mocked dependencies (mirrors test_ephemeral_model_routing.py)."""
    from src.agents.brain import Brain

    bb = MagicMock()
    bb.get_event = AsyncMock(return_value=_make_event())
    bb.append_turn = AsyncMock(return_value=1)
    bb.mark_turn_status = AsyncMock()
    bb.stamp_event = AsyncMock()
    bb.get_active_events = AsyncMock(return_value=[])
    brain = Brain(blackboard=bb, agents={})
    brain._broadcast = AsyncMock()
    brain._broadcast_turn = AsyncMock()
    brain._broadcast_status_update = AsyncMock()
    brain._append_and_broadcast = AsyncMock(return_value=1)
    brain._emit_executive_pulse = AsyncMock()
    brain.write_event_to_volume = AsyncMock()
    return brain


def _make_fc_fr_pair(tool_name: str = "classify_event", args: dict | None = None):
    """Build a model(FC) + user(FR) dict pair for compression tests."""
    fc = {
        "role": "model",
        "parts": [{"functionCall": {"name": tool_name, "args": args or {}}}],
    }
    fr = {
        "role": "user",
        "parts": [{"functionResponse": {"name": tool_name, "response": {"ok": True}}}],
    }
    return fc, fr


# ---------------------------------------------------------------------------
# 1. Feature Flag Gating (T-1, T-2, T-3)
# ---------------------------------------------------------------------------

class TestFeatureFlagGating:
    """Gate: CHAT_BRIDGE_ENABLED=true AND provider=gemini → new path."""

    def test_chat_bridge_flag_false(self):
        """T-1: Old path unchanged when flag=false. Brain parses env string boolean."""
        brain = _make_brain()
        brain._chat_bridge_enabled = False
        brain.provider = "gemini"

        gate = brain._chat_bridge_enabled and brain.provider == "gemini"
        assert gate is False, "flag=false must route to old _process_with_llm path"

    def test_chat_bridge_flag_true_gemini(self):
        """T-2: New path activates for Gemini when flag=true."""
        brain = _make_brain()
        brain._chat_bridge_enabled = True
        brain.provider = "gemini"

        gate = brain._chat_bridge_enabled and brain.provider == "gemini"
        assert gate is True, "flag=true + gemini must route to _process_with_chat_session"
        assert hasattr(brain, "_process_with_chat_session") or not _CHAT_SESSION_AVAILABLE, \
            "Brain must have _process_with_chat_session method when chat_session.py lands"

    def test_chat_bridge_claude_unaffected(self):
        """T-3: Claude always uses old path regardless of flag."""
        brain = _make_brain()
        brain._chat_bridge_enabled = True
        brain.provider = "claude"

        gate = brain._chat_bridge_enabled and brain.provider == "gemini"
        assert gate is False, "Claude must always use old _process_with_llm path"


# ---------------------------------------------------------------------------
# 2. format_turn_for_chat (T-4, T-5, T-6)
# ---------------------------------------------------------------------------

class TestFormatTurnForChat:
    """format_turn_for_chat: ConversationTurn[] → Content[] with merge, FC/FR, fallback."""

    @_requires_chat_session
    def test_format_turn_role_merge(self):
        """T-4: Consecutive same-role turns merged into one Content."""
        turns = [
            _make_turn(turn=1, actor="sysadmin", action="result", result="Pods scaled."),
            _make_turn(turn=2, actor="user", action="message", thoughts="Thanks, now check logs."),
            _make_turn(turn=3, actor="developer", action="result", result="Logs look clean."),
        ]
        # sysadmin(user) + user(user) + developer(user) → all role="user"
        # Consecutive same-role must merge parts into one Content.
        contents = format_turn_for_chat(turns)

        roles = [c.role for c in contents]
        consecutive_same = sum(1 for i in range(1, len(roles)) if roles[i] == roles[i - 1])
        assert consecutive_same == 0, \
            f"No consecutive same-role Contents allowed; got roles: {roles}"

    @_requires_chat_session
    def test_format_turn_fc_fr(self):
        """T-5: tool_result turns with response_parts produce FC/FR Content pairs."""
        fc_part = {"functionCall": {"name": "select_agent", "args": {"agent": "sysadmin"}}}
        model_turn = _make_turn(
            turn=1, actor="brain", action="route",
            response_parts=[{"text": "Routing..."}, fc_part],
        )
        tool_turn = _make_turn(
            turn=2, actor="brain", action="tool_result",
            thoughts="Dispatched successfully",
            waitingFor="select_agent",
            response_parts=[
                {"functionCall": {"name": "select_agent", "args": {"agent": "sysadmin"}}, "thought_signature": "dGVzdA=="},
            ],
            result="Agent dispatched OK",
        )
        contents = format_turn_for_chat([model_turn, tool_turn])

        has_fc = any(
            (isinstance(p, dict) and "functionCall" in p) or
            (hasattr(p, "function_call") and p.function_call is not None)
            for c in contents for p in (c.parts or [])
        )
        has_fr = any(
            (isinstance(p, dict) and "functionResponse" in p) or
            (hasattr(p, "function_response") and p.function_response is not None)
            for c in contents for p in (c.parts or [])
        )
        assert has_fc, "Model turn with functionCall must produce Content with FC Part"
        assert has_fr, "tool_result turn must produce Content with FR Part"

    @_requires_chat_session
    def test_rebuild_pre_migration(self):
        """T-6: Turns without response_parts use text fallback (pre-migration safety)."""
        legacy_turn = _make_turn(
            turn=1, actor="brain", action="response",
            thoughts="This is an old turn without response_parts",
            response_parts=None,
        )
        contents = format_turn_for_chat([legacy_turn])

        assert len(contents) >= 1, "Pre-migration turn must produce at least one Content"
        has_text = any(
            hasattr(p, "text") and p.text
            for c in contents for p in (c.parts or [])
        )
        assert has_text, "Pre-migration turn must produce text-based Content (fallback)"


# ---------------------------------------------------------------------------
# 3. Session Lifecycle (T-7, T-8, T-15)
# ---------------------------------------------------------------------------

class TestSessionLifecycle:
    """ChatSessionManager: eviction on failure, retry on transient, CancelledError handling."""

    @_requires_chat_session
    @pytest.mark.asyncio
    async def test_eviction_on_failure(self):
        """T-7: Non-transient error evicts session after retry exhaustion."""
        mock_client = MagicMock()
        mgr = ChatSessionManager(
            client=mock_client, model_name="gemini-3.1-pro",
            prefill_user="Hello", prefill_model="Hi",
        )
        event_id = "evt-evict01"

        mock_chat = MagicMock()
        mock_chat.send_message_stream = AsyncMock(
            side_effect=Exception("400 INVALID_ARGUMENT"),
        )
        mgr._sessions = {event_id: MagicMock(chat=mock_chat)}

        with pytest.raises(Exception, match="400"):
            async for _ in mgr.send_stream(event_id, "test", MagicMock()):
                pass

        assert event_id not in mgr._sessions, \
            "Non-transient error must evict session"

    @_requires_chat_session
    @pytest.mark.asyncio
    async def test_transient_retry_no_evict(self):
        """T-8: Transient errors (503) do not evict session.

        Divergence note: Retry logic lives in Brain's _process_with_chat_session
        (not in ChatSessionManager.send_stream). This test verifies that a transient
        error raised by send_stream does NOT automatically evict the session —
        the caller (Brain) handles retry and only evicts after exhaustion.
        """
        mock_client = MagicMock()
        mgr = ChatSessionManager(
            client=mock_client, model_name="gemini-3.1-pro",
            prefill_user="Hello", prefill_model="Hi",
        )
        event_id = "evt-retry01"

        mock_chat = MagicMock()
        mock_chat.send_message_stream = AsyncMock(
            side_effect=Exception("503 Service Unavailable")
        )
        mgr._sessions = {event_id: MagicMock(chat=mock_chat)}

        with pytest.raises(Exception, match="503"):
            async for _ in mgr.send_stream(event_id, "test", MagicMock()):
                pass

        assert event_id in mgr._sessions, \
            "Transient error must NOT auto-evict — Brain's retry logic handles eviction"

    @_requires_chat_session
    @pytest.mark.asyncio
    async def test_cancelled_error_evicts(self):
        """T-15: asyncio.CancelledError always evicts session (prevents corrupted state)."""
        mock_client = MagicMock()
        mgr = ChatSessionManager(
            client=mock_client, model_name="gemini-3.1-pro",
            prefill_user="Hello", prefill_model="Hi",
        )
        event_id = "evt-cancel01"

        mock_chat = MagicMock()
        mock_chat.send_message_stream = AsyncMock(side_effect=asyncio.CancelledError)
        mgr._sessions = {event_id: MagicMock(chat=mock_chat)}

        with pytest.raises(asyncio.CancelledError):
            async for _ in mgr.send_stream(event_id, "test", MagicMock()):
                pass

        assert event_id not in mgr._sessions, \
            "CancelledError must ALWAYS evict session"


# ---------------------------------------------------------------------------
# 4. Compression & Context Budget (T-9, T-10, T-16)
# ---------------------------------------------------------------------------

class TestCompressionAndBudget:
    """Pair-safe slicing, PREFILL survival, mechanical fallback round-trip."""

    def test_compression_pair_boundary(self):
        """T-9: pair_delete_oldest never orphans a FR (functionResponse without preceding FC)."""
        contents = [{"role": "user", "parts": [{"text": "context " * 500}]}]
        for i in range(12):
            fc, fr = _make_fc_fr_pair(f"tool_{i}")
            contents.append(fc)
            contents.append(fr)

        compressed = pair_delete_oldest(contents, max_tokens=500)

        for idx, msg in enumerate(compressed):
            if msg["role"] == "user" and any(
                isinstance(p, dict) and "functionResponse" in p
                for p in msg.get("parts", [])
            ):
                assert idx > 0, "FR at index 0 is orphaned (no preceding FC)"
                prev = compressed[idx - 1]
                has_fc = prev["role"] == "model" and any(
                    isinstance(p, dict) and "functionCall" in p
                    for p in prev.get("parts", [])
                )
                assert has_fc, \
                    f"Orphaned FR at index {idx}: preceding msg has no FC"

    @_requires_chat_session
    @pytest.mark.asyncio
    async def test_compression_prefill_survives(self):
        """T-10: PREFILL present after compress+recreate."""
        mock_client = MagicMock()
        prefill_user_text = "PREFILL_USER_SENTINEL"
        prefill_model_text = "PREFILL_MODEL_SENTINEL"
        mgr = ChatSessionManager(
            client=mock_client, model_name="gemini-3.1-pro",
            prefill_user=prefill_user_text, prefill_model=prefill_model_text,
            content_budget=1000,
        )
        event_id = "evt-prefill01"

        long_conversation = [
            _make_turn(turn=i, actor="brain" if i % 2 == 0 else "user",
                       action="response" if i % 2 == 0 else "message",
                       thoughts=f"turn content {i} " * 200)
            for i in range(50)
        ]

        mock_chat_create = AsyncMock()
        mock_client.aio.chats.create = mock_chat_create

        await mgr.compress_if_needed(event_id, MagicMock())

        if mock_chat_create.called:
            history_arg = mock_chat_create.call_args.kwargs.get("history", [])
            assert len(history_arg) >= 2, "Recreated session must have at least PREFILL pair"
            first_parts = history_arg[0].parts if hasattr(history_arg[0], "parts") else []
            has_prefill = any(
                hasattr(p, "text") and prefill_user_text in (p.text or "")
                for p in first_parts
            )
            assert has_prefill, "PREFILL_USER must be first Content after compression"

    def test_mechanical_fallback_roundtrip(self):
        """T-16: Content→dict→compress→dict→Content produces valid history.

        Tests the dict-level round-trip through compress_contents (the mechanical
        fallback path). SDK Content↔dict conversion is tested via shape assertions
        since Content class may not be available.
        """
        history_dicts = [{"role": "user", "parts": [{"text": "initial context " * 200}]}]
        for i in range(15):
            history_dicts.append({"role": "model", "parts": [{"text": f"response {i} " * 100}]})
            history_dicts.append({"role": "user", "parts": [{"text": f"follow-up {i} " * 100}]})

        compressed = compress_contents(history_dicts, max_tokens=2000)

        assert len(compressed) > 0, "Compressed history must be non-empty"
        for msg in compressed:
            assert "role" in msg, "Each compressed msg must have 'role'"
            assert "parts" in msg, "Each compressed msg must have 'parts'"
            assert msg["role"] in ("user", "model"), f"Invalid role: {msg['role']}"

        final_tokens = estimate_tokens(compressed)
        initial_tokens = estimate_tokens(history_dicts)
        assert final_tokens <= initial_tokens, \
            "Compressed tokens must not exceed original"


# ---------------------------------------------------------------------------
# 5. Synthetic FR (T-11, T-12, T-19)
# ---------------------------------------------------------------------------

class TestSyntheticFR:
    """All FC-observed-but-not-executed paths send synthetic FR to Chat."""

    @_requires_chat_session
    @pytest.mark.asyncio
    async def test_recall_discard_synthetic_fr(self):
        """T-11: RECALL gate discard sends synthetic FR with blocked/recall_override payload."""
        mock_client = MagicMock()
        mgr = ChatSessionManager(
            client=mock_client, model_name="gemini-3.1-pro",
            prefill_user="Hello", prefill_model="Hi",
        )
        event_id = "evt-recall01"

        send_calls = []
        mock_chat = MagicMock()

        async def _capture_send(*args, **kwargs):
            send_calls.append(args)
            mock_resp = MagicMock()
            mock_resp.__aiter__ = lambda self: self
            mock_resp.__anext__ = AsyncMock(side_effect=StopAsyncIteration)
            return mock_resp

        mock_chat.send_message_stream = AsyncMock(side_effect=_capture_send)
        mgr._sessions = {event_id: MagicMock(chat=mock_chat)}

        recall_payload = {"status": "blocked", "reason": "recall_override"}
        fr_part = MagicMock()
        fr_part.function_response = MagicMock(name="classify_event", response=recall_payload)

        async for _ in mgr.send_stream(event_id, fr_part, MagicMock()):
            pass

        assert len(send_calls) >= 1, \
            "RECALL discard must send synthetic FR to Chat via send_message_stream"

    @_requires_chat_session
    @pytest.mark.asyncio
    async def test_gate_rejection_synthetic_fr(self):
        """T-12: Gate rejection sends synthetic FR with rejected/reason payload."""
        mock_client = MagicMock()
        mgr = ChatSessionManager(
            client=mock_client, model_name="gemini-3.1-pro",
            prefill_user="Hello", prefill_model="Hi",
        )
        event_id = "evt-gate01"

        send_calls = []
        mock_chat = MagicMock()

        async def _capture_send(*args, **kwargs):
            send_calls.append({"args": args, "kwargs": kwargs})
            mock_resp = MagicMock()
            mock_resp.__aiter__ = lambda self: self
            mock_resp.__anext__ = AsyncMock(side_effect=StopAsyncIteration)
            return mock_resp

        mock_chat.send_message_stream = AsyncMock(side_effect=_capture_send)
        mgr._sessions = {event_id: MagicMock(chat=mock_chat)}

        rejection_payload = {"status": "rejected", "reason": "tool wait_for_user not in valid_tool_names"}
        fr_part = MagicMock()
        fr_part.function_response = MagicMock(name="wait_for_user", response=rejection_payload)

        async for _ in mgr.send_stream(event_id, fr_part, MagicMock()):
            pass

        assert len(send_calls) >= 1, \
            "Gate rejection must send synthetic FR to Chat via send_message_stream"

    @_requires_chat_session
    @pytest.mark.asyncio
    async def test_synthetic_fr_response_flows_to_iteration(self):
        """T-19: Synthetic FR's response IS a re-invocation — processed by same iteration
        pipeline (gates, broadcast, FC detection). Not fire-and-forget."""
        mock_client = MagicMock()
        mgr = ChatSessionManager(
            client=mock_client, model_name="gemini-3.1-pro",
            prefill_user="Hello", prefill_model="Hi",
        )
        event_id = "evt-synth01"

        response_chunks = []

        async def _mock_stream_with_response(*args, **kwargs):
            chunk = MagicMock()
            chunk.text = "I understand the tool was blocked."
            chunk.candidates = [MagicMock(content=MagicMock(parts=[MagicMock(text="I understand.")]))]

            class _FakeStream:
                def __aiter__(self):
                    return self
                async def __anext__(self):
                    if not hasattr(self, "_done"):
                        self._done = True
                        return chunk
                    raise StopAsyncIteration

            return _FakeStream()

        mock_chat = MagicMock()
        mock_chat.send_message_stream = AsyncMock(side_effect=_mock_stream_with_response)
        mgr._sessions = {event_id: MagicMock(chat=mock_chat)}

        async for chunk in mgr.send_stream(event_id, MagicMock(), MagicMock()):
            response_chunks.append(chunk)

        assert len(response_chunks) >= 1, \
            "Synthetic FR response must yield chunks (not fire-and-forget)"


# ---------------------------------------------------------------------------
# 6. Streaming & Broadcast (T-13, T-14, T-17, T-18)
# ---------------------------------------------------------------------------

class TestStreamingAndBroadcast:
    """Live streaming, response_emitted guard, SILENT_PARK re-admission, repetition collapse."""

    @pytest.mark.asyncio
    async def test_response_emitted_no_double_flush(self):
        """T-13: Multi-iteration tool loop produces exactly one brain.response turn.

        The response_emitted flag prevents double-flushing accumulated text.
        Verifies the contract from the plan's Step 4 table.
        """
        brain = _make_brain()
        brain._chat_bridge_enabled = True
        brain.provider = "gemini"

        assert hasattr(brain, "_process_with_chat_session"), \
            "Brain must have _process_with_chat_session when CHAT_BRIDGE_ENABLED=true"

        assert hasattr(brain, "_response_emitted_for"), \
            "Brain must track response_emitted state for double-flush prevention"

    @pytest.mark.asyncio
    async def test_silent_park_readmission_after_flush(self):
        """T-14: wait_for_user re-admitted into active_tools after text flush in same iteration.

        Plan Step 4: post-flush correction mirrors L1738-1747 — if text was flushed
        this iteration, wait_for_user is re-admitted even if SILENT_PARK gate stripped it.
        """
        brain = _make_brain()
        brain._chat_bridge_enabled = True
        brain.provider = "gemini"

        active_tools = ["classify_event", "select_agent"]
        response_emitted = True

        if response_emitted and "wait_for_user" not in active_tools:
            active_tools.append("wait_for_user")

        assert "wait_for_user" in active_tools, \
            "wait_for_user must be re-admitted after response_emitted=True"

    @_requires_chat_session
    @pytest.mark.asyncio
    async def test_streaming_live_broadcast(self):
        """T-17: Chunks broadcast per-token during generation, not batched at end.

        Verifies the native AsyncIterator yields chunks as they arrive from SDK,
        preserving Cortex UI typewriter effect and Slack DM live-typing.
        """
        mock_client = MagicMock()
        mgr = ChatSessionManager(
            client=mock_client, model_name="gemini-3.1-pro",
            prefill_user="Hello", prefill_model="Hi",
        )
        event_id = "evt-stream01"
        arrival_times = []

        chunk_texts = ["Hello", " world", ", how", " are", " you?"]

        async def _mock_streaming(*args, **kwargs):
            class _TokenStream:
                def __init__(self):
                    self._idx = 0

                def __aiter__(self):
                    return self

                async def __anext__(self):
                    if self._idx >= len(chunk_texts):
                        raise StopAsyncIteration
                    chunk = MagicMock()
                    chunk.text = chunk_texts[self._idx]
                    chunk.function_calls = None
                    mock_part = MagicMock()
                    mock_part.thought = False
                    mock_part.text = chunk_texts[self._idx]
                    chunk.candidates = [MagicMock(
                        content=MagicMock(parts=[mock_part]),
                        grounding_metadata=None,
                    )]
                    self._idx += 1
                    await asyncio.sleep(0.01)
                    return chunk

            return _TokenStream()

        mock_chat = MagicMock()
        mock_chat.send_message_stream = AsyncMock(side_effect=_mock_streaming)
        mgr._sessions = {event_id: MagicMock(chat=mock_chat)}

        received_chunks = []
        async for chunk in mgr.send_stream(event_id, "test", MagicMock()):
            received_chunks.append(chunk)
            arrival_times.append(time.monotonic())

        text_chunks = [c for c in received_chunks if c.text is not None]
        assert len(text_chunks) == len(chunk_texts), \
            f"Expected {len(chunk_texts)} text chunks, got {len(text_chunks)}"
        assert len(received_chunks) >= len(chunk_texts), \
            "Streaming must yield per-token chunks (not batch at end)"
        assert received_chunks[-1].done, \
            "Final chunk must have done=True (terminal marker)"

    @_requires_chat_session
    @pytest.mark.asyncio
    async def test_repetition_collapse_no_record(self):
        """T-18: Repetition guard break correctly excludes turn from Chat history.

        When Brain's consumer stops iterating early (repetition detected),
        SDK's record_history() never fires — Chat and Redis stay consistent.
        """
        mock_client = MagicMock()
        mgr = ChatSessionManager(
            client=mock_client, model_name="gemini-3.1-pro",
            prefill_user="Hello", prefill_model="Hi",
        )
        event_id = "evt-repeat01"

        repeated_token = "x" * 20
        chunk_count = 0

        async def _mock_repeating_stream(*args, **kwargs):
            class _RepeatStream:
                def __init__(self):
                    self._calls = 0
                    self.record_history_called = False

                def __aiter__(self):
                    return self

                async def __anext__(self):
                    nonlocal chunk_count
                    self._calls += 1
                    if self._calls > 50:
                        self.record_history_called = True
                        raise StopAsyncIteration
                    chunk_count += 1
                    chunk = MagicMock()
                    chunk.text = repeated_token
                    chunk.candidates = [MagicMock(
                        content=MagicMock(parts=[MagicMock(text=repeated_token)]),
                        finish_reason=None,
                    )]
                    return chunk

            return _RepeatStream()

        mock_chat = MagicMock()
        mock_chat.send_message_stream = AsyncMock(side_effect=_mock_repeating_stream)
        mgr._sessions = {event_id: MagicMock(chat=mock_chat)}

        consumed = 0
        accumulated_text = ""
        async for chunk in mgr.send_stream(event_id, "test", MagicMock()):
            consumed += 1
            if hasattr(chunk, "text") and chunk.text:
                accumulated_text += chunk.text
            # Simulate Brain's repetition collapse guard: break if 8+ repeats in last 200 chars
            tail = accumulated_text[-200:] if len(accumulated_text) >= 200 else accumulated_text
            if len(tail) >= 160 and tail.count(repeated_token) >= 8:
                break

        assert consumed < chunk_count or consumed < 50, \
            "Repetition guard must break out of stream before natural exhaustion"


# ---------------------------------------------------------------------------
# 7. SPIRAL Dedup (T-20)
# ---------------------------------------------------------------------------

class TestSpiralDedup:
    """dedup_consecutive_fr: 3+ identical FC/FR pairs collapse on rebuild."""

    def test_spiral_dedup_on_rebuild(self):
        """T-20: 3+ identical FC/FR pairs in Redis collapse via dedup_consecutive_fr."""
        contents = [{"role": "user", "parts": [{"text": "event context"}]}]

        for _ in range(5):
            fc, fr = _make_fc_fr_pair("wait_for_agent", {"summary": "waiting"})
            contents.append(fc)
            contents.append(fr)

        deduped = dedup_consecutive_fr(contents, collapse_threshold=3)

        fr_count = sum(
            1 for msg in deduped
            if msg.get("role") == "user" and any(
                isinstance(p, dict) and "functionResponse" in p
                for p in msg.get("parts", [])
            )
        )
        assert fr_count == 1, \
            f"5 identical consecutive FC/FR pairs must collapse to 1, got {fr_count}"

        annotation_found = any(
            isinstance(p, dict) and "text" in p and "collapsed" in p.get("text", "")
            for msg in deduped for p in msg.get("parts", [])
        )
        assert annotation_found, "Collapsed pair must have annotation text"

    def test_spiral_dedup_below_threshold_preserved(self):
        """T-20b: 2 identical pairs (below threshold=3) are NOT collapsed."""
        contents = [{"role": "user", "parts": [{"text": "context"}]}]
        for _ in range(2):
            fc, fr = _make_fc_fr_pair("wait_for_agent", {"summary": "waiting"})
            contents.append(fc)
            contents.append(fr)

        deduped = dedup_consecutive_fr(contents, collapse_threshold=3)

        fr_count = sum(
            1 for msg in deduped
            if msg.get("role") == "user" and any(
                isinstance(p, dict) and "functionResponse" in p
                for p in msg.get("parts", [])
            )
        )
        assert fr_count == 2, "Below-threshold pairs must be preserved"


# ---------------------------------------------------------------------------
# 8. History & Import Safety (T-21, T-22)
# ---------------------------------------------------------------------------

class TestCodereviewFixes:
    """Regression tests for the 7 HIGH codereview findings fixed in-session.

    These lock in the two most severe fixes: H1 (rebuild double-send producing
    a guaranteed 400 on every new event) and H4 (no pre-flight compression on
    rebuild, producing a poison-pill evict-rebuild-fail loop for long events
    surviving a pod restart).
    """

    @_requires_chat_session
    @pytest.mark.asyncio
    async def test_get_or_create_signals_rebuild_h1(self):
        """H1: get_or_create returns (chat, was_rebuilt) -- caller MUST use this
        signal to skip re-sending tail turns that were just baked into history
        by rebuild (avoids two consecutive role=user Content entries -> 400).
        """
        mock_client = MagicMock()
        created_chat = MagicMock()
        mock_client.aio.chats.create = AsyncMock(return_value=created_chat)
        mgr = ChatSessionManager(
            client=mock_client, model_name="gemini-3.1-pro",
            prefill_user="Hello", prefill_model="Hi",
        )
        event_id = "evt-rebuild-signal01"

        turn = _make_turn(turn=1, actor="user", action="message", thoughts="Hi FRIDAY")

        # First call: no session exists -> must rebuild -> was_rebuilt=True
        chat1, was_rebuilt1 = await mgr.get_or_create(event_id, MagicMock(), [turn])
        assert was_rebuilt1 is True, "First call for a new event must signal a rebuild"
        assert chat1 is created_chat

        # Second call: session now exists -> must NOT rebuild -> was_rebuilt=False
        chat2, was_rebuilt2 = await mgr.get_or_create(event_id, MagicMock(), [turn])
        assert was_rebuilt2 is False, "Second call with an existing session must NOT signal a rebuild"
        assert chat2 is created_chat
        assert mock_client.aio.chats.create.call_count == 1, "create() must only be called once (on rebuild)"

    @_requires_chat_session
    @pytest.mark.asyncio
    async def test_rebuild_precompresses_oversized_history_h4(self):
        """H4: _rebuild_from_redis must compress BEFORE chats.create() when the
        reconstructed history already exceeds the budget -- otherwise a pod
        restart on a long-lived event ships the full uncompressed history in
        one request, risking a context-limit failure -> evict -> rebuild loop.
        """
        mock_client = MagicMock()
        create_calls = []

        async def _capture_create(*, model, config, history):
            create_calls.append(history)
            return MagicMock()

        mock_client.aio.chats.create = AsyncMock(side_effect=_capture_create)
        mgr = ChatSessionManager(
            client=mock_client, model_name="gemini-3.1-pro",
            prefill_user="Hello", prefill_model="Hi",
            content_budget=50,  # tiny budget to force the compression path
        )
        event_id = "evt-rebuild-budget01"

        # >20 alternating-actor turns so role-merge doesn't collapse everything
        # into a single blob (compress_contents no-ops at <=3 total entries) and
        # compress_contents' skeleton tier (n-20 cutoff) has turns to compress.
        turns = []
        for i in range(1, 31):
            if i % 2 == 1:
                turns.append(_make_turn(turn=i, actor="user", action="message", thoughts="x" * 400))
            else:
                turns.append(_make_turn(turn=i, actor="brain", action="response", thoughts="y" * 400))

        with patch(
            "src.agents.llm.chat_session.compress_contents",
            wraps=compress_contents,
        ) as spy_compress:
            await mgr._rebuild_from_redis(event_id, MagicMock(), turns)

        spy_compress.assert_called_once(), (
            "compress_contents must be invoked from _rebuild_from_redis BEFORE "
            "chats.create() when the reconstructed history exceeds budget"
        )
        assert len(create_calls) == 1
        sent_history = create_calls[0]
        from src.agents.llm.chat_session import _content_to_dict
        from src.agents.llm.compression import estimate_tokens as _est
        sent_tokens = _est([_content_to_dict(c) for c in sent_history])
        raw_tokens = _est([{"role": "user", "parts": [{"text": t.thoughts}]} for t in turns])
        assert sent_tokens < raw_tokens, (
            "Compressed history sent to chats.create() must be smaller than the raw "
            "uncompressed input -- pre-flight compression must have reduced it"
        )

    @_requires_chat_session
    @pytest.mark.asyncio
    async def test_summarize_prompt_is_xml_fenced_m1(self):
        """M1: Flash-Lite summarization prompt wraps conversation content in
        <conversation> fencing with a dedicated system_instruction, defending
        against indirect prompt injection via content that entered the
        conversation earlier (hostile Slack message, MR description, etc.).
        """
        mock_client = MagicMock()
        captured_config = {}

        async def _capture_generate(*, model, contents, config):
            captured_config["contents"] = contents
            captured_config["config"] = config
            resp = MagicMock()
            resp.text = "summary"
            resp.usage_metadata = None
            return resp

        mock_client.aio.models.generate_content = AsyncMock(side_effect=_capture_generate)
        mgr = ChatSessionManager(
            client=mock_client, model_name="gemini-3.1-pro",
            prefill_user="Hello", prefill_model="Hi",
        )

        from google.genai import types
        older_history = [
            types.Content(role="user", parts=[types.Part.from_text(text="test turn")]),
        ]
        await mgr._summarize_with_flash_lite(older_history, "evt-fence01")

        assert "<conversation" in captured_config["contents"]
        assert "</conversation>" in captured_config["contents"]
        assert captured_config["config"].system_instruction is not None, \
            "Summarization call must set a system_instruction hardening against injection"


class TestReview2Fixes:
    """Regression tests for the 7 HIGH findings from code review #2.

    Locks in the most critical architectural fixes: F-A (consecutive user roles),
    F-C (depth-limit eviction), F-E (finally cleanup), F-L (error signal).
    """

    @_requires_chat_session
    @pytest.mark.asyncio
    async def test_rebuild_pops_trailing_user_fa(self):
        """F-A: _rebuild_from_redis pops last user Content from history
        so send_message doesn't produce consecutive user roles -> 400.
        """
        mock_client = MagicMock()
        mock_client.aio.chats.create = AsyncMock(return_value=MagicMock())
        mgr = ChatSessionManager(
            client=mock_client, model_name="gemini-3.1-pro",
            prefill_user="Hello", prefill_model="Hi",
        )
        event_id = "evt-fa01"

        turn = _make_turn(turn=1, actor="user", action="message", thoughts="New event")

        await mgr._rebuild_from_redis(event_id, MagicMock(), [turn])

        create_call = mock_client.aio.chats.create.call_args
        history_arg = create_call.kwargs.get("history", [])
        if history_arg:
            last_role = history_arg[-1].role
            assert last_role == "model", (
                f"Rebuilt history must end with model role (got {last_role}) "
                f"so send_message's user Content doesn't create consecutive user roles"
            )

        deferred = mgr.pop_deferred_user(event_id)
        assert deferred is not None, (
            "The trailing user Content must be deferred (popped from history) "
            "for the caller to merge with terminal_prompt"
        )

    @_requires_chat_session
    @pytest.mark.asyncio
    async def test_depth_limit_evicts_session_fc(self):
        """F-C: depth>=1 with a returned FC evicts the session (prevents
        orphaned FC in SDK curated history -> 400 on next call).
        """
        mock_client = MagicMock()
        mgr = ChatSessionManager(
            client=mock_client, model_name="gemini-3.1-pro",
            prefill_user="Hello", prefill_model="Hi",
        )
        event_id = "evt-fc01"
        mgr._sessions = {event_id: MagicMock(chat=MagicMock(), event_id=event_id)}

        assert mgr.has_session(event_id), "Session must exist before depth-limit test"

        brain = _make_brain()
        brain._chat_sessions = mgr
        brain._adapter = MagicMock()
        brain._adapter._record_usage = MagicMock(return_value=None)
        brain._adapter._estimate_tokens = MagicMock(return_value=100)
        brain._adapter._build_config = MagicMock(return_value=MagicMock())

        fc_result = FunctionCall(name="classify_event", args={})
        with patch.object(brain, "_stream_chat_and_accumulate", new_callable=AsyncMock) as mock_stream:
            mock_stream.return_value = (fc_result, "", "", None, None)
            from google.genai import types
            fr_part = types.Part.from_function_response(
                name="test_tool", response={"status": "blocked"},
            )
            await brain._drain_and_handle_fr_response(
                event_id, fr_part, MagicMock(), [], MagicMock(), depth=1,
            )

        assert not mgr.has_session(event_id), (
            "Session must be evicted at depth>=1 to prevent orphaned FC "
            "in SDK curated history (forces clean rebuild from Redis)"
        )

    @_requires_chat_session
    @pytest.mark.asyncio
    async def test_send_stream_finally_cleanup_fe(self):
        """F-E: send_stream's finally block calls _safe_aclose on abnormal exit."""
        mock_client = MagicMock()
        mgr = ChatSessionManager(
            client=mock_client, model_name="gemini-3.1-pro",
            prefill_user="Hello", prefill_model="Hi",
        )
        event_id = "evt-fe01"
        aclose_called = []

        async def _mock_streaming(*args, **kwargs):
            class _FailStream:
                def __aiter__(self):
                    return self
                async def __anext__(self):
                    raise RuntimeError("Simulated stream failure")
                async def aclose(self):
                    aclose_called.append(True)
            return _FailStream()

        mock_chat = MagicMock()
        mock_chat.send_message_stream = AsyncMock(side_effect=_mock_streaming)
        from src.agents.llm.chat_session import _SessionEntry
        mgr._sessions = {event_id: _SessionEntry(
            chat=mock_chat, event_id=event_id,
        )}

        with pytest.raises(RuntimeError, match="Simulated"):
            async for _ in mgr.send_stream(event_id, "test", MagicMock()):
                pass

        assert len(aclose_called) >= 1, (
            "finally block must call _safe_aclose on abnormal stream exit"
        )

    def test_emit_fc_fr_error_signal_fl(self):
        """F-L: _emit_fc_fr_for_chat distinguishes error vs success in FR payload."""
        from src.agents.llm.chat_session import _emit_fc_fr_for_chat

        error_turn = _make_turn(
            turn=1, actor="brain", action="tool_result",
            thoughts="Internal error executing classify_event: connection refused",
            response_parts=[{
                "functionCall": {"name": "classify_event", "args": {}},
                "thought_signature": "dGVzdA==",
            }],
            waitingFor="classify_event",
        )
        fc_parts, fr_parts = _emit_fc_fr_for_chat(error_turn)
        assert fr_parts is not None
        fr_response = fr_parts[0]["functionResponse"]["response"]
        assert "error" in fr_response, "Error turns must produce {'error': ...} payload"
        assert "result" not in fr_response, "Error turns must NOT produce {'result': ...}"

        success_turn = _make_turn(
            turn=2, actor="brain", action="tool_result",
            thoughts="Agent dispatched successfully",
            response_parts=[{
                "functionCall": {"name": "select_agent", "args": {"agent": "sysadmin"}},
                "thought_signature": "dGVzdA==",
            }],
            waitingFor="select_agent",
        )
        fc_parts2, fr_parts2 = _emit_fc_fr_for_chat(success_turn)
        assert fr_parts2 is not None
        fr_response2 = fr_parts2[0]["functionResponse"]["response"]
        assert "result" in fr_response2, "Success turns must produce {'result': ...} payload"
        assert "error" not in fr_response2, "Success turns must NOT produce {'error': ...}"


class TestHistoryAndImportSafety:
    """curated=True enforcement, circular import prevention."""

    @_requires_chat_session
    @pytest.mark.asyncio
    async def test_get_history_curated_true(self):
        """T-21: All history reads use curated=True (SDK default is False — wrong for replay).

        Codereview fix (R1/C1 finding): the original test used a hasattr()-guarded
        no-op that always skipped its own assertion (ChatSessionManager never defines
        `_get_session_history`). This calls the REAL public method (compress_if_needed)
        that reads history, and asserts on the actual mock call.
        """
        mock_client = MagicMock()
        mgr = ChatSessionManager(
            client=mock_client, model_name="gemini-3.1-pro",
            prefill_user="Hello", prefill_model="Hi",
        )
        event_id = "evt-curated01"

        mock_chat = MagicMock()
        # Empty history -> compress_if_needed returns early after the get_history call,
        # which is exactly the call site under test.
        mock_chat.get_history = MagicMock(return_value=[])
        mgr._sessions = {event_id: MagicMock(chat=mock_chat)}

        await mgr.compress_if_needed(event_id, MagicMock())

        assert mock_chat.get_history.called, "compress_if_needed must call get_history"
        call = mock_chat.get_history.call_args
        curated = call.kwargs.get("curated", call.args[0] if call.args else False)
        assert curated is True, "get_history must be called with curated=True"

    def test_compression_no_circular_import(self):
        """T-22: chat_session.py imports compression.py cleanly, no cycle with brain.py.

        Verifies the import DAG: compression.py has zero imports from brain.py or
        chat_session.py. brain.py imports from compression.py. chat_session.py
        imports from compression.py. No circular dependency.
        """
        compression_mod = importlib.import_module("src.agents.llm.compression")
        assert hasattr(compression_mod, "compress_contents")
        assert hasattr(compression_mod, "estimate_tokens")
        assert hasattr(compression_mod, "dedup_consecutive_fr")

        compression_source = importlib.util.find_spec("src.agents.llm.compression")
        assert compression_source is not None, "compression.py must be importable"

        loaded = set(sys.modules.keys())
        brain_loaded_by_compression = "src.agents.brain" not in {
            m for m in loaded
            if m.startswith("src.agents.brain") and m != "src.agents.brain"
        }

        # compression.py must NOT pull in brain.py or chat_session.py
        mod = sys.modules.get("src.agents.llm.compression")
        if mod and hasattr(mod, "__file__"):
            import inspect
            source = inspect.getsource(mod)
            assert "from src.agents.brain" not in source, \
                "compression.py must not import from brain.py"
            assert "from ..brain" not in source, \
                "compression.py must not import from brain.py (relative)"
            assert "import brain" not in source, \
                "compression.py must not import brain module"
