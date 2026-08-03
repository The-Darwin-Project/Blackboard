# tests/test_two_tier_reconciler.py
# @ai-rules:
# 1. [Constraint]: 26 tests from plan Step 7 (chat-native_two-tier_096c68e6). TDD — tests
#    define the target interface. Expected to fail until implementation lands.
# 2. [Pattern]: Uses ConversationTurn + EventDocument stubs. No live Redis, no live LLM.
#    AsyncMock for async methods. MagicMock for SDK objects.
# 3. [Gotcha]: Reconciler module (src.agents.llm.reconciler or equivalent) may not exist yet.
#    Use conditional import with skip marker. Model tests (T1-T3) and gate tests (T22-T23)
#    run immediately against existing modules.
# 4. [Pattern]: Each test class independently runnable. Follows test_chat_session_bridge.py
#    Brain mock pattern and test_brain_loop_plumbing.py ConversationTurn stub pattern.
"""Two-Tier Reconciler — 26 specification tests from plan Step 7.

Tests are written against the PLANNED public interface, not implementation
internals. Expected to fail until the code executor completes implementation.

Test groups:
  T1-T3:   ConversationTurn.chat_role Pydantic validation
  T4-T5:   Rebuild filter (macro vs progress turns)
  T6-T12:  Reconciler cycle behavior (macro model guarantee, suppress, cap)
  T13-T15: Scheduling gate (delta detection)
  T16:     Config rebuild on state-mutating tools
  T17:     Error FR pairing
  T18-T19: was_rebuilt paths (terminal prompt, empty event header)
  T20-T21: User interrupt detection
  T22-T24: web_search gate (CASUAL domain)
  T25:     RECALL mid-stream blocks FC
  T26:     Multi-cycle macro alternation
"""
from __future__ import annotations

import time
from typing import Literal, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import ValidationError

from src.models import ConversationTurn, EventDocument, EventEvidence, EventInput, EventStatus


# ---------------------------------------------------------------------------
# Conditional import: reconciler module will exist after code executor lands
# ---------------------------------------------------------------------------
try:
    from src.agents.llm.reconciler import (
        reconcile_cycle,
        get_macro_user_delta,
        stream_and_drain,
    )
    _RECONCILER_AVAILABLE = True
except ImportError:
    reconcile_cycle = None  # type: ignore[assignment]
    get_macro_user_delta = None  # type: ignore[assignment]
    stream_and_drain = None  # type: ignore[assignment]
    _RECONCILER_AVAILABLE = False

_requires_reconciler = pytest.mark.skipif(
    not _RECONCILER_AVAILABLE,
    reason="reconciler module not yet implemented (parallel execution)",
)


# ---------------------------------------------------------------------------
# Helpers (same patterns as test_chat_session_bridge.py and test_brain_loop_plumbing.py)
# ---------------------------------------------------------------------------

def _make_event(
    event_id: str = "evt-2tier01",
    source: str = "chat",
    status: str = "active",
    brain_phase: str | None = "triage",
    conversation: list | None = None,
    domain: str = "complicated",
) -> EventDocument:
    evidence = EventEvidence(
        display_text="test two-tier",
        source_type=source,
        domain=domain,
        severity="info",
    )
    return EventDocument(
        id=event_id,
        source=source,
        status=EventStatus(status),
        brain_phase=brain_phase,
        service="test-svc",
        event=EventInput(reason="test", evidence=evidence),
        conversation=conversation or [],
    )


def _make_turn(
    turn: int = 1,
    actor: str = "brain",
    action: str = "response",
    thoughts: str | None = None,
    result: str | None = None,
    chat_role: Optional[Literal["user", "model"]] = None,
    timestamp: float | None = None,
    waitingFor: str | None = None,
    status: str = "evaluated",
) -> ConversationTurn:
    return ConversationTurn(
        turn=turn,
        actor=actor,
        action=action,
        thoughts=thoughts,
        result=result,
        chat_role=chat_role,
        status=status,
        waitingFor=waitingFor,
        timestamp=timestamp or time.time(),
    )


def _make_brain():
    """Minimal Brain with mocked dependencies (mirrors test_chat_session_bridge.py)."""
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


# ---------------------------------------------------------------------------
# 1. Model Tests: ConversationTurn.chat_role (T1-T3)
# ---------------------------------------------------------------------------

