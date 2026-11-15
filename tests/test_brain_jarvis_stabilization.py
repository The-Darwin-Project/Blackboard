# BlackBoard/tests/test_brain_jarvis_stabilization.py
# @ai-rules:
# 1. [Constraint]: Verify JARVIS stabilization.
import pytest
import time
from unittest.mock import AsyncMock, MagicMock
from src.agents.brain import Brain
from src.models import EventDocument, ConversationTurn
import asyncio

class MockLiveAPIAdapter:
    def __init__(self):
        self.request_stabilization_watch = AsyncMock(return_value=True)
    def is_operational_peer_ready(self):
        return True

def _make_brain():
    bb = AsyncMock()
    bb.get_active_events_with_status = AsyncMock(return_value={})
    bb.mark_turns_delivered = AsyncMock()
    brain = Brain(blackboard=bb, agents={})
    brain._live_adapter = MockLiveAPIAdapter()
    brain._slack_notify = AsyncMock()
    brain.enqueue_for_processing = MagicMock()
    return brain

@pytest.mark.asyncio
async def test_t11_automated_event_3_transient_errors_handoffs_to_jarvis():
    brain = _make_brain()
    brain._escalate_to_human = AsyncMock()
    brain._append_and_broadcast = AsyncMock()
    
    turns = [
        ConversationTurn(turn=1, actor="brain", action="error", thoughts="429 RESOURCE_EXHAUSTED"),
        ConversationTurn(turn=1, actor="brain", action="error", thoughts="429 RESOURCE_EXHAUSTED"),
        ConversationTurn(turn=1, actor="brain", action="error", thoughts="429 RESOURCE_EXHAUSTED")
    ]
    ev = EventDocument(id="evt-1", source="headhunter", conversation=turns, status="active", service="test-svc", event={"reason": "", "evidence": "x"})
    brain.blackboard.get_event = AsyncMock(return_value=ev)
    brain.blackboard.get_active_events_with_status = AsyncMock(return_value={"evt-1": "active"})
    
    await brain._scan_active_for_reconcile()
    
    brain._escalate_to_human.assert_not_called()
    assert "evt-1" in getattr(brain, "_waiting_for_jarvis", {})
    assert "evt-1" not in getattr(brain, "_waiting_for_user", set())
    brain._live_adapter.request_stabilization_watch.assert_awaited_once()

    # Check appended turn
    appended_turn = brain._append_and_broadcast.call_args[0][1]
    assert appended_turn.actor == "brain"
    assert appended_turn.action == "wait"
    assert appended_turn.waitingFor == "jarvis"

    # Check snapshot
    snap = brain.get_system_stability_snapshot()
    for key in ["tokens_used_60s", "tpm_limit", "tokens_remaining", "utilization_pct", "active_reservations", "high_priority_waiters", "pending_jarvis_events", "active_wip"]:
        assert key in snap

    # Check clear_jarvis_wait
    brain._jarvis_recovery_rounds["evt-1"] = 1
    brain.clear_jarvis_wait("evt-1")
    assert "evt-1" not in brain._waiting_for_jarvis
    assert brain._jarvis_recovery_rounds["evt-1"] == 1

@pytest.mark.asyncio
async def test_t12_jarvis_stabilization_loop_timeout_fallback():
    brain = _make_brain()
    brain._waiting_for_jarvis = {"evt-1": time.time()}
    brain._jarvis_wait_tasks = {}
    brain._append_and_broadcast = AsyncMock()
    
    # Execute loop directly with short timeout
    task = asyncio.create_task(brain._jarvis_stabilization_loop("evt-1", timeout_s=0.02))
    brain._jarvis_wait_tasks["evt-1"] = task
    
    await task
    
    assert "evt-1" not in getattr(brain, "_waiting_for_jarvis", {})
    assert "evt-1" not in getattr(brain, "_jarvis_wait_tasks", {})
    brain._append_and_broadcast.assert_called()
    
    appended_turn = brain._append_and_broadcast.call_args[0][1]
    assert appended_turn.actor == "dispatcher"
    
    assert brain.enqueue_for_processing.call_count > 0

