# BlackBoard/tests/test_brain_jarvis_stabilization.py
# @ai-rules:
# 1. [Constraint]: The JARVIS peer is mocked with create_autospec(LiveAPIAdapter) so the REAL method signatures are enforced
#    (e.g. receive_brain_response(event_id, response)). Never replace it with a hand-written duck-typed stub.
# 2. [Pattern]: Every Brain built here goes through the `make_brain` factory; its finalizer cancels leftover timer tasks and
#    asserts none leaked. Loop timing is shrunk via monkeypatch on the module constants, not by sleeping for real intervals.
# 3. [Gotcha]: Stabilization state (_stabilization_waits) is SEPARATE from normal wait_for_jarvis state (_waiting_for_jarvis);
#    a stabilization wait is mirrored into _waiting_for_jarvis only so the scan treats the event as parked.
"""Brain-side FRIDAY->JARVIS stabilization handoff: scan trigger, timer loop, cleanup, round cap, isolation."""
from __future__ import annotations

import asyncio
import inspect
import time
from unittest.mock import AsyncMock, MagicMock, create_autospec

import pytest

import src.agents.brain as brain_module
from src.adapters.live_api_adapter import LiveAPIAdapter
from src.agents.brain import Brain
from src.models import ConversationTurn, EventDocument


def _adapter(*, ready: bool = True, watch_result: bool = True):
    adapter = create_autospec(LiveAPIAdapter, instance=True)
    adapter.is_operational_peer_ready.return_value = ready
    adapter.request_stabilization_watch = AsyncMock(return_value=watch_result)
    adapter.send_stability_telemetry = AsyncMock(return_value=True)
    return adapter


@pytest.fixture
async def make_brain():
    brains: list[Brain] = []

    def _make(adapter="default") -> Brain:
        bb = AsyncMock()
        bb.get_active_events_with_status = AsyncMock(return_value={})
        bb.mark_turns_delivered = AsyncMock()
        brain = Brain(blackboard=bb, agents={})
        brain._live_adapter = _adapter() if adapter == "default" else adapter
        brain._slack_notify = AsyncMock()
        brain.enqueue_for_processing = MagicMock()
        brain._append_and_broadcast = AsyncMock(return_value=7)
        brains.append(brain)
        return brain

    yield _make
    for brain in brains:
        for task in list(brain._jarvis_wait_tasks.values()):
            task.cancel()
        await asyncio.gather(*brain._jarvis_wait_tasks.values(), return_exceptions=True)
    await asyncio.sleep(0)
    leaked = [t for t in asyncio.all_tasks() if t is not asyncio.current_task() and not t.done()]
    assert leaked == [], f"leaked asyncio tasks: {leaked}"


def _err_turns(text: str = "429 RESOURCE_EXHAUSTED", n: int = 3) -> list[ConversationTurn]:
    return [ConversationTurn(turn=i + 1, actor="brain", action="error", thoughts=text) for i in range(n)]


def _event(eid: str = "evt-1", *, source: str = "headhunter", turns=None) -> EventDocument:
    return EventDocument(
        id=eid, source=source, conversation=turns if turns is not None else _err_turns(),
        status="active", service="test-svc", event={"reason": "", "evidence": "x"},
    )


def _serve_event(brain: Brain, ev: EventDocument) -> None:
    brain.blackboard.get_event = AsyncMock(return_value=ev)
    brain.blackboard.get_active_events_with_status = AsyncMock(return_value={ev.id: "active"})


def _register_wait(brain: Brain, eid: str = "evt-1") -> None:
    """Register a stabilization wait exactly as _handoff_transient_error_to_jarvis does."""
    token = time.time()
    brain._waiting_for_jarvis[eid] = token
    brain._stabilization_waits[eid] = token


def _start_loop(brain: Brain, eid: str, timeout_s: float) -> asyncio.Task:
    task = asyncio.create_task(brain._jarvis_stabilization_loop(eid, timeout_s=timeout_s))
    brain._jarvis_wait_tasks[eid] = task
    return task


