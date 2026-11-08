# BlackBoard/tests/test_handlers_planning.py
# @ai-rules:
# 1. [Pattern]: Tests for handle_get_plan_progress in src/agents/handlers_planning.py.
# 2. [Pattern]: _progress() helper builds a mock event and returns the rendered progress evidence string.
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


async def _progress(conv):
    ctx = MagicMock()
    bb = MagicMock()
    ctx.get_blackboard.return_value = bb
    ctx.next_turn_number = AsyncMock(return_value=999)
    ctx.append_and_broadcast = AsyncMock()
    event_doc = MagicMock()
    event_doc.conversation = conv
    bb.get_event = AsyncMock(return_value=event_doc)
    await handle_get_plan_progress(ctx, "evt-test", {}, None)
    return ctx.append_and_broadcast.call_args[0][1].evidence


def _plan(turn, actor, steps, source=None):
    return ConversationTurn(
        turn=turn, actor=actor, action="plan",
        taskForAgent={"steps": steps, "source": source or actor},
    )


def _execute(turn, actor, result="done"):
    return ConversationTurn(turn=turn, actor=actor, action="execute", result=result)


def _plan_step(turn, actor, step_id, status):
    return ConversationTurn(
        turn=turn, actor=actor, action="plan_step",
        taskForAgent={"step_id": step_id, "status": status},
    )


@pytest.mark.asyncio
async def test_fallback_worker_plan_starts_pending_and_completes_on_execute():
    fallback = _plan(5, "developer", [{"id": "1", "agent": "developer", "summary": "Do work"}])
    ev = await _progress([fallback])
    assert "- [ ] Step 1: Do work (developer) -- pending" in ev
    assert "0/1 steps completed" in ev

    ev = await _progress([fallback, _execute(6, "developer")])
    assert "- [x] Step 1: Do work (developer) -- completed" in ev
    assert "1/1 steps completed" in ev


@pytest.mark.asyncio
async def test_orchestrator_plan_step_updates_any_agents_step():
    orch = _plan(1, "brain", [
        {"id": "1", "agent": "developer", "summary": "fix"},
        {"id": "2", "agent": "qe", "summary": "verify"},
    ])
    ev = await _progress([orch, _plan_step(2, "brain", "2", "completed"), _plan_step(3, "Architect", "1", "in_progress")])
    assert "- [x] Step 2: verify (qe) -- completed" in ev
    assert "- [~] Step 1: fix (developer) -- in_progress" in ev


@pytest.mark.asyncio
async def test_orchestrator_execute_does_not_complete_worker_steps():
    orch = _plan(1, "brain", [{"id": "1", "agent": "developer", "summary": "fix"}])
    ev = await _progress([orch, _execute(2, "brain"), _execute(3, "architect")])
    assert "- [ ] Step 1: fix (developer) -- pending" in ev


@pytest.mark.asyncio
async def test_single_execute_completes_one_step_and_prefers_in_progress():
    orch = _plan(1, "brain", [
        {"id": "1", "agent": "developer", "summary": "a"},
        {"id": "2", "agent": "developer", "summary": "b"},
    ])
    ev = await _progress([orch, _execute(2, "developer")])
    assert "- [x] Step 1: a (developer) -- completed" in ev
    assert "- [ ] Step 2: b (developer) -- pending" in ev

    ev = await _progress([orch, _plan_step(2, "developer", "2", "in_progress"), _execute(3, "developer")])
    assert "- [ ] Step 1: a (developer) -- pending" in ev
    assert "- [x] Step 2: b (developer) -- completed" in ev


@pytest.mark.asyncio
async def test_blocked_step_not_overwritten_by_auto_complete():
    orch = _plan(1, "brain", [{"id": "1", "agent": "developer", "summary": "a"}])
    ev = await _progress([orch, _plan_step(2, "brain", "1", "blocked"), _execute(3, "developer")])
    assert "- [!] Step 1: a (developer) -- blocked" in ev


@pytest.mark.asyncio
async def test_failed_execute_does_not_auto_complete():
    orch = _plan(1, "brain", [{"id": "1", "agent": "developer", "summary": "a"}])
    ev = await _progress([orch, _execute(2, "developer", result="Error: Agent task failed")])
    assert "- [ ] Step 1: a (developer) -- pending" in ev


@pytest.mark.asyncio
async def test_replan_ignores_turns_before_latest_orchestrator_plan():
    old = _plan(1, "brain", [{"id": "1", "agent": "developer", "summary": "old"}])
    pre = _execute(2, "developer")  # belongs to the old plan
    pre_step = _plan_step(3, "brain", "1", "completed")
    replan = _plan(4, "brain", [{"id": "1", "agent": "developer", "summary": "new"}])
    ev = await _progress([old, pre, pre_step, replan])
    assert "- [ ] Step 1: new (developer) -- pending" in ev
    assert "0/1 steps completed" in ev


@pytest.mark.asyncio
async def test_orchestrator_detection_uses_actor_and_source():
    # Worker actor with orchestrator source is an orchestrator plan -> beats a later worker proposal
    orch = _plan(1, "developer", [{"id": "1", "agent": "developer", "summary": "orch"}], source="Brain")
    worker = _plan(2, "developer", [{"id": "1", "agent": "developer", "summary": "worker"}])
    ev = await _progress([orch, worker])
    assert "Step 1: orch (developer)" in ev

    # Orchestrator actor with worker source is still an orchestrator plan
    orch2 = _plan(1, "Architect", [{"id": "1", "agent": "developer", "summary": "orch2"}], source="developer")
    ev = await _progress([orch2, worker])
    assert "Step 1: orch2 (developer)" in ev


@pytest.mark.asyncio
async def test_cross_agent_plan_step_is_ignored_and_logged(caplog):
    orch = _plan(1, "brain", [{"id": "1", "agent": "qe", "summary": "verify"}])
    with caplog.at_level("WARNING", logger="darwin.brain"):
        ev = await _progress([orch, _plan_step(2, "developer", "1", "completed")])
    assert "- [ ] Step 1: verify (qe) -- pending" in ev
    assert any("Ignored plan_step update for step 1" in r.message for r in caplog.records)