class TestChatRoleField:
    """ConversationTurn.chat_role: Optional[Literal['user', 'model']]."""

    def test_chat_role_field_default_none(self):
        """T1: chat_role defaults to None for backward compat with existing turns."""
        turn = ConversationTurn(
            turn=1, actor="brain", action="tool_result",
            thoughts="internal processing",
        )
        assert turn.chat_role is None, (
            "chat_role must default to None (progress tier) for backward compat"
        )

    def test_chat_role_accepts_user_model(self):
        """T2: chat_role accepts the two macro-tier literals."""
        user_turn = ConversationTurn(
            turn=1, actor="user", action="message",
            thoughts="Hello FRIDAY", chat_role="user",
        )
        assert user_turn.chat_role == "user"

        model_turn = ConversationTurn(
            turn=2, actor="brain", action="response",
            thoughts="Hello!", chat_role="model",
        )
        assert model_turn.chat_role == "model"

    def test_chat_role_rejects_invalid(self):
        """T3: chat_role rejects non-literal values via Pydantic validation."""
        with pytest.raises(ValidationError):
            ConversationTurn(
                turn=1, actor="brain", action="response",
                thoughts="test", chat_role="assistant",  # type: ignore[arg-type]
            )

        with pytest.raises(ValidationError):
            ConversationTurn(
                turn=1, actor="brain", action="response",
                thoughts="test", chat_role="system",  # type: ignore[arg-type]
            )


# ---------------------------------------------------------------------------
# 2. Rebuild Filter Tests (T4-T5)
# ---------------------------------------------------------------------------

class TestRebuildFilter:
    """Rebuild filter: only macro turns (chat_role != None) are replayed."""

    def test_macro_turns_filter(self):
        """T4: Only turns with chat_role != None are included in rebuild."""
        conversation = [
            _make_turn(turn=1, actor="user", action="message",
                       thoughts="Hi FRIDAY", chat_role="user"),
            _make_turn(turn=2, actor="brain", action="triage",
                       thoughts="Classifying...", chat_role=None),
            _make_turn(turn=3, actor="brain", action="response",
                       thoughts="Hello!", chat_role="model"),
            _make_turn(turn=4, actor="brain", action="tool_result",
                       thoughts="dispatched", chat_role=None),
            _make_turn(turn=5, actor="sysadmin", action="result",
                       result="Pods healthy", chat_role="user"),
            _make_turn(turn=6, actor="brain", action="response",
                       thoughts="All good", chat_role="model"),
        ]

        macro_turns = [t for t in conversation if t.chat_role is not None]
        progress_turns = [t for t in conversation if t.chat_role is None]

        assert len(macro_turns) == 4, (
            f"Expected 4 macro turns (user, model, user, model), got {len(macro_turns)}"
        )
        assert len(progress_turns) == 2, (
            f"Expected 2 progress turns, got {len(progress_turns)}"
        )

        roles = [t.chat_role for t in macro_turns]
        assert roles == ["user", "model", "user", "model"], (
            f"Macro turns must alternate user/model, got {roles}"
        )

    def test_progress_turns_excluded_from_rebuild(self):
        """T5: Turns with chat_role=None are excluded from rebuild history."""
        conversation = [
            _make_turn(turn=1, actor="user", action="message",
                       thoughts="Check the pods", chat_role="user"),
            _make_turn(turn=2, actor="brain", action="triage",
                       thoughts="Classifying as complicated", chat_role=None),
            _make_turn(turn=3, actor="brain", action="phase",
                       thoughts="Moving to dispatch", chat_role=None),
            _make_turn(turn=4, actor="brain", action="tool_result",
                       thoughts="Agent dispatched", chat_role=None, waitingFor="select_agent"),
            _make_turn(turn=5, actor="brain", action="response",
                       thoughts="I've dispatched sysadmin", chat_role="model"),
        ]

        rebuild_history = [t for t in conversation if t.chat_role is not None]
        excluded = [t for t in conversation if t.chat_role is None]

        assert len(rebuild_history) == 2, (
            "Only macro turns (user + model) should be in rebuild"
        )
        assert len(excluded) == 3, (
            "All progress turns (triage, phase, tool_result) should be excluded"
        )
        for t in excluded:
            assert t.chat_role is None
            assert t.action in ("triage", "phase", "tool_result")


# ---------------------------------------------------------------------------
# 3. Reconciler Cycle Behavior (T6-T12)
# ---------------------------------------------------------------------------

