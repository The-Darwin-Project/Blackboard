# tests/test_handle_close_event.py
# @ai-rules:
# 1. [Constraint]: Pure unit tests — mock ToolContext + BlackboardState, no real Redis.
# 2. [Pattern]: Uses ConversationTurn objects (not dicts) to match production path.
# 3. [Gotcha]: handle_close_event is async — all tests use pytest-asyncio.
"""Tests for handle_close_event pessimistic re-check (commit 76803ab0) and the
terminal-state close-gate enforcement (GitHub #155/#156).

Covers: abort on unevaluated user/jarvis message, happy-path close,
None/closed event fallback, brain.phase scan boundary, response_parts threading,
terminal_reason validation, open-incident-reference blocking + escape valve,
feature flag, and precedence between the pessimistic guard and the new checks.
"""
from __future__ import annotations

import importlib
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

import src.agents.handlers_state as handlers_state
from src.agents.handlers_state import _is_valid_tracking_link, handle_close_event
from src.models import ConversationTurn, EventStatus, MessageStatus


def _turn(actor: str, action: str, status: MessageStatus = MessageStatus.SENT) -> ConversationTurn:
    return ConversationTurn(turn=0, actor=actor, action=action, status=status)


def _mock_ctx(event=None):
    bb = AsyncMock()
    bb.get_event = AsyncMock(return_value=event)
    ctx = AsyncMock()
    ctx.get_blackboard = MagicMock(return_value=bb)
    ctx.append_and_broadcast = AsyncMock(return_value=1)
    ctx.close_and_broadcast = AsyncMock()
    return ctx, bb


def _event(
    conversation: list[ConversationTurn],
    status: str = "active",
    source: str = "chat",
    incident_references: list[str] | None = None,
):
    return SimpleNamespace(
        conversation=conversation,
        status=SimpleNamespace(value=status),
        source=source,
        incident_references=incident_references,
    )


class TestAbortOnUnevaluatedMessage:
    """Handler must abort close when unevaluated user/jarvis message exists."""

    @pytest.mark.asyncio
    async def test_user_message_sent_aborts(self):
        event = _event([_turn("user", "message", MessageStatus.SENT)])
        ctx, _ = _mock_ctx(event)
        result = await handle_close_event(ctx, "evt-1", {}, None)
        assert result is True
        ctx.close_and_broadcast.assert_not_called()
        ctx.append_and_broadcast.assert_called_once()

    @pytest.mark.asyncio
    async def test_jarvis_message_delivered_aborts(self):
        event = _event([_turn("jarvis", "message", MessageStatus.DELIVERED)])
        ctx, _ = _mock_ctx(event)
        result = await handle_close_event(ctx, "evt-1", {}, None)
        assert result is True
        ctx.close_and_broadcast.assert_not_called()

    @pytest.mark.asyncio
    async def test_abort_turn_includes_response_parts(self):
        event = _event([_turn("user", "message", MessageStatus.SENT)])
        ctx, _ = _mock_ctx(event)
        fake_parts = [{"text": "thinking..."}]
        await handle_close_event(ctx, "evt-1", {}, fake_parts)
        turn_arg = ctx.append_and_broadcast.call_args[0][1]
        assert turn_arg.response_parts == fake_parts


class TestHappyPathClose:
    """Handler must proceed with close when no unevaluated messages exist."""

    @pytest.mark.asyncio
    async def test_all_evaluated_closes(self):
        event = _event([
            _turn("user", "message", MessageStatus.EVALUATED),
            _turn("brain", "response"),
        ])
        ctx, _ = _mock_ctx(event)
        result = await handle_close_event(
            ctx, "evt-1", {"summary": "Done.", "terminal_reason": "resolved"}, None,
        )
        assert result is False
        ctx.close_and_broadcast.assert_called_once_with(
            "evt-1", "Done.", close_reason="resolved", tracking_link=None,
        )
        ctx.append_and_broadcast.assert_not_called()

    @pytest.mark.asyncio
    async def test_empty_conversation_closes(self):
        event = _event([])
        ctx, _ = _mock_ctx(event)
        result = await handle_close_event(ctx, "evt-1", {"terminal_reason": "resolved"}, None)
        assert result is False
        ctx.close_and_broadcast.assert_called_once()


