# tests/test_evt_996e33ec_loop_wiring.py
# @ai-rules:
# 1. [Constraint]: Integration-level pin for the evt-996e33ec fix: drives the REAL Brain._process_event_inner
#    loop against a REAL BlackboardState (fakeredis). Only _process_with_llm is scripted.
# 2. [Pattern]: Complements the pure-helper tests in test_brain_loop_plumbing.py. Those pin
#    _compute_processed_up_to; these pin the call site (acknowledged_interrupts wiring + mark_turns_status).
# 3. [Gotcha]: Mutation-tested: replacing the call site with `processed_up_to = turn_snapshot`, or recording
#    acknowledged_interrupts with a bogus length, must fail this file.
"""QE loop-wiring tests for evt-996e33ec (seeded first turn + PROCESSED scope)."""
from __future__ import annotations

import json
import time
from unittest.mock import AsyncMock, MagicMock

import fakeredis.aioredis
import pytest

from src.agents.brain import Brain
from src.models import ConversationTurn, EventEvidence, MessageStatus
from src.state.blackboard import BlackboardState


@pytest.fixture
async def bb():
    state = BlackboardState.__new__(BlackboardState)
    state.redis = fakeredis.aioredis.FakeRedis()
    state.EVENT_PREFIX = "darwin:event:"
    state.EVENT_QUEUE = "darwin:queue"
    state.EVENT_ACTIVE = "darwin:event:active"
    state.EVENT_WAITING_APPROVAL = "darwin:event:waiting_approval"
    state.EVENT_CLOSED = "darwin:event:closed"
    state.SLACK_THREAD_PREFIX = "darwin:slack:thread:"
    return state


def _make_brain(bb: BlackboardState) -> Brain:
    # Stub external collaborators only; the blackboard is real.
    bb.record_event = AsyncMock()
    bb.append_journal = AsyncMock()
    brain = Brain(blackboard=bb, agents={})
    brain._broadcast = AsyncMock()
    brain._broadcast_turn = AsyncMock()
    brain._broadcast_status_update = AsyncMock()
    brain._get_adapter = AsyncMock(return_value=MagicMock())
    return brain


async def _create(bb, initial_turns=None) -> str:
    return await bb.create_event(
        source="chat", service="general", reason="Hi Friday",
        evidence=EventEvidence(
            display_text="Hi Friday", source_type="chat", triggered_by="Tal Hason",
            domain="disorder", severity="info",
        ),
        created_by_email="thason@redhat.com",
        initial_turns=initial_turns,
    )


def _user(text="Hi Friday") -> ConversationTurn:
    return ConversationTurn(turn=1, actor="user", action="message", thoughts=text, user_name="Tal Hason")


def _brain(action: str) -> ConversationTurn:
    return ConversationTurn(turn=0, actor="brain", action=action, thoughts=action)


async def _statuses(bb, eid) -> dict[int, str]:
    ev = await bb.get_event(eid)
    return {t.turn: t.status.value for t in ev.conversation}


async def _age_queue_stamp(bb, eid) -> None:
    """Step past the blank-chat-event grace window (B8) so the legacy blank-snapshot race is reachable."""
    ev = await bb.get_event(eid)
    ev.queued_at = time.time() - 600
    await bb.redis.set(f"{bb.EVENT_PREFIX}{eid}", json.dumps(ev.model_dump()))


def _scripted_llm(brain: Brain, bb, script):
    """script: list of async callables(eid), one per LLM iteration; each returns should_continue."""
    calls = {"n": 0}

    async def fake(event_id, event, **kw):
        step = script[calls["n"]]
        calls["n"] += 1
        return await step(event_id)

    brain._process_with_llm = fake
    return calls


class TestSeededEventSingleCycle:
    @pytest.mark.asyncio
    async def test_seeded_event_is_evaluated_at_start_and_fully_processed(self, bb):
        """evt-996e33ec fixed path: T1 is in the snapshot, one response, everything PROCESSED."""
        eid = await _create(bb, [_user()])
        brain = _make_brain(bb)
        seen = {}

        async def iter0(e):
            ev = await bb.get_event(e)
            seen["conv_len_at_llm"] = len(ev.conversation)
            await bb.append_turn(e, _brain("thoughts"))
            await bb.append_turn(e, _brain("response"))
            return False

        _scripted_llm(brain, bb, [iter0])
        await brain._process_event_inner(eid)

        assert seen["conv_len_at_llm"] == 1  # never a 0-turn snapshot
        assert await _statuses(bb, eid) == {1: "processed", 2: "processed", 3: "processed"}
        # Nothing left for the scan safety net to re-run
        assert not any(
            t.status == MessageStatus.DELIVERED for t in (await bb.get_event(eid)).conversation
        )
        # No user "interrupt" was synthesised for the seeded turn
        brain._broadcast_status_update.assert_any_await(eid, "evaluated", turns=[1])


class TestInterruptWiring:
    @pytest.mark.asyncio
    async def test_answered_mid_loop_user_turn_becomes_processed(self, bb):
        """Legacy race (blank snapshot, user turn lands mid-cycle): once answered it must be PROCESSED."""
        eid = await _create(bb, None)  # blank: snapshot 0
        brain = _make_brain(bb)

        async def iter0(e):
            await bb.append_turn(e, _user())          # lands during iteration 0
            await bb.append_turn(e, _brain("tool_result"))
            return True                               # tool wants continuation

        async def iter1(e):
            await bb.append_turn(e, _brain("response"))  # answers the acknowledged interrupt
            return False

        _scripted_llm(brain, bb, [iter0, iter1])
        await _age_queue_stamp(bb, eid)
        await brain._process_event_inner(eid)

        st = await _statuses(bb, eid)
        assert st[1] == "processed", st   # the interrupt that was answered
        assert all(v == "processed" for v in st.values()), st

    @pytest.mark.asyncio
    async def test_ignored_mid_loop_user_turn_stays_unprocessed(self, bb):
        """Safety net (@ai-rules #43): an acknowledged-but-unanswered user turn must stay re-processable."""
        eid = await _create(bb, None)
        brain = _make_brain(bb)

        async def iter0(e):
            await bb.append_turn(e, _user())
            await bb.append_turn(e, _brain("tool_result"))
            return True

        async def iter1(e):
            await bb.append_turn(e, _brain("route"))   # acts, but never emits a response
            return False

        _scripted_llm(brain, bb, [iter0, iter1])
        await _age_queue_stamp(bb, eid)
        await brain._process_event_inner(eid)

        st = await _statuses(bb, eid)
        assert st[1] != "processed", st
