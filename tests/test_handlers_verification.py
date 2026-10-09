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