# ---------------------------------------------------------------------------
# Scan trigger + handoff
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_scan_three_transient_errors_hands_off_to_jarvis(make_brain):
    brain = make_brain()
    brain._escalate_to_human = AsyncMock()
    _serve_event(brain, _event())

    await brain._scan_active_for_reconcile()

    brain._escalate_to_human.assert_not_called()
    assert brain.pending_stabilization_event_ids() == ["evt-1"]
    assert "evt-1" in brain._waiting_for_jarvis
    assert "evt-1" not in brain._waiting_for_user
    assert brain._jarvis_recovery_rounds["evt-1"] == 1
    brain._live_adapter.request_stabilization_watch.assert_awaited_once()
    wait_turn = brain._append_and_broadcast.call_args[0][1]
    assert (wait_turn.actor, wait_turn.action, wait_turn.waitingFor) == ("brain", "wait", "jarvis")
    assert "evt-1" in brain._jarvis_wait_tasks


@pytest.mark.asyncio
async def test_snapshot_exposes_stabilization_keys(make_brain):
    brain = make_brain()
    snap = brain.get_system_stability_snapshot()
    for key in ("tokens_used_60s", "tpm_limit", "tokens_remaining", "utilization_pct",
                "active_reservations", "high_priority_waiters", "pending_jarvis_events", "active_wip"):
        assert key in snap


@pytest.mark.asyncio
async def test_scan_without_live_adapter_uses_60s_fallback(make_brain):
    brain = make_brain(adapter=None)
    brain._escalate_to_human = AsyncMock()
    seen: dict = {}

    async def _stub_loop(eid, timeout_s=None):
        seen["timeout_s"] = timeout_s

    brain._jarvis_stabilization_loop = _stub_loop
    _serve_event(brain, _event())

    await brain._scan_active_for_reconcile()
    await asyncio.sleep(0)

    brain._escalate_to_human.assert_not_called()
    assert seen["timeout_s"] == brain_module._STABILIZATION_FALLBACK_TIMEOUT_S == 60.0


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "ready, watch_result, expected",
    [
        (True, True, 180.0),    # delivered -> full window
        (False, True, 60.0),    # peer not ready -> watch never requested
        (True, False, 60.0),    # watch returned False
    ],
)
async def test_handoff_timeout_window_depends_on_delivery(make_brain, ready, watch_result, expected):
    brain = make_brain(adapter=_adapter(ready=ready, watch_result=watch_result))
    seen: dict = {}

    async def _stub_loop(eid, timeout_s=None):
        seen["timeout_s"] = timeout_s

    brain._jarvis_stabilization_loop = _stub_loop

    assert await brain._handoff_transient_error_to_jarvis("evt-1", "sum", {}) is True
    await asyncio.sleep(0)

    assert seen["timeout_s"] == expected
    assert brain._live_adapter.request_stabilization_watch.await_count == (1 if ready else 0)


@pytest.mark.asyncio
async def test_handoff_watch_exception_falls_back_to_60s(make_brain):
    adapter = _adapter()
    adapter.request_stabilization_watch = AsyncMock(side_effect=RuntimeError("boom"))
    brain = make_brain(adapter=adapter)
    seen: dict = {}

    async def _stub_loop(eid, timeout_s=None):
        seen["timeout_s"] = timeout_s

    brain._jarvis_stabilization_loop = _stub_loop

    assert await brain._handoff_transient_error_to_jarvis("evt-1", "sum", {}) is True
    await asyncio.sleep(0)
    assert seen["timeout_s"] == 60.0


@pytest.mark.asyncio
async def test_round_cap_exhaustion_returns_false_and_escalates(make_brain):
    brain = make_brain()
    brain._escalate_to_human = AsyncMock()
    brain._jarvis_recovery_rounds["evt-1"] = brain_module._STABILIZATION_MAX_ROUNDS

    assert await brain._handoff_transient_error_to_jarvis("evt-1", "sum", {}) is False
    brain._append_and_broadcast.assert_not_called()
    assert brain.pending_stabilization_event_ids() == []

    _serve_event(brain, _event())
    await brain._scan_active_for_reconcile()
    brain._escalate_to_human.assert_awaited()


