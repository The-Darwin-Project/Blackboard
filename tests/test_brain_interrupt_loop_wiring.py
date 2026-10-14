# tests/test_brain_interrupt_loop_wiring.py
# @ai-rules:
# 1. [Constraint]: Integration tests for the in-loop wiring of acknowledged_interrupts in
#    Brain._process_event_inner (evt-996e33ec Gap 5). The pure helper is covered by A-T1..A-T5.
# 2. [Pattern]: Real BlackboardState on fakeredis for turn storage/status (get_event, append_turn,
#    mark_turns_*); everything else on the Brain side is mocked. _process_with_llm is replaced with a
#    scripted per-iteration coroutine so the loop, snapshot, interrupt detection and PROCESSED scope
#    run for real.
# 3. [Gotcha]: Statuses are asserted from the stored Redis document, not from mock call args.
"""Brain loop wiring: acknowledged_interrupts population -> PROCESSED scope (evt-996e33ec)."""
from __future__ import annotations

import time
from unittest.mock import AsyncMock, MagicMock, patch

import fakeredis.aioredis
import pytest

from src.agents import brain as brain_mod
from src.agents.brain import Brain
from src.models import (
    ConversationTurn, EventDocument, EventEvidence, EventStatus, MessageStatus,
)
from src.state.blackboard import BlackboardState

EID = "evt-wiring-1"


@pytest.fixture
async def real_bb():
    state = BlackboardState(fakeredis.aioredis.FakeRedis())
    return state


async def _seed_chat_event(bb: BlackboardState) -> EventDocument:
    """Create a chat event the way WS/REST now do: first user turn seeded atomically."""
    evidence = EventEvidence(display_text="Hi Friday", source_type="chat", severity="info")
    event_id = await bb.create_event(
        source="chat", service="general", reason="Hi Friday", evidence=evidence,
        initial_turns=[ConversationTurn(turn=1, actor="user", action="message", thoughts="Hi Friday")],
    )
    doc = await bb.get_event(event_id)
    assert doc is not None
    return doc


def _make_brain(bb: BlackboardState) -> Brain:
    mocked = MagicMock()
    mocked.redis = bb.redis
    mocked.EVENT_ACTIVE = bb.EVENT_ACTIVE
    mocked.EVENT_QUEUE = bb.EVENT_QUEUE
    mocked.EVENT_PREFIX = bb.EVENT_PREFIX
    # Real turn storage + status machinery
    for name in ("get_event", "append_turn", "mark_turns_evaluated", "mark_turns_status",
                 "mark_turn_status", "mark_turns_delivered"):
        setattr(mocked, name, getattr(bb, name))
    for name in ("stamp_event", "record_event", "update_event_phase", "close_event", "persist_report",
                 "append_journal", "generate_mermaid", "get_recent_closed_for_service"):
        setattr(mocked, name, AsyncMock(return_value=[] if name == "get_recent_closed_for_service" else None))
    mocked.get_active_events = AsyncMock(return_value=[])
    brain = Brain(blackboard=mocked, agents={})
    brain._broadcast = AsyncMock()
    brain._broadcast_turn = AsyncMock()
    brain._broadcast_status_update = AsyncMock()
    brain._get_adapter = AsyncMock(return_value=MagicMock())  # non-None -> LLM path
    return brain


def _statuses(doc: EventDocument) -> dict[int, tuple[str, str, str]]:
    return {t.turn: (t.actor, t.action, t.status.value) for t in doc.conversation}


async def _append(bb: BlackboardState, actor: str, action: str) -> int:
    return await bb.append_turn(
        EID_HOLDER["id"], ConversationTurn(turn=0, actor=actor, action=action, thoughts="x"),
    )


EID_HOLDER: dict[str, str] = {}


async def _run(bb: BlackboardState, steps, *, prefetch_blank: bool):
    """Drive _process_event_inner with scripted _process_with_llm iterations.

    `steps[i]` is an async callable run on iteration i; it returns should_continue.
    Returns (stored doc after the cycle, captured acknowledged_interrupts dict).
    """
    doc = await _seed_chat_event(bb)
    EID_HOLDER["id"] = doc.id
    brain = _make_brain(bb)

    prefetched = doc
    if prefetch_blank:
        # evt-996e33ec: the queue pop beat the T1 append -> Run 1 saw 0 turns.
        prefetched = doc.model_copy(deep=True)
        prefetched.conversation = []
    # Past the blank-event grace window, already stamped: go straight into the loop.
    prefetched.queued_at = time.time() - 60
    prefetched.processing_started_at = time.time() - 60
    prefetched.status = EventStatus.ACTIVE
    prefetched.brain_phase = "triage"

    calls = {"i": 0}

    async def fake_llm(event_id, event, **kw):
        i = kw["iteration"]
        calls["i"] += 1
        return await steps[i](bb)

    captured: dict = {}
    real_helper = brain_mod._compute_processed_up_to

    def spy(conversation, turn_snapshot, acked):
        captured["acked"] = dict(acked)
        captured["snapshot"] = turn_snapshot
        return real_helper(conversation, turn_snapshot, acked)

    with patch.object(brain, "_process_with_llm", side_effect=fake_llm), \
         patch.object(brain_mod, "_compute_processed_up_to", side_effect=spy):
        await brain._process_event_inner(doc.id, prefetched)

    return await bb.get_event(doc.id), captured, calls["i"]