@pytest.mark.asyncio
async def test_t12_non_jarvis_fallback_path():
    brain = _make_brain()
    brain._escalate_to_human = AsyncMock()
    brain._append_and_broadcast = AsyncMock()
    brain._live_adapter = None  # No live adapter
    
    turns = [
        ConversationTurn(turn=1, actor="brain", action="error", thoughts="429 RESOURCE_EXHAUSTED"),
        ConversationTurn(turn=1, actor="brain", action="error", thoughts="429 RESOURCE_EXHAUSTED"),
        ConversationTurn(turn=1, actor="brain", action="error", thoughts="429 RESOURCE_EXHAUSTED")
    ]
    ev = EventDocument(id="evt-1", source="headhunter", conversation=turns, status="active", service="test-svc", event={"reason": "", "evidence": "x"})
    brain.blackboard.get_event = AsyncMock(return_value=ev)
    brain.blackboard.get_active_events_with_status = AsyncMock(return_value={"evt-1": "active"})
    
    await brain._scan_active_for_reconcile()
    
    # Should not escalate, but enter fallback cooling wait
    brain._escalate_to_human.assert_not_called()
    assert "evt-1" in getattr(brain, "_waiting_for_jarvis", {})
    assert "evt-1" in getattr(brain, "_jarvis_wait_tasks", {})

@pytest.mark.asyncio
async def test_t13_permanent_burst_error_escalates_to_human():
    brain = _make_brain()
    brain._escalate_to_human = AsyncMock()
    
    turns = [
        ConversationTurn(turn=1, actor="brain", action="error", thoughts="Request of 250000 tokens exceeds the burst limit of 200000 tokens"),
        ConversationTurn(turn=1, actor="brain", action="error", thoughts="Request of 250000 tokens exceeds the burst limit of 200000 tokens"),
        ConversationTurn(turn=1, actor="brain", action="error", thoughts="Request of 250000 tokens exceeds the burst limit of 200000 tokens")
    ]
    ev = EventDocument(id="evt-1", source="headhunter", conversation=turns, status="active", service="test-svc", event={"reason": "", "evidence": "x"})
    brain.blackboard.get_event = AsyncMock(return_value=ev)
    brain.blackboard.get_active_events_with_status = AsyncMock(return_value={"evt-1": "active"})
    
    await brain._scan_active_for_reconcile()
    brain._escalate_to_human.assert_awaited()

    # Second case: _jarvis_recovery_rounds >= 2 triggers escalate on transient
    brain._escalate_to_human.reset_mock()
    turns2 = [
        ConversationTurn(turn=1, actor="brain", action="error", thoughts="429 RESOURCE_EXHAUSTED"),
        ConversationTurn(turn=1, actor="brain", action="error", thoughts="429 RESOURCE_EXHAUSTED"),
        ConversationTurn(turn=1, actor="brain", action="error", thoughts="429 RESOURCE_EXHAUSTED")
    ]
    ev2 = EventDocument(id="evt-2", source="headhunter", conversation=turns2, status="active", service="test-svc", event={"reason": "", "evidence": "x"})
    brain.blackboard.get_event = AsyncMock(return_value=ev2)
    brain.blackboard.get_active_events_with_status = AsyncMock(return_value={"evt-2": "active"})
    brain._jarvis_recovery_rounds = {"evt-2": 2}
    
    await brain._scan_active_for_reconcile()
    brain._escalate_to_human.assert_awaited()

@pytest.mark.asyncio
async def test_t15_waiting_for_jarvis_counts_as_wip():
    brain = _make_brain()
    brain.blackboard.get_active_events_with_status = AsyncMock(return_value={"evt-1": "active"})
    brain._waiting_for_jarvis = {"evt-1": time.time()}
    wip = await brain._count_global_wip()
    assert wip >= 1

@pytest.mark.asyncio
async def test_close_and_broadcast_pops_recovery_rounds():
    brain = _make_brain()
    brain._jarvis_recovery_rounds["evt-1"] = 2
    brain.agents["_archivist_memory"] = AsyncMock()
    brain._slack_notify = AsyncMock()
    await brain._close_and_broadcast("evt-1", "Closed", None)
    assert "evt-1" not in brain._jarvis_recovery_rounds

@pytest.mark.asyncio
async def test_is_transient_llm_error_turn_server_disconnected():
    brain = _make_brain()
    t = ConversationTurn(turn=1, actor="brain", action="error", thoughts="Server disconnected")
    assert brain._is_transient_llm_error_turn(t) is True