@pytest.mark.asyncio
async def test_permanent_burst_error_escalates_instead_of_handoff(make_brain):
    brain = make_brain()
    brain._escalate_to_human = AsyncMock()
    text = "Quota exhausted: request of 250000 tokens exceeds the burst limit of 200000 tokens"
    _serve_event(brain, _event(turns=_err_turns(text)))

    await brain._scan_active_for_reconcile()

    brain._escalate_to_human.assert_awaited()
    brain._live_adapter.request_stabilization_watch.assert_not_called()


@pytest.mark.asyncio
async def test_scan_skips_handoff_when_worker_active(make_brain):
    brain = make_brain()
    brain._escalate_to_human = AsyncMock()
    brain._active_tasks["evt-1"] = MagicMock(done=MagicMock(return_value=False))
    _serve_event(brain, _event())

    await brain._scan_active_for_reconcile()

    brain._escalate_to_human.assert_not_called()
    brain._live_adapter.request_stabilization_watch.assert_not_called()
    assert brain.pending_stabilization_event_ids() == []
    assert "evt-1" not in brain._jarvis_recovery_rounds


@pytest.mark.asyncio
async def test_chat_sourced_events_never_handoff(make_brain):
    brain = make_brain()
    brain._escalate_to_human = AsyncMock()
    _serve_event(brain, _event(source="slack"))

    await brain._scan_active_for_reconcile()

    brain._live_adapter.request_stabilization_watch.assert_not_called()
    assert brain.pending_stabilization_event_ids() == []


@pytest.mark.asyncio
async def test_handoff_event_missing_registers_nothing(make_brain):
    brain = make_brain()
    brain._append_and_broadcast = AsyncMock(return_value=0)  # event closed/deleted

    assert await brain._handoff_transient_error_to_jarvis("evt-1", "sum", {}) is True

    brain._live_adapter.request_stabilization_watch.assert_not_called()
    assert brain.pending_stabilization_event_ids() == []
    assert brain._waiting_for_jarvis == {}
    assert brain._jarvis_wait_tasks == {}
    assert "evt-1" not in brain._jarvis_recovery_rounds


@pytest.mark.asyncio
async def test_handoff_append_failure_returns_false_without_state(make_brain):
    brain = make_brain()
    brain._append_and_broadcast = AsyncMock(side_effect=RuntimeError("redis down"))

    assert await brain._handoff_transient_error_to_jarvis("evt-1", "sum", {}) is False
    assert brain.pending_stabilization_event_ids() == []
    assert brain._jarvis_wait_tasks == {}


@pytest.mark.asyncio
async def test_fast_jarvis_reply_during_watch_await_leaves_no_timer(make_brain):
    """JARVIS wakes FRIDAY while request_stabilization_watch is still awaiting -> no stray timer/wait."""
    brain = make_brain()

    async def _wake_during_await(event_id, summary, snapshot):
        brain.clear_jarvis_wait(event_id)  # what send_event_message does on the wake
        return True

    brain._live_adapter.request_stabilization_watch = AsyncMock(side_effect=_wake_during_await)

    assert await brain._handoff_transient_error_to_jarvis("evt-1", "sum", {}) is True

    assert brain._jarvis_wait_tasks == {}
    assert brain._stabilization_waits == {}
    assert brain._waiting_for_jarvis == {}


@pytest.mark.asyncio
async def test_close_during_watch_await_leaves_no_timer(make_brain):
    brain = make_brain()

    async def _close_during_await(event_id, summary, snapshot):
        brain._clear_jarvis_wait(event_id)
        brain._jarvis_recovery_rounds.pop(event_id, None)
        return True

    brain._live_adapter.request_stabilization_watch = AsyncMock(side_effect=_close_during_await)
    await brain._handoff_transient_error_to_jarvis("evt-1", "sum", {})
    assert brain._jarvis_wait_tasks == {} and brain._stabilization_waits == {}


@pytest.mark.asyncio
async def test_new_round_replaces_previous_timer(make_brain):
    brain = make_brain()
    await brain._handoff_transient_error_to_jarvis("evt-1", "first", {})
    first = brain._jarvis_wait_tasks["evt-1"]

    await brain._handoff_transient_error_to_jarvis("evt-1", "second", {})
    await asyncio.sleep(0)

    assert first.cancelled() or first.done()
    assert brain._jarvis_wait_tasks["evt-1"] is not first
    assert brain._jarvis_recovery_rounds["evt-1"] == 2


