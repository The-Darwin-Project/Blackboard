# tests/test_handle_close_event.py
# @ai-rules:
# 1. [Constraint]: Pure unit tests — mock ToolContext + BlackboardState, no real Redis.
# 2. [Pattern]: Uses ConversationTurn objects (not dicts) to match production path.
# 3. [Gotcha]: handle_close_event is async — all tests use pytest-asyncio.
"""Tests for handle_close_event pessimistic re-check (commit 76803ab0).

Covers: abort on unevaluated user/jarvis message, happy-path close,
None/closed event fallback, brain.phase scan boundary, response_parts threading.
"""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.agents.handlers_state import handle_close_event
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


def _event(conversation: list[ConversationTurn], status: str = "active"):
    return SimpleNamespace(
        conversation=conversation,
        status=SimpleNamespace(value=status),
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
        result = await handle_close_event(ctx, "evt-1", {"summary": "Done."}, None)
        assert result is False
        ctx.close_and_broadcast.assert_called_once_with("evt-1", "Done.")
        ctx.append_and_broadcast.assert_not_called()

    @pytest.mark.asyncio
    async def test_empty_conversation_closes(self):
        event = _event([])
        ctx, _ = _mock_ctx(event)
        result = await handle_close_event(ctx, "evt-1", {}, None)
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
        result = await handle_close_event(ctx, "evt-1", {}, None)
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
        result = await handle_close_event(ctx, "evt-1", {}, None)
        assert result is False
        ctx.close_and_broadcast.assert_called_once()


class TestNonBlockingTurns:
    """Non-message actions and non-user/jarvis actors must not trigger abort."""

    @pytest.mark.asyncio
    async def test_user_confirm_ignored(self):
        event = _event([_turn("user", "confirm", MessageStatus.SENT)])
        ctx, _ = _mock_ctx(event)
        result = await handle_close_event(ctx, "evt-1", {}, None)
        assert result is False
        ctx.close_and_broadcast.assert_called_once()

    @pytest.mark.asyncio
    async def test_sysadmin_message_ignored(self):
        event = _event([_turn("sysadmin", "message", MessageStatus.SENT)])
        ctx, _ = _mock_ctx(event)
        result = await handle_close_event(ctx, "evt-1", {}, None)
        assert result is False
        ctx.close_and_broadcast.assert_called_once()