class TestNoneAndClosedEvent:
    """Handler must handle missing or already-closed events gracefully."""

    @pytest.mark.asyncio
    async def test_none_event_returns_false(self):
        ctx, _ = _mock_ctx(None)
        result = await handle_close_event(ctx, "evt-1", {}, None)
        assert result is False
        ctx.close_and_broadcast.assert_not_called()

    @pytest.mark.asyncio
    async def test_already_closed_returns_false(self):
        event = _event([_turn("user", "message", MessageStatus.SENT)], status="closed")
        ctx, _ = _mock_ctx(event)
        result = await handle_close_event(ctx, "evt-1", {}, None)
        assert result is False
        ctx.close_and_broadcast.assert_not_called()


class TestScanBoundary:
    """brain.phase/close must stop backward scan — older messages don't block."""

    @pytest.mark.asyncio
    async def test_brain_phase_stops_scan(self):
        event = _event([
            _turn("user", "message", MessageStatus.DELIVERED),
            _turn("brain", "phase"),
            _turn("brain", "response"),
        ])
        ctx, _ = _mock_ctx(event)
        result = await handle_close_event(ctx, "evt-1", {"terminal_reason": "resolved"}, None)
        assert result is False
        ctx.close_and_broadcast.assert_called_once()

    @pytest.mark.asyncio
    async def test_brain_close_stops_scan(self):
        event = _event([
            _turn("jarvis", "message", MessageStatus.SENT),
            _turn("brain", "close"),
            _turn("brain", "response"),
        ])
        ctx, _ = _mock_ctx(event)
        result = await handle_close_event(ctx, "evt-1", {"terminal_reason": "resolved"}, None)
        assert result is False
        ctx.close_and_broadcast.assert_called_once()


class TestNonBlockingTurns:
    """Non-message actions and non-user/jarvis actors must not trigger abort."""

    @pytest.mark.asyncio
    async def test_user_confirm_ignored(self):
        event = _event([_turn("user", "confirm", MessageStatus.SENT)])
        ctx, _ = _mock_ctx(event)
        result = await handle_close_event(ctx, "evt-1", {"terminal_reason": "resolved"}, None)
        assert result is False
        ctx.close_and_broadcast.assert_called_once()

    @pytest.mark.asyncio
    async def test_sysadmin_message_ignored(self):
        event = _event([_turn("sysadmin", "message", MessageStatus.SENT)])
        ctx, _ = _mock_ctx(event)
        result = await handle_close_event(ctx, "evt-1", {"terminal_reason": "resolved"}, None)
        assert result is False
        ctx.close_and_broadcast.assert_called_once()


class TestTerminalReasonValidation:
    """T-1, T-2, T-13: terminal_reason is required and must be a valid enum value."""

    @pytest.mark.asyncio
    async def test_missing_terminal_reason_rejects(self):
        # T-1
        event = _event([])
        ctx, _ = _mock_ctx(event)
        result = await handle_close_event(ctx, "evt-1", {"summary": "done"}, None)
        assert result is True
        ctx.close_and_broadcast.assert_not_called()
        turn_arg = ctx.append_and_broadcast.call_args[0][1]
        assert turn_arg.waitingFor == "close_event"

    @pytest.mark.asyncio
    async def test_invalid_terminal_reason_rejects(self):
        # T-2
        event = _event([])
        ctx, _ = _mock_ctx(event)
        result = await handle_close_event(
            ctx, "evt-1", {"summary": "done", "terminal_reason": "whatever"}, None,
        )
        assert result is True
        ctx.close_and_broadcast.assert_not_called()

    @pytest.mark.asyncio
    async def test_valid_terminal_reason_no_open_incidents_closes(self):
        # T-3
        event = _event([], incident_references=None)
        ctx, _ = _mock_ctx(event)
        result = await handle_close_event(ctx, "evt-1", {"terminal_reason": "resolved"}, None)
        assert result is False
        ctx.close_and_broadcast.assert_called_once_with(
            "evt-1", "Event closed.", close_reason="resolved", tracking_link=None,
        )

    @pytest.mark.asyncio
    async def test_self_resolved_still_works(self):
        # T-13
        event = _event([], incident_references=None)
        ctx, _ = _mock_ctx(event)
        result = await handle_close_event(ctx, "evt-1", {"terminal_reason": "self_resolved"}, None)
        assert result is False
        ctx.close_and_broadcast.assert_called_once()


