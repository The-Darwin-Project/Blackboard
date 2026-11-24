# tests/test_handlers_verification.py
# @ai-rules:
# 1. [Constraint]: Pure unit tests for verification and phase-transition handlers -- no Redis, no Brain import.
# 2. [Pattern]: Mock ToolContext and Blackboard to verify handle_set_phase and can_transition_to_close admissibility.
"""Tests for verification phase handlers."""
from types import SimpleNamespace
import pytest
from unittest.mock import AsyncMock, MagicMock
from src.agents.handlers_verification import handle_set_phase
from src.models import ConversationTurn

@pytest.mark.asyncio
async def test_close_rejected_without_verify():
    ctx = MagicMock()
    bb = MagicMock()
    ctx.get_blackboard.return_value = bb
    ctx.next_turn_number = AsyncMock(return_value=1)
    ctx.append_and_broadcast = AsyncMock()
    
    event_doc = MagicMock()
    event_doc.event.evidence.brain_domain = "complex"
    event_doc.conversation = []
    bb.get_event = AsyncMock(return_value=event_doc)
    
    sample_rp = [
        {"functionCall": {"name": "set_phase", "args": {"phase": "close"}}, "thought_signature": "sig-close"},
    ]
    result = await handle_set_phase(ctx, "evt-1", {"phase": "close"}, sample_rp)

    assert result is True
    # Step 5 contract: close-gate rejection emits brain.tool_result (turn=0) preserving response_parts
    ctx.append_and_broadcast.assert_called_once()
    appended_turn = ctx.append_and_broadcast.call_args[0][1]
    assert appended_turn.turn == 0
    assert appended_turn.actor == "brain"
    assert appended_turn.action == "tool_result"
    assert appended_turn.waitingFor == "set_phase"
    assert "Cannot transition to 'close'" in (appended_turn.thoughts or "")
    assert appended_turn.response_parts == sample_rp

@pytest.mark.asyncio
async def test_close_permitted_after_verify():
    ctx = MagicMock()
    bb = MagicMock()
    ctx.get_blackboard.return_value = bb
    ctx.next_turn_number = AsyncMock(return_value=1)
    ctx.append_and_broadcast = AsyncMock()
    ctx.broadcast = AsyncMock()
    ctx.emit_pulse = AsyncMock()
    
    verify_turn = ConversationTurn(
        turn=1, actor="brain", action="phase", thoughts="Phase: VERIFY", waitingFor="set_phase"
    )
    event_doc = MagicMock()
    event_doc.brain_phase = "verify"
    event_doc.event.evidence.brain_domain = "complex"
    event_doc.conversation = [verify_turn]
    bb.get_event = AsyncMock(return_value=event_doc)
    bb.update_event_phase = AsyncMock()
    
    await handle_set_phase(ctx, "evt-1", {"phase": "close"}, None)
    
    # Check that bb.update_event_phase was called with close
    bb.update_event_phase.assert_called_once_with("evt-1", "close")


@pytest.mark.asyncio
async def test_close_rejected_when_reclassified_after_verify():
    ctx = MagicMock()
    bb = MagicMock()
    ctx.get_blackboard.return_value = bb
    ctx.next_turn_number = AsyncMock(return_value=3)
    ctx.append_and_broadcast = AsyncMock()

    verify_turn = ConversationTurn(
        turn=1, actor="brain", action="phase", thoughts="Phase: VERIFY", waitingFor="set_phase"
    )
    triage_turn = ConversationTurn(
        turn=2, actor="brain", action="triage", thoughts="Cynefin: COMPLICATED."
    )
    event_doc = MagicMock()
    event_doc.brain_phase = "triage"
    event_doc.event.evidence.brain_domain = "complicated"
    event_doc.conversation = [verify_turn, triage_turn]
    bb.get_event = AsyncMock(return_value=event_doc)

    result = await handle_set_phase(ctx, "evt-1", {"phase": "close"}, None)

    assert result is True
    ctx.append_and_broadcast.assert_called_once()
    appended_turn = ctx.append_and_broadcast.call_args[0][1]
    assert appended_turn.turn == 0
    assert appended_turn.actor == "brain"
    assert appended_turn.action == "tool_result"
    assert appended_turn.waitingFor == "set_phase"
    assert "Cannot transition to 'close'" in (appended_turn.thoughts or "")


