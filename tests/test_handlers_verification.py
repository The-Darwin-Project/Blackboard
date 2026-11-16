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
    
    await handle_set_phase(ctx, "evt-1", {"phase": "close"}, None)
    
    # Check that append_and_broadcast was called with an error turn
    ctx.append_and_broadcast.assert_called_once()
    appended_turn = ctx.append_and_broadcast.call_args[0][1]
    assert appended_turn.actor == "system"
    assert "Cannot transition to 'close'" in appended_turn.result

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

    await handle_set_phase(ctx, "evt-1", {"phase": "close"}, None)

    ctx.append_and_broadcast.assert_called_once()
    appended_turn = ctx.append_and_broadcast.call_args[0][1]
    assert appended_turn.actor == "system"
    assert "Cannot transition to 'close'" in appended_turn.result


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