class TestAcknowledgedInterruptLoopWiring:
    @pytest.mark.asyncio
    async def test_evt_996e33ec_replay_answered_interrupt_all_processed(self, real_bb):
        """snapshot=0 (Run 1 fetched before T1), iteration 1 detects T1 as an interrupt,
        T2..T6 are brain turns ending in the response -> acked == {1: 1}, all 6 PROCESSED."""
        async def it0(bb):  # RECALL-blocked classify: nothing appended, continue
            return True

        async def it1(bb):
            for a in ("triage", "tool_result"):
                await _append(bb, "brain", a)
            return True

        async def it2(bb):
            await _append(bb, "brain", "phase")
            return True

        async def it3(bb):
            await _append(bb, "brain", "thoughts")
            await _append(bb, "brain", "response")
            return False

        doc, cap, n = await _run(real_bb, [it0, it1, it2, it3], prefetch_blank=True)

        assert n == 4
        assert cap["snapshot"] == 0
        assert cap["acked"] == {1: 1}, "T1 acknowledged with len(conversation)==1 at detection"
        assert len(doc.conversation) == 6
        assert all(t.status == MessageStatus.PROCESSED for t in doc.conversation), _statuses(doc)

    @pytest.mark.asyncio
    async def test_seeded_turn_normal_cycle_no_interrupt(self, real_bb):
        """Post-fix happy path (Batch B): snapshot=1, no interrupt, response -> all PROCESSED."""
        async def it0(bb):
            await _append(bb, "brain", "response")
            return False

        doc, cap, _ = await _run(real_bb, [it0], prefetch_blank=False)

        assert cap["snapshot"] == 1
        assert cap["acked"] == {}
        assert all(t.status == MessageStatus.PROCESSED for t in doc.conversation), _statuses(doc)

    @pytest.mark.asyncio
    async def test_mid_loop_interrupt_answered_is_processed(self, real_bb):
        """Real mid-loop user message: acked at iteration 1 with ack_len, answered by a later
        brain.response -> PROCESSED. ack_len must be len(conversation) at detection (3 here)."""
        async def it0(bb):
            await _append(bb, "brain", "triage")      # T2
            await _append(bb, "user", "message")      # T3 arrives mid-iteration
            return True

        async def it1(bb):
            await _append(bb, "brain", "response")    # T4 answers it
            return False

        doc, cap, _ = await _run(real_bb, [it0, it1], prefetch_blank=False)

        assert cap["snapshot"] == 1
        assert cap["acked"] == {3: 3}
        assert all(t.status == MessageStatus.PROCESSED for t in doc.conversation), _statuses(doc)

    @pytest.mark.asyncio
    async def test_ignored_interrupt_stays_unprocessed(self, real_bb):
        """Acked but never answered (no brain.response after ack) -> user turn is NOT PROCESSED,
        so the scan safety net (@ai-rules #43) still re-runs the event."""
        async def it0(bb):
            await _append(bb, "user", "message")      # T2
            return True

        async def it1(bb):
            await _append(bb, "brain", "route")       # T3, not a response
            return False

        doc, cap, _ = await _run(real_bb, [it0, it1], prefetch_blank=False)

        assert cap["acked"] == {2: 2}
        st = _statuses(doc)
        assert st[1][2] == "processed"
        assert st[2][2] in ("sent", "delivered", "evaluated") and st[2][2] != "processed", st
        assert st[3][2] != "processed", "brain turn after an unprocessed user turn stays unprocessed"

    @pytest.mark.asyncio
    async def test_response_flushed_before_ack_does_not_count(self, real_bb):
        """A response appended BEFORE the interrupt was acknowledged never saw it: the user turn
        must stay unprocessed even though a brain.response exists in the conversation."""
        async def it0(bb):
            await _append(bb, "brain", "response")    # T2 flushed first
            await _append(bb, "user", "message")      # T3 lands afterwards
            return True

        async def it1(bb):
            await _append(bb, "brain", "tool_result")  # T4, no new response
            return False

        doc, cap, _ = await _run(real_bb, [it0, it1], prefetch_blank=False)

        assert cap["acked"] == {3: 3}
        st = _statuses(doc)
        assert st[2][2] == "processed"
        assert st[3][2] != "processed", st

    @pytest.mark.asyncio
    async def test_user_turn_landing_in_final_call_is_never_acked(self, real_bb):
        """A user turn that lands during the FINAL iteration (no re-fetch afterwards) is never
        acked and must stay unprocessed, even though a brain.response follows it."""
        async def it0(bb):
            await _append(bb, "user", "message")      # T2 lands mid final call
            await _append(bb, "brain", "response")    # T3
            return False

        doc, cap, _ = await _run(real_bb, [it0], prefetch_blank=False)

        assert cap["acked"] == {}
        st = _statuses(doc)
        assert st[1][2] == "processed"
        assert st[2][2] != "processed", st
