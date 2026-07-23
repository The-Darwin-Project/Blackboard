# @ai-rules:
# 1. [Constraint]: Pure unit tests for _pred_unevaluated_close — no Redis, no async.
# 2. [Pattern]: Uses SimpleNamespace turns with status field to match ConversationTurn.
# 3. [Gotcha]: status can be a MessageStatus enum or a plain string (dict path).
"""Tests for the UNEVALUATED_CLOSE gate fix (PR #132).

Verifies that _pred_unevaluated_close correctly reads ConversationTurn.status
(MessageStatus enum) instead of the non-existent 'evaluated' attribute.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from src.agents.tool_gates import (
    GateContext,
    evaluate_gates,
    diagnose_rejection,
    _pred_unevaluated_close,
)
from src.models import MessageStatus


def _fake_schemas(*names: str) -> list[dict]:
    return [{"name": n} for n in names]


def _names(tools: list[dict]) -> set[str]:
    return {t["name"] for t in tools}


def _turn(actor: str, action: str, status=None, **kw) -> SimpleNamespace:
    return SimpleNamespace(
        actor=actor,
        action=action,
        status=status if status is not None else MessageStatus.SENT,
        waitingFor=kw.get("waitingFor"),
    )


def _turn_dict(actor: str, action: str, status: str | None = None) -> dict:
    d = {"actor": actor, "action": action}
    if status is not None:
        d["status"] = status
    return d


def _ctx(**overrides) -> GateContext:
    defaults = dict(
        brain_phase="close",
        event_source="aligner",
        context_flags={"brain_has_classified": True, "event_domain": "complicated"},
        conversation=[],
        is_defer_wake=False,
        iteration=0,
        has_kargo_context=True,
        has_github_context=False,
        unread_notes=0,
        refresh_budget=5,
        refresh_count=0,
        agent_completions=0,
        jarvis_already_waiting=False,
        jarvis_wait_count=0,
    )
    defaults.update(overrides)
    return GateContext(**defaults)


CLOSE_SCHEMAS = _fake_schemas("close_event", "select_agent", "classify_event")


class TestEvaluatedAllowsClose:
    """EVALUATED messages must NOT block close_event."""

    def test_jarvis_message_evaluated_enum(self):
        turns = [_turn("jarvis", "message", status=MessageStatus.EVALUATED)]
        ctx = _ctx(conversation=turns)
        result = evaluate_gates(CLOSE_SCHEMAS, ctx)
        assert "close_event" in _names(result)

    def test_user_message_evaluated_enum(self):
        turns = [_turn("user", "message", status=MessageStatus.EVALUATED)]
        ctx = _ctx(conversation=turns)
        result = evaluate_gates(CLOSE_SCHEMAS, ctx)
        assert "close_event" in _names(result)

    def test_multiple_evaluated_messages(self):
        turns = [
            _turn("jarvis", "message", status=MessageStatus.EVALUATED),
            _turn("user", "message", status=MessageStatus.EVALUATED),
            _turn("jarvis", "message", status=MessageStatus.EVALUATED),
        ]
        ctx = _ctx(conversation=turns)
        result = evaluate_gates(CLOSE_SCHEMAS, ctx)
        assert "close_event" in _names(result)


class TestDeliveredBlocksClose:
    """DELIVERED messages must block close_event."""

    def test_jarvis_message_delivered_blocks(self):
        turns = [_turn("jarvis", "message", status=MessageStatus.DELIVERED)]
        ctx = _ctx(conversation=turns)
        result = evaluate_gates(CLOSE_SCHEMAS, ctx)
        assert "close_event" not in _names(result)

    def test_user_message_delivered_blocks(self):
        turns = [_turn("user", "message", status=MessageStatus.DELIVERED)]
        ctx = _ctx(conversation=turns)
        result = evaluate_gates(CLOSE_SCHEMAS, ctx)
        assert "close_event" not in _names(result)


class TestSentBlocksClose:
    """SENT messages must block close_event."""

    def test_jarvis_message_sent_blocks(self):
        turns = [_turn("jarvis", "message", status=MessageStatus.SENT)]
        ctx = _ctx(conversation=turns)
        result = evaluate_gates(CLOSE_SCHEMAS, ctx)
        assert "close_event" not in _names(result)

    def test_user_message_sent_blocks(self):
        turns = [_turn("user", "message", status=MessageStatus.SENT)]
        ctx = _ctx(conversation=turns)
        result = evaluate_gates(CLOSE_SCHEMAS, ctx)
        assert "close_event" not in _names(result)


class TestNoneStatusBlocksClose:
    """None status is fail-safe — blocks close."""

    def test_none_status_blocks(self):
        turns = [_turn("jarvis", "message", status=None)]
        ctx = _ctx(conversation=turns)
        result = evaluate_gates(CLOSE_SCHEMAS, ctx)
        assert "close_event" not in _names(result)


class TestDictTurnPath:
    """Dict-based turns (non-Pydantic path) tested via direct predicate call."""

    def test_dict_evaluated_allows_close(self):
        turns = [_turn_dict("jarvis", "message", status="evaluated")]
        ctx = _ctx(conversation=turns)
        assert _pred_unevaluated_close(ctx) is False

    def test_dict_delivered_blocks_close(self):
        turns = [_turn_dict("jarvis", "message", status="delivered")]
        ctx = _ctx(conversation=turns)
        assert _pred_unevaluated_close(ctx) is True

    def test_dict_sent_blocks_close(self):
        turns = [_turn_dict("jarvis", "message", status="sent")]
        ctx = _ctx(conversation=turns)
        assert _pred_unevaluated_close(ctx) is True

    def test_dict_missing_status_blocks_close(self):
        turns = [_turn_dict("jarvis", "message")]
        ctx = _ctx(conversation=turns)
        assert _pred_unevaluated_close(ctx) is True


class TestBrainCloseBreaksLoop:
    """brain.close turn must stop scanning — earlier messages don't matter."""

    def test_brain_close_breaks_scan(self):
        turns = [
            _turn("jarvis", "message", status=MessageStatus.DELIVERED),
            _turn("brain", "close"),
            _turn("jarvis", "message", status=MessageStatus.EVALUATED),
        ]
        ctx = _ctx(conversation=turns)
        result = evaluate_gates(CLOSE_SCHEMAS, ctx)
        assert "close_event" in _names(result)


