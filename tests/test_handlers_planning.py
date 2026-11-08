# BlackBoard/tests/test_handlers_planning.py
# @ai-rules:
# 1. [Pattern]: Tests for handle_get_plan_progress in src/agents/handlers_planning.py.
import pytest
from unittest.mock import AsyncMock, MagicMock
from src.agents.handlers_planning import handle_get_plan_progress
from src.models import ConversationTurn


@pytest.mark.asyncio
async def test_get_plan_progress_orchestrator_precedence():
    ctx = MagicMock()
    bb = MagicMock()
    ctx.get_blackboard.return_value = bb
    ctx.next_turn_number = AsyncMock(return_value=40)
    ctx.append_and_broadcast = AsyncMock()

    # Conversation matching evt-e3805021
    conv = [
        ConversationTurn(
            turn=10,
            actor="brain",
            action="plan",
            taskForAgent={
                "steps": [
                    {"id": "1", "agent": "code_reviewer", "summary": "Inspect PR #316"},
                    {"id": "2", "agent": "developer", "summary": "Remediate findings"},
                    {"id": "3", "agent": "qe", "summary": "Verify fixes"},
                ],
                "source": "brain",
            },
        ),
        ConversationTurn(
            turn=22,
            actor="code_reviewer",
            action="execute",
            result="6 lenses complete",
        ),
        ConversationTurn(
            turn=34,
            actor="developer",
            action="plan_step",
            taskForAgent={"step_id": "3", "status": "completed"},
        ),
        ConversationTurn(
            turn=36,
            actor="developer",
            action="plan",
            taskForAgent={
                "steps": [{"id": "3", "agent": "", "summary": "In-branch remediation pushed as 3dcba8eb"}],
                "source": "developer",
            },
        ),
    ]

    event_doc = MagicMock()
    event_doc.conversation = conv
    bb.get_event = AsyncMock(return_value=event_doc)

    res = await handle_get_plan_progress(ctx, "evt-e3805021", {}, None)
    assert res is True
    ctx.append_and_broadcast.assert_called_once()
    turn = ctx.append_and_broadcast.call_args[0][1]
    assert turn.actor == "brain"
    assert turn.action == "tool_result"
    evidence = turn.evidence
    # Step 1 should be completed (code_reviewer execute)
    assert "- [x] Step 1: Inspect PR #316 (code_reviewer) -- completed" in evidence
    # Step 2 should be completed (developer plan deliverable)
    assert "- [x] Step 2: Remediate findings (developer) -- completed" in evidence
    # Step 3 should remain pending (developer's hijacking of step 3 was rejected)
    assert "- [ ] Step 3: Verify fixes (qe) -- pending" in evidence
    assert "2/3 steps completed" in evidence