class TestOpenIncidentEscapeValve:
    """T-4 through T-7: open incident_references block close unless non_transient_confirmed + tracking_link."""

    @pytest.mark.asyncio
    async def test_open_incident_blocks_close_without_escape_valve(self):
        # T-4
        event = _event([], source="aligner", incident_references=["JIRA-1"])
        ctx, _ = _mock_ctx(event)
        result = await handle_close_event(ctx, "evt-1", {"terminal_reason": "resolved"}, None)
        assert result is True
        ctx.close_and_broadcast.assert_not_called()
        turn_arg = ctx.append_and_broadcast.call_args[0][1]
        assert "JIRA-1" in turn_arg.thoughts
        assert turn_arg.waitingFor == "close_event"

    @pytest.mark.asyncio
    async def test_non_transient_confirmed_without_tracking_link_still_blocks(self):
        # T-5
        event = _event([], source="aligner", incident_references=["JIRA-1"])
        ctx, _ = _mock_ctx(event)
        result = await handle_close_event(
            ctx, "evt-1", {"terminal_reason": "non_transient_confirmed"}, None,
        )
        assert result is True
        ctx.close_and_broadcast.assert_not_called()

    @pytest.mark.asyncio
    async def test_non_transient_confirmed_with_tracking_link_succeeds(self):
        # T-6
        event = _event([], source="aligner", incident_references=["JIRA-1"])
        ctx, _ = _mock_ctx(event)
        result = await handle_close_event(
            ctx, "evt-1",
            {"terminal_reason": "non_transient_confirmed", "tracking_link": "JIRA-1"},
            None,
        )
        assert result is False
        ctx.close_and_broadcast.assert_called_once_with(
            "evt-1", "Event closed.",
            close_reason="non_transient_confirmed", tracking_link="JIRA-1",
        )

    @pytest.mark.asyncio
    async def test_open_incident_on_non_automated_source_does_not_block(self):
        # T-7
        event = _event([], source="chat", incident_references=["JIRA-1"])
        ctx, _ = _mock_ctx(event)
        result = await handle_close_event(ctx, "evt-1", {"terminal_reason": "resolved"}, None)
        assert result is False
        ctx.close_and_broadcast.assert_called_once()


class TestFeatureFlag:
    """T-14: ENABLE_TERMINAL_CLOSE_GATE=false restores legacy behavior."""

    @pytest.mark.asyncio
    async def test_feature_flag_disabled_skips_enforcement(self, monkeypatch):
        monkeypatch.setattr(handlers_state, "ENABLE_TERMINAL_CLOSE_GATE", False)
        event = _event([], source="aligner", incident_references=["JIRA-1"])
        ctx, _ = _mock_ctx(event)
        result = await handle_close_event(ctx, "evt-1", {"summary": "done"}, None)
        assert result is False
        ctx.close_and_broadcast.assert_called_once_with("evt-1", "done", close_reason="resolved")


class TestExistingGuardPrecedence:
    """T-20: the pre-existing unevaluated-close-blocker still wins over terminal_reason checks."""

    @pytest.mark.asyncio
    async def test_unevaluated_message_blocks_even_with_valid_terminal_reason(self):
        event = _event(
            [_turn("user", "message", MessageStatus.SENT)],
            source="aligner", incident_references=["JIRA-1"],
        )
        ctx, _ = _mock_ctx(event)
        result = await handle_close_event(
            ctx, "evt-1",
            {"terminal_reason": "non_transient_confirmed", "tracking_link": "JIRA-1"},
            None,
        )
        assert result is True
        ctx.close_and_broadcast.assert_not_called()
        turn_arg = ctx.append_and_broadcast.call_args[0][1]
        assert "unevaluated message" in turn_arg.thoughts