# ---------------------------------------------------------------------------
# Stabilization loop
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_loop_timeout_appends_defer_turn_and_enqueues(make_brain):
    brain = make_brain()
    _register_wait(brain)

    await _start_loop(brain, "evt-1", timeout_s=0.03)

    assert brain._waiting_for_jarvis == {} and brain._stabilization_waits == {}
    assert brain._jarvis_wait_tasks == {}
    turn = brain._append_and_broadcast.call_args[0][1]
    assert (turn.actor, turn.action) == ("dispatcher", "defer")
    assert "window elapsed" in turn.thoughts
    brain.enqueue_for_processing.assert_called_once_with("evt-1")


@pytest.mark.asyncio
async def test_loop_timeout_on_closed_event_skips_enqueue(make_brain):
    brain = make_brain()
    brain._append_and_broadcast = AsyncMock(return_value=0)
    _register_wait(brain)

    await _start_loop(brain, "evt-1", timeout_s=0.02)

    assert brain._stabilization_waits == {} and brain._jarvis_wait_tasks == {}
    brain.enqueue_for_processing.assert_not_called()


@pytest.mark.asyncio
async def test_loop_timeout_append_failure_still_reenqueues(make_brain):
    brain = make_brain()
    brain._append_and_broadcast = AsyncMock(side_effect=RuntimeError("redis down"))
    _register_wait(brain)

    await _start_loop(brain, "evt-1", timeout_s=0.02)

    brain.enqueue_for_processing.assert_called_once_with("evt-1")


@pytest.mark.asyncio
async def test_early_wake_appends_no_defer_turn_and_no_enqueue(make_brain, monkeypatch):
    monkeypatch.setattr(brain_module, "_STABILIZATION_TELEMETRY_INTERVAL_S", 0.01)
    brain = make_brain()
    _register_wait(brain)
    task = _start_loop(brain, "evt-1", timeout_s=30.0)
    await asyncio.sleep(0.03)

    brain._stabilization_waits.pop("evt-1")  # cleared by wake, task entry intentionally left in place
    brain._waiting_for_jarvis.pop("evt-1")
    await asyncio.wait_for(task, timeout=1.0)

    brain._append_and_broadcast.assert_not_called()
    brain.enqueue_for_processing.assert_not_called()
    assert brain._jarvis_wait_tasks == {}


@pytest.mark.asyncio
async def test_clear_jarvis_wait_cancels_loop_without_side_effects(make_brain, monkeypatch):
    monkeypatch.setattr(brain_module, "_STABILIZATION_TELEMETRY_INTERVAL_S", 0.01)
    brain = make_brain()
    _register_wait(brain)
    task = _start_loop(brain, "evt-1", timeout_s=30.0)
    await asyncio.sleep(0.02)

    brain.clear_jarvis_wait("evt-1")
    await asyncio.wait_for(asyncio.gather(task, return_exceptions=True), timeout=1.0)

    assert task.done()
    brain._append_and_broadcast.assert_not_called()
    brain.enqueue_for_processing.assert_not_called()
    assert brain._jarvis_wait_tasks == {} and brain._stabilization_waits == {}


@pytest.mark.asyncio
async def test_close_and_broadcast_cleans_stabilization_state(make_brain):
    brain = make_brain()
    brain._jarvis_recovery_rounds["evt-1"] = 2
    _register_wait(brain)
    _start_loop(brain, "evt-1", timeout_s=30.0)
    brain.agents["_archivist_memory"] = AsyncMock()

    await brain._close_and_broadcast("evt-1", "Closed", None)
    await asyncio.sleep(0)

    assert "evt-1" not in brain._jarvis_recovery_rounds
    assert brain._stabilization_waits == {} and brain._jarvis_wait_tasks == {}


@pytest.mark.asyncio
async def test_loop_delivers_telemetry_ticks_via_dedicated_port(make_brain, monkeypatch):
    monkeypatch.setattr(brain_module, "_STABILIZATION_TELEMETRY_INTERVAL_S", 0.01)
    brain = make_brain()
    _register_wait(brain)

    await _start_loop(brain, "evt-1", timeout_s=0.08)

    adapter = brain._live_adapter
    assert adapter.send_stability_telemetry.await_count >= 2
    event_id, snapshot = adapter.send_stability_telemetry.await_args.args
    assert event_id == "evt-1"
    assert "tokens_used_60s" in snapshot
    # The FRIDAY-DIRECT path (which arms the reply state) must never carry telemetry.
    adapter.receive_brain_response.assert_not_called()