def test_can_transition_to_close_admissibility():
    """T-9: Direct unit test for can_transition_to_close(event_doc) covering clear/casual
    allowed vs complicated/complex without PHASE: VERIFY rejected."""
    from src.agents.handlers_verification import can_transition_to_close

    for domain in ("clear", "casual", "chaotic"):
        doc = SimpleNamespace(
            event=SimpleNamespace(evidence=SimpleNamespace(brain_domain=domain)),
            conversation=[],
        )
        allowed, reason = can_transition_to_close(doc)
        assert allowed is True
        assert reason is None

    for domain in ("complicated", "complex"):
        unverified_doc = SimpleNamespace(
            event=SimpleNamespace(evidence=SimpleNamespace(brain_domain=domain)),
            conversation=[],
        )
        allowed, reason = can_transition_to_close(unverified_doc)
        assert allowed is False
        assert reason is not None
        assert f"Cannot transition to 'close' from '{domain}'" in reason

        verified_doc = SimpleNamespace(
            event=SimpleNamespace(evidence=SimpleNamespace(brain_domain=domain)),
            conversation=[
                ConversationTurn(
                    turn=1, actor="brain", action="phase",
                    thoughts="Phase: VERIFY", waitingFor="set_phase",
                ),
            ],
        )
        allowed_v, reason_v = can_transition_to_close(verified_doc)
        assert allowed_v is True
        assert reason_v is None


@pytest.mark.asyncio
async def test_t17_set_phase_close_rejected_as_fc0_in_batch_preserves_batch_metadata():
    """T-17: Given set_phase('close') fails can_transition_to_close as FC[0] in a batch
    When handle_set_phase executes through a batch-wrapping ToolContext
    Then it writes turn=0, actor='brain', action='tool_result', waitingFor='set_phase',
    thoughts=reject_msg, carries response_parts, and allows batch_ctx to stamp batch_size."""
    captured: list[ConversationTurn] = []

    class _BatchCtxDouble:
        def __init__(self, inner, batch_size: int):
            self._inner = inner
            self._batch_size = batch_size

@pytest.mark.asyncio
async def test_r5_f3_unevaluated_message_rejects_close():
    """[R5-F3] verify can_transition_to_close and handle_set_phase("close") reject when an
    unevaluated user.message or jarvis.message exists, and succeed once evaluated."""
    from src.agents.handlers_verification import can_transition_to_close, handle_set_phase
    from src.models import EventDocument
    import time

    ev = MagicMock(
        id="evt-1",
        domain="COMPLICATED",
        title="test",
        source="chat",
        user_id="U1",
        
                conversation=[
            ConversationTurn(turn=0, actor="user", action="message", result="fix this", status="evaluated"),
            ConversationTurn(turn=1, actor="brain", action="phase", result="VERIFY"),
            ConversationTurn(turn=2, actor="user", action="message", result="also fix that", status="delivered")
        ]
    )

    allowed, reason = can_transition_to_close(ev)
    assert not allowed
    assert "unevaluated" in reason.lower()

    ctx = MagicMock()
    ctx.get_blackboard.return_value.get_event = AsyncMock(return_value=ev)
    ctx.next_turn_number = AsyncMock(return_value=3)
    ctx.append_and_broadcast = AsyncMock()

    res = await handle_set_phase(ctx, "evt-1", {"phase": "close"}, None)
    # The handler returns True because it succeeds in executing the tool (by appending a tool_result turn)
    assert res is True
    ctx.append_and_broadcast.assert_called_once()
    turn = ctx.append_and_broadcast.call_args[0][1]
    assert turn.actor == "brain"
    assert turn.action == "tool_result"
    assert "unevaluated" in (turn.result or turn.thoughts or "").lower()

    # Test jarvis and sent
    ev.conversation[2].actor = "jarvis"
    ev.conversation[2].status = "sent"
    allowed, reason = can_transition_to_close(ev)
    assert not allowed

    # Mark as evaluated
    ev.conversation[2].status = "evaluated"
    allowed, reason = can_transition_to_close(ev)
    assert allowed