class TestIsValidTrackingLinkNewlineRejection:
    """HIGH finding fix: embedded newlines in tracking_link must be rejected outright,
    even when they would otherwise match incident_references or the URL/issue-key
    pattern -- prevents GitLab quick-action/comment injection under the bot's identity."""

    def test_rejects_bare_newline(self):
        assert _is_valid_tracking_link("PROJ-123\n/close", []) is False

    def test_rejects_bare_carriage_return(self):
        assert _is_valid_tracking_link("PROJ-123\r/close", []) is False

    def test_rejects_crlf(self):
        assert _is_valid_tracking_link("https://example.com/x\r\n/assign @bot", []) is False

    def test_rejects_newline_even_when_matching_incident_references(self):
        # Defense-in-depth: an exact incident_references match must not bypass the
        # newline check -- an attacker-controlled tracking_link should never be able
        # to smuggle a newline just because its prefix happens to equal a known ref.
        assert _is_valid_tracking_link("JIRA-1\n/close", ["JIRA-1\n/close"]) is False

    def test_rejects_newline_in_otherwise_valid_url(self):
        assert _is_valid_tracking_link("https://example.com/incident/42\ninjected", []) is False

    def test_rejects_trailing_newline(self):
        assert _is_valid_tracking_link("https://example.com/incident/42\n", []) is False

    def test_accepts_clean_issue_key(self):
        assert _is_valid_tracking_link("PROJ-123", []) is True

    def test_accepts_clean_url(self):
        assert _is_valid_tracking_link("https://example.com/incident/42", []) is True

    def test_accepts_exact_incident_reference_match_without_newline(self):
        assert _is_valid_tracking_link("JIRA-1", ["JIRA-1"]) is True

    def test_rejects_empty_string(self):
        assert _is_valid_tracking_link("", []) is False

    def test_rejects_unrecognized_pattern_without_newline(self):
        assert _is_valid_tracking_link("just some text", []) is False


class TestEnableTerminalCloseGateFailsClosedOnMisconfig:
    """HIGH finding fix: an unrecognized ENABLE_TERMINAL_CLOSE_GATE value must resolve
    to True (gate enabled / fail-closed), matching the warning log emitted at import
    time -- previously the log claimed fail-closed but _raw_flag was never reset,
    so ENABLE_TERMINAL_CLOSE_GATE silently evaluated to False (fail-open)."""

    @staticmethod
    def _reload_with_env(monkeypatch, value):
        if value is None:
            monkeypatch.delenv("ENABLE_TERMINAL_CLOSE_GATE", raising=False)
        else:
            monkeypatch.setenv("ENABLE_TERMINAL_CLOSE_GATE", value)
        return importlib.reload(handlers_state)

    def test_unrecognized_value_fails_closed(self, monkeypatch, caplog):
        with caplog.at_level("WARNING"):
            reloaded = self._reload_with_env(monkeypatch, "garbage")
        assert reloaded.ENABLE_TERMINAL_CLOSE_GATE is True
        assert "defaulting to enabled" in caplog.text

    def test_empty_string_value_fails_closed(self, monkeypatch):
        reloaded = self._reload_with_env(monkeypatch, "")
        assert reloaded.ENABLE_TERMINAL_CLOSE_GATE is True

    def test_case_variant_value_fails_closed(self, monkeypatch):
        # Only the exact lowercase "false" disables the gate -- anything else,
        # including a plausible-looking variant, must fail closed.
        reloaded = self._reload_with_env(monkeypatch, "False")
        assert reloaded.ENABLE_TERMINAL_CLOSE_GATE is True

    def test_explicit_true_enables_gate(self, monkeypatch):
        reloaded = self._reload_with_env(monkeypatch, "true")
        assert reloaded.ENABLE_TERMINAL_CLOSE_GATE is True

    def test_explicit_false_disables_gate(self, monkeypatch):
        reloaded = self._reload_with_env(monkeypatch, "false")
        assert reloaded.ENABLE_TERMINAL_CLOSE_GATE is False

    def test_unset_env_var_defaults_to_enabled(self, monkeypatch):
        reloaded = self._reload_with_env(monkeypatch, None)
        assert reloaded.ENABLE_TERMINAL_CLOSE_GATE is True

    def teardown_method(self, method):
        # Restore the module to its normal (unset-env) state for any other test
        # in this file that imported handlers_state before this class reloaded it.
        import os
        os.environ.pop("ENABLE_TERMINAL_CLOSE_GATE", None)
        importlib.reload(handlers_state)