@pytest.mark.asyncio
async def test_telemetry_not_sent_after_early_wake(make_brain, monkeypatch):
    monkeypatch.setattr(brain_module, "_STABILIZATION_TELEMETRY_INTERVAL_S", 0.05)
    brain = make_brain()
    _register_wait(brain)
    task = _start_loop(brain, "evt-1", timeout_s=30.0)
    brain._stabilization_waits.pop("evt-1")
    await asyncio.wait_for(task, timeout=1.0)
    brain._live_adapter.send_stability_telemetry.assert_not_called()


@pytest.mark.asyncio
async def test_telemetry_failure_is_logged_and_does_not_abort_loop(make_brain, monkeypatch, caplog):
    monkeypatch.setattr(brain_module, "_STABILIZATION_TELEMETRY_INTERVAL_S", 0.01)
    brain = make_brain()
    brain._live_adapter.send_stability_telemetry = AsyncMock(side_effect=RuntimeError("ws closed"))
    _register_wait(brain)

    with caplog.at_level("WARNING", logger=brain_module.logger.name):
        await _start_loop(brain, "evt-1", timeout_s=0.05)

    assert brain._live_adapter.send_stability_telemetry.await_count >= 2
    assert any("telemetry delivery failed" in r.getMessage() for r in caplog.records)
    # The loop still reached its normal timeout exit.
    assert "window elapsed" in brain._append_and_broadcast.call_args[0][1].thoughts
    brain.enqueue_for_processing.assert_called_once_with("evt-1")


@pytest.mark.asyncio
async def test_unexpected_loop_error_cleans_up_in_finally(make_brain, monkeypatch):
    monkeypatch.setattr(brain_module, "_STABILIZATION_TELEMETRY_INTERVAL_S", 0.01)
    brain = make_brain()
    brain._send_stability_telemetry = AsyncMock(side_effect=RuntimeError("unexpected"))
    _register_wait(brain)

    await _start_loop(brain, "evt-1", timeout_s=5.0)

    assert brain._waiting_for_jarvis == {} and brain._stabilization_waits == {}
    assert brain._jarvis_wait_tasks == {}
    turn = brain._append_and_broadcast.call_args[0][1]
    assert "aborted" in turn.thoughts
    brain.enqueue_for_processing.assert_called_once_with("evt-1")


@pytest.mark.asyncio
async def test_stale_loop_does_not_clobber_newer_round(make_brain):
    brain = make_brain()
    _register_wait(brain)
    stale = asyncio.create_task(brain._jarvis_stabilization_loop("evt-1", timeout_s=0.02))
    newer_marker = asyncio.create_task(asyncio.sleep(30))
    brain._jarvis_wait_tasks["evt-1"] = newer_marker  # a newer round owns the entry
    try:
        await stale
        assert brain._jarvis_wait_tasks["evt-1"] is newer_marker
        assert "evt-1" in brain._stabilization_waits
        brain._append_and_broadcast.assert_not_called()
    finally:
        newer_marker.cancel()
        await asyncio.gather(newer_marker, return_exceptions=True)
        brain._jarvis_wait_tasks.pop("evt-1", None)


# ---------------------------------------------------------------------------
# Isolation from normal wait_for_jarvis + port contract
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_normal_wait_for_jarvis_is_not_a_stabilization_wait(make_brain):
    brain = make_brain()
    brain._tool_ctx.mark_jarvis_wait("evt-1", time.time())  # what handle_wait_for_jarvis does

    assert brain.pending_jarvis_event_ids() == ["evt-1"]
    assert brain.pending_stabilization_event_ids() == []


@pytest.mark.asyncio
async def test_clear_jarvis_wait_preserves_recovery_round_budget(make_brain):
    brain = make_brain()
    _register_wait(brain)
    brain._jarvis_recovery_rounds["evt-1"] = 1

    brain.clear_jarvis_wait("evt-1")

    assert brain.pending_stabilization_event_ids() == []
    assert brain._jarvis_recovery_rounds["evt-1"] == 1