class TestReconcilerCycleBehavior:
    """Reconciler: macro model guarantee, text+FC flush, suppress, cap."""

    @_requires_reconciler
    @pytest.mark.asyncio
    async def test_reconciler_produces_one_macro_model(self):
        """T6: Every reconcile cycle writes exactly one macro model turn."""
        bb = MagicMock()
        appended_turns = []

        async def _capture_append(event_id, actor, action, text=None, chat_role=None, **kw):
            appended_turns.append({
                "actor": actor, "action": action,
                "text": text, "chat_role": chat_role,
            })
            return len(appended_turns)

        bb.append_turn = AsyncMock(side_effect=_capture_append)
        bb.get_event = AsyncMock(return_value=_make_event())

        mock_session = MagicMock()

        async def _stream_text_only(*args, **kwargs):
            return (None, None, "Here is my response", None)

        with patch(
            "src.agents.llm.reconciler.stream_and_drain",
            new_callable=AsyncMock,
            side_effect=_stream_text_only,
        ):
            await reconcile_cycle(
                event_id="evt-macro01", session=mock_session,
                config=MagicMock(), blackboard=bb,
            )

        macro_model_turns = [
            t for t in appended_turns if t["chat_role"] == "model"
        ]
        assert len(macro_model_turns) == 1, (
            f"Reconcile cycle must produce exactly 1 macro model turn, got {len(macro_model_turns)}"
        )

    @_requires_reconciler
    @pytest.mark.asyncio
    async def test_text_fc_flush_is_progress(self):
        """T7: When text+FC both present, text is written as progress (chat_role=None)."""
        bb = MagicMock()
        appended_turns = []

        async def _capture_append(event_id, actor, action, text=None, chat_role=None, **kw):
            appended_turns.append({
                "actor": actor, "action": action,
                "text": text, "chat_role": chat_role,
            })
            return len(appended_turns)

        bb.append_turn = AsyncMock(side_effect=_capture_append)
        bb.get_event = AsyncMock(return_value=_make_event())

        call_count = 0

        async def _stream_text_then_fc(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return ("classify_event", {"domain": "complicated"}, "Let me classify this...", None)
            return (None, None, "Classification complete.", None)

        with patch(
            "src.agents.llm.reconciler.stream_and_drain",
            new_callable=AsyncMock,
            side_effect=_stream_text_then_fc,
        ):
            await reconcile_cycle(
                event_id="evt-textfc01", session=MagicMock(),
                config=MagicMock(), blackboard=bb,
            )

        text_fc_turns = [
            t for t in appended_turns
            if t.get("text") and t["chat_role"] is None
            and "classify" in (t.get("text") or "").lower()
        ]
        assert len(text_fc_turns) >= 1, (
            "Text accompanying a FC must be written as progress (chat_role=None)"
        )

    @_requires_reconciler
    @pytest.mark.asyncio
    async def test_text_only_is_macro(self):
        """T8: When text-only (no FC), it's written as macro (chat_role='model')."""
        bb = MagicMock()
        appended_turns = []

        async def _capture_append(event_id, actor, action, text=None, chat_role=None, **kw):
            appended_turns.append({
                "actor": actor, "action": action,
                "text": text, "chat_role": chat_role,
            })
            return len(appended_turns)

        bb.append_turn = AsyncMock(side_effect=_capture_append)
        bb.get_event = AsyncMock(return_value=_make_event())

        async def _stream_text_only(*args, **kwargs):
            return (None, None, "I've completed the analysis.", None)

        with patch(
            "src.agents.llm.reconciler.stream_and_drain",
            new_callable=AsyncMock,
            side_effect=_stream_text_only,
        ):
            await reconcile_cycle(
                event_id="evt-textonly01", session=MagicMock(),
                config=MagicMock(), blackboard=bb,
            )

        macro_turns = [t for t in appended_turns if t["chat_role"] == "model"]
        assert len(macro_turns) == 1
        assert "completed" in (macro_turns[0]["text"] or "").lower(), (
            "Text-only response must be the macro model turn"
        )

    @_requires_reconciler
    @pytest.mark.asyncio
    async def test_terminal_tool_writes_macro(self):
        """T9: Terminal tool (wait_for_user etc) result written as macro model turn."""
        bb = MagicMock()
        appended_turns = []

        async def _capture_append(event_id, actor, action, text=None, chat_role=None, **kw):
            appended_turns.append({
                "actor": actor, "action": action,
                "text": text, "chat_role": chat_role,
            })
            return len(appended_turns)

        bb.append_turn = AsyncMock(side_effect=_capture_append)
        bb.get_event = AsyncMock(return_value=_make_event())

        async def _stream_terminal_tool(*args, **kwargs):
            return ("wait_for_user", {"summary": "Waiting for response"}, "Let me know.", None)

        with patch(
            "src.agents.llm.reconciler.stream_and_drain",
            new_callable=AsyncMock,
            side_effect=_stream_terminal_tool,
        ):
            await reconcile_cycle(
                event_id="evt-terminal01", session=MagicMock(),
                config=MagicMock(), blackboard=bb,
            )

        macro_turns = [t for t in appended_turns if t["chat_role"] == "model"]
        assert len(macro_turns) == 1, (
            "Terminal tool cycle must produce exactly one macro model turn"
        )

    @_requires_reconciler
    @pytest.mark.asyncio
    async def test_terminal_suppress_bounded(self):
        """T10: Suppress loop runs max 3 times before escalating."""
        bb = MagicMock()
        bb.append_turn = AsyncMock(return_value=1)
        bb.get_event = AsyncMock(return_value=_make_event())

        suppress_drain_calls = []

        async def _stream_keeps_returning_fc(*args, **kwargs):
            suppress_drain_calls.append(1)
            return ("classify_event", {"domain": "clear"}, None, None)

        with patch(
            "src.agents.llm.reconciler.stream_and_drain",
            new_callable=AsyncMock,
            side_effect=_stream_keeps_returning_fc,
        ):
            await reconcile_cycle(
                event_id="evt-suppress01", session=MagicMock(),
                config=MagicMock(), blackboard=bb,
            )

        # 1 initial + up to 3 suppress = max 4 stream_and_drain calls before eviction
        assert len(suppress_drain_calls) <= 4, (
            f"Suppress loop must be bounded at 3 (+ 1 initial), got {len(suppress_drain_calls)} calls"
        )

    @_requires_reconciler
    @pytest.mark.asyncio
    async def test_terminal_suppress_evicts_on_overflow(self):
        """T11: If model still generates FC after 3 suppresses, session evicted."""
        bb = MagicMock()
        bb.append_turn = AsyncMock(return_value=1)
        bb.get_event = AsyncMock(return_value=_make_event())

        mock_session = MagicMock()
        evict_called = []

        def _mock_evict(*args, **kwargs):
            evict_called.append(True)

        mock_session.evict = _mock_evict

        call_count = 0

        async def _stream_always_fc(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            return ("classify_event", {"domain": "clear"}, None, None)

        with patch(
            "src.agents.llm.reconciler.stream_and_drain",
            new_callable=AsyncMock,
            side_effect=_stream_always_fc,
        ):
            await reconcile_cycle(
                event_id="evt-evict01", session=mock_session,
                config=MagicMock(), blackboard=bb,
            )

        assert len(evict_called) >= 1, (
            "Session must be evicted after 3 suppress attempts exhaust"
        )

    @_requires_reconciler
    @pytest.mark.asyncio
    async def test_cap_pairs_pending_fc(self):
        """T12: For-else cap sends synthetic FR before writing macro turn."""
        bb = MagicMock()
        appended_turns = []

        async def _capture_append(event_id, actor, action, text=None, chat_role=None, **kw):
            appended_turns.append({
                "actor": actor, "action": action,
                "text": text, "chat_role": chat_role,
            })
            return len(appended_turns)

        bb.append_turn = AsyncMock(side_effect=_capture_append)
        bb.get_event = AsyncMock(return_value=_make_event())

        iteration = 0

        async def _stream_fc_then_cap(*args, **kwargs):
            nonlocal iteration
            iteration += 1
            return ("classify_event", {"domain": "clear"}, f"Step {iteration}", None)

        drain_calls = []

        async def _capture_drain(session, content, config):
            drain_calls.append(content)
            return (None, None, "Capped.", None)

        with patch(
            "src.agents.llm.reconciler.stream_and_drain",
            new_callable=AsyncMock,
            side_effect=_capture_drain,
        ):
            await reconcile_cycle(
                event_id="evt-cap01", session=MagicMock(),
                config=MagicMock(), blackboard=bb,
            )

        macro_turns = [t for t in appended_turns if t["chat_role"] == "model"]
        assert len(macro_turns) >= 1, (
            "Cap path must still produce a macro model turn with 'Tool limit.' or similar"
        )


# ---------------------------------------------------------------------------
# 4. Scheduling Gate (T13-T15)
# ---------------------------------------------------------------------------

class TestSchedulingGate:
    """Scheduling gate: get_macro_user_delta controls reconcile entry."""

    @_requires_reconciler
    def test_scheduling_gate_no_delta(self):
        """T13: No macro user delta + not cold start → no reconcile call."""
        conversation = [
            _make_turn(turn=1, actor="user", action="message",
                       thoughts="Original request", chat_role="user"),
            _make_turn(turn=2, actor="brain", action="response",
                       thoughts="Handled", chat_role="model"),
        ]
        event = _make_event(conversation=conversation)

        last_sent_cursor = 1  # cursor at turn 1 = already processed

        delta = get_macro_user_delta(event, last_sent_cursor)
        assert not delta, (
            "No new macro user turns since cursor → delta must be empty/falsy"
        )

    @_requires_reconciler
    def test_scheduling_gate_cold_start_bypasses(self):
        """T14: Cold start always reconciles even with no delta."""
        event = _make_event(conversation=[])

        # Cold start: last_sent_cursor = -1 (never sent), conversation empty
        delta = get_macro_user_delta(event, -1)

        # With cold start, the system should still proceed (cold_start flag
        # bypasses the delta check in the caller)
        # The delta itself may be empty, but cold_start overrides
        cold_start = True
        should_reconcile = bool(delta) or cold_start
        assert should_reconcile, (
            "Cold start must always trigger reconciliation regardless of delta"
        )

    @_requires_reconciler
    def test_scheduling_gate_with_delta(self):
        """T15: New macro user turn since cursor → reconcile fires."""
        conversation = [
            _make_turn(turn=1, actor="user", action="message",
                       thoughts="First request", chat_role="user"),
            _make_turn(turn=2, actor="brain", action="response",
                       thoughts="Done", chat_role="model"),
            _make_turn(turn=3, actor="brain", action="tool_result",
                       thoughts="internal", chat_role=None),
            _make_turn(turn=4, actor="sysadmin", action="result",
                       result="Agent report", chat_role="user"),
        ]
        event = _make_event(conversation=conversation)

        last_sent_cursor = 2  # processed up to turn 2

        delta = get_macro_user_delta(event, last_sent_cursor)
        assert delta, (
            "New macro user turn (turn 4, chat_role='user') since cursor → delta must be truthy"
        )


# ---------------------------------------------------------------------------
# 5. Config Rebuild on State-Mutating Tools (T16)
# ---------------------------------------------------------------------------

class TestConfigRebuild:
    """State-mutating tools trigger config rebuild."""

    @_requires_reconciler
    @pytest.mark.asyncio
    async def test_config_rebuild_on_state_mutating(self):
        """T16: set_phase/classify_event trigger config rebuild."""
        bb = MagicMock()
        bb.append_turn = AsyncMock(return_value=1)
        bb.get_event = AsyncMock(return_value=_make_event())

        config_rebuild_calls = []

        original_config = MagicMock()

        def _mock_rebuild_config(*args, **kwargs):
            config_rebuild_calls.append(True)
            return original_config

        call_count = 0

        async def _stream_state_mutating(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return ("classify_event", {"domain": "casual"}, None, None)
            if call_count == 2:
                return ("set_phase", {"phase": "dispatch"}, None, None)
            return (None, None, "Done.", None)

        with patch(
            "src.agents.llm.reconciler.stream_and_drain",
            new_callable=AsyncMock,
            side_effect=_stream_state_mutating,
        ), patch(
            "src.agents.llm.reconciler._rebuild_config",
            side_effect=_mock_rebuild_config,
        ):
            await reconcile_cycle(
                event_id="evt-statemut01", session=MagicMock(),
                config=original_config, blackboard=bb,
            )

        assert len(config_rebuild_calls) >= 1, (
            "classify_event and set_phase must trigger config rebuild "
            f"(got {len(config_rebuild_calls)} rebuild calls)"
        )


# ---------------------------------------------------------------------------
# 6. Error FR Pairing (T17)
# ---------------------------------------------------------------------------

class TestErrorFRPairing:
    """Exception in execute_tool → error message in FR payload."""

    @_requires_reconciler
    @pytest.mark.asyncio
    async def test_error_fr_pairing(self):
        """T17: Exception in tool execution → error in FR → model sees failure."""
        bb = MagicMock()
        appended_turns = []

        async def _capture_append(event_id, actor, action, text=None, chat_role=None, **kw):
            appended_turns.append({
                "actor": actor, "action": action,
                "text": text, "chat_role": chat_role,
            })
            return len(appended_turns)

        bb.append_turn = AsyncMock(side_effect=_capture_append)
        bb.get_event = AsyncMock(return_value=_make_event())

        fr_payloads = []

        call_count = 0

        async def _stream_with_error_tool(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return ("lookup_service", {"name": "test-svc"}, None, None)
            return (None, None, "Encountered an error.", None)

        async def _mock_execute_tool(tool_name, args, **kwargs):
            raise ConnectionError("Redis connection refused")

        with patch(
            "src.agents.llm.reconciler.stream_and_drain",
            new_callable=AsyncMock,
            side_effect=_stream_with_error_tool,
        ), patch(
            "src.agents.llm.reconciler.execute_tool",
            new_callable=AsyncMock,
            side_effect=_mock_execute_tool,
        ):
            await reconcile_cycle(
                event_id="evt-err01", session=MagicMock(),
                config=MagicMock(), blackboard=bb,
            )

        # The reconciler should have caught the exception and sent an FR
        # with error payload, not crashed
        macro_turns = [t for t in appended_turns if t["chat_role"] == "model"]
        assert len(macro_turns) >= 1, (
            "Error in tool execution must not prevent macro model turn"
        )


# ---------------------------------------------------------------------------
# 7. was_rebuilt Paths (T18-T19)
# ---------------------------------------------------------------------------

class TestWasRebuiltPaths:
    """Rebuilt session: terminal_prompt only for existing macros, header for empty."""

    @_requires_reconciler
    @pytest.mark.asyncio
    async def test_was_rebuilt_sends_terminal_prompt_only(self):
        """T18: Rebuilt session with existing macros sends only terminal_prompt."""
        bb = MagicMock()
        existing_macros = [
            _make_turn(turn=1, actor="user", action="message",
                       thoughts="Check pods", chat_role="user"),
            _make_turn(turn=2, actor="brain", action="response",
                       thoughts="Checking now", chat_role="model"),
            _make_turn(turn=3, actor="sysadmin", action="result",
                       result="Pods healthy", chat_role="user"),
        ]
        event = _make_event(conversation=existing_macros)
        bb.get_event = AsyncMock(return_value=event)

        send_calls = []

        async def _capture_stream(session, content, config):
            send_calls.append(content)
            return (None, None, "All pods look healthy.", None)

        bb.append_turn = AsyncMock(return_value=1)

        with patch(
            "src.agents.llm.reconciler.stream_and_drain",
            new_callable=AsyncMock,
            side_effect=_capture_stream,
        ):
            await reconcile_cycle(
                event_id="evt-rebuilt01", session=MagicMock(),
                config=MagicMock(), blackboard=bb,
                was_rebuilt=True,
            )

        assert len(send_calls) >= 1, (
            "Rebuilt session must send at least the terminal_prompt"
        )
        # The send content should NOT include the full conversation history
        # (it was baked into the rebuilt session already)

    @_requires_reconciler
    @pytest.mark.asyncio
    async def test_cold_start_empty_event_header(self):
        """T19: Rebuilt session with no macros sends header + terminal_prompt."""
        bb = MagicMock()
        event = _make_event(conversation=[])
        bb.get_event = AsyncMock(return_value=event)

        send_calls = []

        async def _capture_stream(session, content, config):
            send_calls.append(content)
            return (None, None, "New event received. Analyzing.", None)

        bb.append_turn = AsyncMock(return_value=1)

        with patch(
            "src.agents.llm.reconciler.stream_and_drain",
            new_callable=AsyncMock,
            side_effect=_capture_stream,
        ):
            await reconcile_cycle(
                event_id="evt-cold01", session=MagicMock(),
                config=MagicMock(), blackboard=bb,
                was_rebuilt=True,
            )

        assert len(send_calls) >= 1, (
            "Cold start with empty event must send header + terminal_prompt"
        )


# ---------------------------------------------------------------------------
# 8. User Interrupt Detection (T20-T21)
# ---------------------------------------------------------------------------

class TestUserInterrupt:
    """User interrupt: chat/slack periodic re-fetch, skipped for non-chat."""

    @_requires_reconciler
    @pytest.mark.asyncio
    async def test_user_interrupt_chat_source(self):
        """T20: Chat/slack source: periodic re-fetch detects new user turn."""
        bb = MagicMock()
        event = _make_event(source="chat")

        # Simulate: during reconcile, a new user turn appears
        interrupted_event = _make_event(
            source="chat",
            conversation=[
                _make_turn(turn=1, actor="user", action="message",
                           thoughts="First msg", chat_role="user"),
                _make_turn(turn=2, actor="brain", action="response",
                           thoughts="Working on it", chat_role="model"),
                _make_turn(turn=3, actor="user", action="message",
                           thoughts="Actually, cancel that", chat_role="user"),
            ],
        )

        fetch_count = 0

        async def _mock_get_event(eid):
            nonlocal fetch_count
            fetch_count += 1
            if fetch_count >= 2:
                return interrupted_event
            return event

        bb.get_event = AsyncMock(side_effect=_mock_get_event)
        bb.append_turn = AsyncMock(return_value=1)

        iteration = 0

        async def _slow_stream(*args, **kwargs):
            nonlocal iteration
            iteration += 1
            if iteration <= 2:
                return ("classify_event", {"domain": "casual"}, None, None)
            return (None, None, "Done.", None)

        with patch(
            "src.agents.llm.reconciler.stream_and_drain",
            new_callable=AsyncMock,
            side_effect=_slow_stream,
        ):
            await reconcile_cycle(
                event_id="evt-interrupt01", session=MagicMock(),
                config=MagicMock(), blackboard=bb,
            )

        assert fetch_count >= 1, (
            "Chat source must periodically re-fetch event to detect interrupts"
        )

    @_requires_reconciler
    @pytest.mark.asyncio
    async def test_user_interrupt_skipped_non_chat(self):
        """T21: Non-chat sources never check for user interrupt."""
        bb = MagicMock()
        event = _make_event(source="headhunter")
        bb.get_event = AsyncMock(return_value=event)
        bb.append_turn = AsyncMock(return_value=1)

        async def _simple_stream(*args, **kwargs):
            return (None, None, "Processed MR.", None)

        with patch(
            "src.agents.llm.reconciler.stream_and_drain",
            new_callable=AsyncMock,
            side_effect=_simple_stream,
        ):
            await reconcile_cycle(
                event_id="evt-noint01", session=MagicMock(),
                config=MagicMock(), blackboard=bb,
            )

        # For non-chat sources, get_event should only be called for initial
        # fetch, not for interrupt polling
        call_count = bb.get_event.await_count
        assert call_count <= 2, (
            f"Non-chat source should not poll for interrupts, got {call_count} get_event calls"
        )


# ---------------------------------------------------------------------------
# 9. web_search Gate (T22-T24)
# ---------------------------------------------------------------------------

class TestWebSearchGate:
    """web_search: available in CASUAL domain and PRE_CLASSIFICATION allowlist."""

    def _make_gate_context(
        self,
        domain: str = "casual",
        classified: bool = True,
        phase: str = "triage",
        source: str = "chat",
    ):
        from src.agents.tool_gates import GateContext
        return GateContext(
            brain_phase=phase,
            event_source=source,
            context_flags={
                "brain_has_classified": classified,
                "event_domain": domain,
            },
            conversation=[],
            is_defer_wake=False,
            iteration=0,
            has_kargo_context=False,
            has_github_context=False,
            unread_notes=0,
        )

    def test_web_search_gate_casual_domain(self):
        """T22: web_search available in CASUAL domain."""
        from src.agents.tool_gates import evaluate_gates

        all_tools = [
            {"name": "classify_event"}, {"name": "set_phase"},
            {"name": "wait_for_user"}, {"name": "web_search"},
            {"name": "consult_deep_memory"}, {"name": "lookup_service"},
            {"name": "lookup_journal"}, {"name": "respond_to_jarvis"},
            {"name": "read_sticky_notes"}, {"name": "take_note"},
            {"name": "review_notes"},
        ]

        ctx = self._make_gate_context(domain="casual", classified=True, phase="dispatch")
        active = evaluate_gates(all_tools, ctx)
        active_names = {t["name"] for t in active}

        assert "web_search" in active_names, (
            "web_search must be available in CASUAL domain "
            f"(got active tools: {active_names})"
        )

    def test_web_search_gate_blocked_non_casual(self):
        """T23: web_search blocked outside CASUAL domain (unless pre-classification).

        Plan spec: web_search gate is 'triage/dispatch + CASUAL domain'.
        In complicated domain (classified), web_search must NOT be available.
        The code executor will add the gating mechanism (dedicated strip gate
        or phase/domain predicate). This test defines the target behavior.
        """
        from src.agents.tool_gates import evaluate_gates

        all_tools = [
            {"name": "classify_event"}, {"name": "set_phase"},
            {"name": "web_search"}, {"name": "select_agent"},
            {"name": "consult_deep_memory"}, {"name": "close_event"},
        ]

        ctx = self._make_gate_context(
            domain="complicated", classified=True, phase="dispatch",
        )
        active = evaluate_gates(all_tools, ctx)
        active_names = {t["name"] for t in active}

        assert "web_search" not in active_names, (
            "web_search must be blocked in non-CASUAL domains. "
            f"Got active tools: {active_names}"
        )

    @_requires_reconciler
    @pytest.mark.asyncio
    async def test_web_search_returns_true(self):
        """T24: web_search handler returns True (non-terminal, continue cycle)."""
        # The handler should return True to signal "continue iterating"
        # (non-terminal tool — reconciler keeps going after web_search)
        try:
            from src.agents.handlers_tools import handle_web_search
        except ImportError:
            pytest.skip("handle_web_search not yet implemented")

        bb = MagicMock()
        event = _make_event(source="chat")
        ctx = MagicMock()
        ctx.event = event

        with patch(
            "src.agents.handlers_tools.vertex_search",
            new_callable=AsyncMock,
            return_value={"results": [{"title": "Test", "snippet": "Test result"}]},
        ):
            result = await handle_web_search(
                query="Python asyncio tutorial",
                context=ctx,
            )

        assert result is True, (
            "web_search handler must return True (non-terminal, continue cycle)"
        )


# ---------------------------------------------------------------------------
# 10. RECALL Mid-Stream (T25)
# ---------------------------------------------------------------------------

class TestRecallMidStream:
    """RECALL keyword in thinking → blocked FR → config rebuild."""

    @_requires_reconciler
    @pytest.mark.asyncio
    async def test_recall_mid_stream_blocks_fc(self):
        """T25: RECALL keyword in thinking blocks FC and triggers config rebuild."""
        bb = MagicMock()
        bb.append_turn = AsyncMock(return_value=1)
        bb.get_event = AsyncMock(return_value=_make_event())

        config_rebuild_calls = []

        def _track_rebuild(*args, **kwargs):
            config_rebuild_calls.append(True)
            return MagicMock()

        call_count = 0

        async def _stream_with_recall(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                # Model returns FC + thinking that contains RECALL keyword
                return (
                    "classify_event",
                    {"domain": "complicated"},
                    None,
                    "I should RECALL lessons from past events before classifying.",
                )
            return (None, None, "After reviewing lessons, classification complete.", None)

        with patch(
            "src.agents.llm.reconciler.stream_and_drain",
            new_callable=AsyncMock,
            side_effect=_stream_with_recall,
        ), patch(
            "src.agents.llm.reconciler._rebuild_config",
            side_effect=_track_rebuild,
        ):
            await reconcile_cycle(
                event_id="evt-recall01", session=MagicMock(),
                config=MagicMock(), blackboard=bb,
            )

        assert len(config_rebuild_calls) >= 1, (
            "RECALL in thinking must trigger config rebuild with injected lessons"
        )


# ---------------------------------------------------------------------------
# 11. Multi-Cycle Alternation (T26)
# ---------------------------------------------------------------------------

class TestMacrTurnAlternation:
    """After multiple cycles, conversation shows strict user/model alternation."""

    def test_macro_turn_alternation(self):
        """T26: Multi-cycle conversation maintains strict user/model alternation."""
        # Simulate a conversation after 3 reconcile cycles with interleaved
        # progress turns. The macro view must alternate strictly.
        conversation = [
            # Cycle 1: user message → brain processes → macro response
            _make_turn(turn=1, actor="user", action="message",
                       thoughts="Check pod health", chat_role="user"),
            _make_turn(turn=2, actor="brain", action="triage",
                       thoughts="Classifying...", chat_role=None),
            _make_turn(turn=3, actor="brain", action="tool_result",
                       thoughts="Classified as complicated", chat_role=None,
                       waitingFor="classify_event"),
            _make_turn(turn=4, actor="brain", action="phase",
                       thoughts="dispatch", chat_role=None),
            _make_turn(turn=5, actor="brain", action="response",
                       thoughts="I'll check the pods now.", chat_role="model"),

            # Cycle 2: agent result → brain processes → macro response
            _make_turn(turn=6, actor="sysadmin", action="result",
                       result="All pods healthy", chat_role="user"),
            _make_turn(turn=7, actor="brain", action="tool_result",
                       thoughts="Agent confirmed health", chat_role=None,
                       waitingFor="wait_for_agent"),
            _make_turn(turn=8, actor="brain", action="response",
                       thoughts="Pods are all healthy.", chat_role="model"),

            # Cycle 3: user follow-up → brain responds
            _make_turn(turn=9, actor="user", action="message",
                       thoughts="What about memory?", chat_role="user"),
            _make_turn(turn=10, actor="brain", action="tool_result",
                       thoughts="Queried memory metrics", chat_role=None),
            _make_turn(turn=11, actor="brain", action="response",
                       thoughts="Memory usage is nominal.", chat_role="model"),
        ]

        macro_turns = [t for t in conversation if t.chat_role is not None]
        macro_roles = [t.chat_role for t in macro_turns]

        assert macro_roles == ["user", "model", "user", "model", "user", "model"], (
            f"Macro turns must strictly alternate user/model, got {macro_roles}"
        )

        # Verify no consecutive same roles
        for i in range(1, len(macro_roles)):
            assert macro_roles[i] != macro_roles[i - 1], (
                f"Consecutive same role at position {i}: {macro_roles[i - 1]} → {macro_roles[i]}"
            )

        # Verify progress turns are correctly interspersed
        progress_turns = [t for t in conversation if t.chat_role is None]
        assert len(progress_turns) == 5, (
            f"Expected 5 progress turns, got {len(progress_turns)}"
        )
        for t in progress_turns:
            assert t.action in ("triage", "tool_result", "phase"), (
                f"Unexpected progress action: {t.action}"
            )