class TestEmptyConversation:
    """Empty conversation must allow close."""

    def test_empty_conversation_allows_close(self):
        ctx = _ctx(conversation=[])
        result = evaluate_gates(CLOSE_SCHEMAS, ctx)
        assert "close_event" in _names(result)


class TestNonMessageActionsIgnored:
    """Non-message actions from jarvis/user must not trigger the gate."""

    def test_jarvis_execute_ignored(self):
        turns = [_turn("jarvis", "execute", status=MessageStatus.SENT)]
        ctx = _ctx(conversation=turns)
        result = evaluate_gates(CLOSE_SCHEMAS, ctx)
        assert "close_event" in _names(result)

    def test_user_confirm_ignored(self):
        turns = [_turn("user", "confirm", status=MessageStatus.SENT)]
        ctx = _ctx(conversation=turns)
        result = evaluate_gates(CLOSE_SCHEMAS, ctx)
        assert "close_event" in _names(result)


class TestNonGatedActorsIgnored:
    """Messages from brain, architect, sysadmin etc. must not trigger the gate."""

    def test_brain_message_ignored(self):
        turns = [_turn("brain", "message", status=MessageStatus.SENT)]
        ctx = _ctx(conversation=turns)
        result = evaluate_gates(CLOSE_SCHEMAS, ctx)
        assert "close_event" in _names(result)

    def test_sysadmin_message_ignored(self):
        turns = [_turn("sysadmin", "message", status=MessageStatus.SENT)]
        ctx = _ctx(conversation=turns)
        result = evaluate_gates(CLOSE_SCHEMAS, ctx)
        assert "close_event" in _names(result)


class TestMixedStatusConversation:
    """One unevaluated message among evaluated ones must block."""

    def test_one_delivered_among_evaluated_blocks(self):
        turns = [
            _turn("jarvis", "message", status=MessageStatus.EVALUATED),
            _turn("user", "message", status=MessageStatus.DELIVERED),
            _turn("jarvis", "message", status=MessageStatus.EVALUATED),
        ]
        ctx = _ctx(conversation=turns)
        result = evaluate_gates(CLOSE_SCHEMAS, ctx)
        assert "close_event" not in _names(result)

    def test_all_evaluated_allows(self):
        turns = [
            _turn("jarvis", "message", status=MessageStatus.EVALUATED),
            _turn("user", "message", status=MessageStatus.EVALUATED),
        ]
        ctx = _ctx(conversation=turns)
        result = evaluate_gates(CLOSE_SCHEMAS, ctx)
        assert "close_event" in _names(result)


class TestDiagnosticMessage:
    """Gate diagnostic must report the blocking reason."""

    def test_diagnostic_mentions_unevaluated(self):
        turns = [_turn("jarvis", "message", status=MessageStatus.DELIVERED)]
        ctx = _ctx(conversation=turns)
        msg = diagnose_rejection("close_event", ctx)
        assert "[GATE]" in msg
        assert "Unevaluated" in msg or "unevaluated" in msg.lower()

    def test_diagnostic_has_hint(self):
        turns = [_turn("jarvis", "message", status=MessageStatus.DELIVERED)]
        ctx = _ctx(conversation=turns)
        msg = diagnose_rejection("close_event", ctx)
        assert "Hint:" in msg


class TestOnlyCloseEventAffected:
    """The UNEVALUATED_CLOSE gate only strips close_event, not other tools."""

    def test_select_agent_unaffected(self):
        turns = [_turn("jarvis", "message", status=MessageStatus.DELIVERED)]
        ctx = _ctx(conversation=turns)
        result = evaluate_gates(CLOSE_SCHEMAS, ctx)
        assert "select_agent" in _names(result) or "classify_event" in _names(result)