@pytest.mark.asyncio
async def test_waiting_for_jarvis_counts_as_wip(make_brain):
    brain = make_brain()
    brain.blackboard.get_active_events_with_status = AsyncMock(return_value={"evt-1": "active"})
    brain._waiting_for_jarvis = {"evt-1": time.time()}
    assert await brain._count_global_wip() >= 1


def test_real_adapter_signatures_match_brain_usage():
    params = list(inspect.signature(LiveAPIAdapter.receive_brain_response).parameters)
    assert params == ["self", "event_id", "response"]
    assert list(inspect.signature(LiveAPIAdapter.send_stability_telemetry).parameters) == ["self", "event_id", "snapshot"]
    assert list(inspect.signature(LiveAPIAdapter.request_stabilization_watch).parameters) == [
        "self", "event_id", "summary", "snapshot",
    ]


def test_autospec_adapter_rejects_one_arg_receive_brain_response():
    adapter = _adapter()
    with pytest.raises(TypeError):
        adapter.receive_brain_response("only-one-arg")


# ---------------------------------------------------------------------------
# has_jarvis_waiters excludes stabilization watches (create_system_review gate)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_stabilization_watch_alone_is_not_a_jarvis_waiter(make_brain):
    brain = make_brain()
    _register_wait(brain)
    assert brain.pending_stabilization_event_ids() == ["evt-1"]
    assert brain.has_jarvis_waiters() is False
    assert brain._tool_ctx.has_jarvis_waiters() is False


@pytest.mark.asyncio
async def test_ordinary_wait_for_jarvis_is_still_a_jarvis_waiter(make_brain):
    brain = make_brain()
    brain._tool_ctx.mark_jarvis_wait("evt-2", time.time())
    assert brain.has_jarvis_waiters() is True
    assert brain._tool_ctx.has_jarvis_waiters() is True
    brain.clear_jarvis_wait("evt-2")
    assert brain.has_jarvis_waiters() is False


@pytest.mark.asyncio
async def test_ordinary_waiter_counts_even_while_another_event_stabilizes(make_brain):
    brain = make_brain()
    _register_wait(brain, "evt-1")
    brain._tool_ctx.mark_jarvis_wait("evt-2", time.time())
    assert brain.has_jarvis_waiters() is True
    brain.clear_jarvis_wait("evt-2")
    assert brain.has_jarvis_waiters() is False  # stabilization on evt-1 still does not count
    assert brain.pending_stabilization_event_ids() == ["evt-1"]


@pytest.mark.asyncio
@pytest.mark.parametrize("stabilizing, expect_blocked", [(True, False), (False, True)])
async def test_create_system_review_gate_ignores_stabilization_only(make_brain, stabilizing, expect_blocked):
    brain = make_brain()
    if stabilizing:
        _register_wait(brain)
    else:
        brain._tool_ctx.mark_jarvis_wait("evt-1", time.time())
    bb = MagicMock()
    bb.get_active_events = AsyncMock(return_value=[])
    bb.find_active_event_by_source = AsyncMock(return_value=None)
    adapter = LiveAPIAdapter(bb, MagicMock(), MagicMock(), AsyncMock(), brain)
    adapter._shadow = False

    res = await adapter._tool_create_system_review("cross-event pattern worth a review")

    assert res.startswith("Cannot create review: FRIDAY is currently waiting") is expect_blocked


# ---------------------------------------------------------------------------
# Regression guards for mutants that previously survived
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_loop_exits_silently_when_stabilization_entry_removed_without_cancel(make_brain, monkeypatch):
    """The post-sleep ownership/entry check must stop the loop even though the task was never cancelled."""
    monkeypatch.setattr(brain_module, "_STABILIZATION_TELEMETRY_INTERVAL_S", 0.02)
    brain = make_brain()
    _register_wait(brain)
    task = _start_loop(brain, "evt-1", timeout_s=0.3)
    await asyncio.sleep(0.03)

    brain._stabilization_waits.pop("evt-1", None)  # state cleared, task deliberately NOT cancelled
    ticks = brain._live_adapter.send_stability_telemetry.await_count
    await asyncio.sleep(0.1)

    assert brain._live_adapter.send_stability_telemetry.await_count == ticks, "telemetry sent after the wait was gone"
    await asyncio.wait_for(task, timeout=1.0)
    brain.enqueue_for_processing.assert_not_called()
    brain._append_and_broadcast.assert_not_awaited()


@pytest.mark.asyncio
async def test_scan_held_event_lock_without_worker_blocks_handoff(make_brain):
    """_escalation_blocked must also honour a held per-event lock when no worker task exists."""
    brain = make_brain()
    brain._escalate_to_human = AsyncMock()
    lock = asyncio.Lock()
    await lock.acquire()
    brain._event_locks["evt-1"] = lock
    assert "evt-1" not in brain._active_tasks
    _serve_event(brain, _event())
    try:
        await brain._scan_active_for_reconcile()
    finally:
        lock.release()

    brain._live_adapter.request_stabilization_watch.assert_not_called()
    brain._escalate_to_human.assert_not_called()
    assert brain.pending_stabilization_event_ids() == []
    assert "evt-1" not in brain._jarvis_recovery_rounds


@pytest.mark.asyncio
async def test_jarvis_sourced_events_never_handoff(make_brain):
    brain = make_brain()
    brain._escalate_to_human = AsyncMock()
    _serve_event(brain, _event(source="jarvis"))

    await brain._scan_active_for_reconcile()

    brain._live_adapter.request_stabilization_watch.assert_not_called()
    assert brain.pending_stabilization_event_ids() == []
    assert "evt-1" not in brain._jarvis_recovery_rounds


@pytest.mark.parametrize(
    "text",
    [
        "400 INVALID_ARGUMENT: INTERNAL error in request",
        "403 PERMISSION_DENIED UNAVAILABLE project",
        "400 Bad Request 503 tokens-ish INTERNAL",
        "INVALID_ARGUMENT: payload too large, upstream said RESOURCE_EXHAUSTED",
    ],
)
def test_non_transient_client_error_takes_precedence_over_transient_tokens(text):
    assert Brain._is_transient_llm_error_turn(_turn(text)) is False


# ---------------------------------------------------------------------------
# _is_transient_llm_error_turn
# ---------------------------------------------------------------------------

def _turn(text, actor="brain", action="error"):
    return ConversationTurn(turn=1, actor=actor, action=action, thoughts=text)


@pytest.mark.parametrize(
    "text",
    [
        "429 RESOURCE_EXHAUSTED",
        "Server disconnected without sending a response",
        "LLM stream TTFB timed out after 90s (chunks_seen=0) for evt-1",
        "LLM stream inter-chunk timed out after 60s for evt-1",
        "503 UNAVAILABLE: model overloaded",
        "DEADLINE_EXCEEDED",
        "Quota exhausted: tpm window full",
        "upstream returned HTTP 503",
    ],
)
def test_transient_error_turns_match(make_brain, text):
    assert Brain._is_transient_llm_error_turn(_turn(text)) is True


@pytest.mark.parametrize(
    "text",
    [
        "Request of 250000 tokens exceeds the burst limit of 200000 tokens",
        "Quota exhausted: request exceeds the burst limit",
        "processed 42900 tokens then failed to parse tool args",
        "evt-5031 tool args malformed",
        "took 0.503s before parse error",
        "400 INVALID_ARGUMENT: bad schema",
        "403 PERMISSION_DENIED",
        "",
    ],
)
def test_non_transient_error_turns_do_not_match(text):
    assert Brain._is_transient_llm_error_turn(_turn(text)) is False


def test_transient_error_turn_requires_brain_error_actor_and_action():
    assert Brain._is_transient_llm_error_turn(_turn("429 RESOURCE_EXHAUSTED", actor="agent")) is False
    assert Brain._is_transient_llm_error_turn(_turn("429 RESOURCE_EXHAUSTED", action="think")) is False
    assert Brain._is_transient_llm_error_turn(None) is False


def test_transient_error_turn_accepts_dicts():
    assert Brain._is_transient_llm_error_turn(
        {"actor": "brain", "action": "error", "thoughts": "429 RESOURCE_EXHAUSTED"}
    ) is True
    assert Brain._is_transient_llm_error_turn({"actor": "brain", "action": "error", "thoughts": None}) is False
