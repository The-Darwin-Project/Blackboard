# BlackBoard/tests/test_vmer_2505_wip_tpm.py
# @ai-rules:
# 1. [Pattern]: 4-Layer Farley ATDD executable specification for VMER-2505 (T-2..T-4, T-6..T-13, T-20, T-22, T-24).
# 2. [Constraint]: Zero live Redis/GCP/Anthropic calls; uses FakeRedis, QuotaPoolRegistry, FastAPI TestClient, and mocks.
# 3. [Gotcha]: Deferred imports inside scenario methods ensure independent test discovery while proving RED per scenario.
"""4-Layer Farley ATDD executable specification for VMER-2505 WIP decoupling & Global TPM governance."""
from __future__ import annotations

import asyncio
import json
import re
import time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import fakeredis.aioredis
import pytest
from httpx import ASGITransport, AsyncClient

from src.models import (
    ConversationTurn,
    EventDocument,
    EventInput,
    EventStatus,
    FlowMetricsResponse,
    FlowSnapshot,
    MessageStatus,
)
from src.state.blackboard import BlackboardState


REPO_ROOT = Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------------------
# Layer 3: Protocol Drivers
# ---------------------------------------------------------------------------

def _make_fakeredis_bb() -> tuple[BlackboardState, fakeredis.aioredis.FakeRedis]:
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    return BlackboardState(redis), redis


def _make_brain_stub(bb: BlackboardState | MagicMock) -> "Brain":
    from src.agents.brain import Brain

    with patch.object(Brain, "__init__", lambda self, *a, **kw: None):
        brain = Brain.__new__(Brain)
        brain.blackboard = bb
        brain.agents = {}
        brain._broadcast_targets = []
        brain._active_tasks = {}
        brain._active_event_sources = {}
        brain._active_agent_for_event = {}
        brain._event_locks = {}
        brain._state_watcher = None
        brain._waiting_for_user = {}
        brain._waiting_for_agent = {}
        brain._waiting_for_jarvis = {}
        brain._stabilization_waits = {}
        brain._jarvis_wait_tasks = {}
        brain._jarvis_recovery_rounds = {}
        brain._jarvis_wait_count = {}
        brain._hold_watch_events = {}
        brain._hold_watch_park_time = {}
        brain._last_processed = {}
        brain._recall_lessons = {}
        brain._orphan_requeue_count = {}
        brain._orphan_last_attempt = {}
        brain._last_error_retry = {}
        brain._escalated_error_events = set()
        brain._thinking_bypass_time = {}
        brain._thinking_bypass_count = {}
        brain._escalated_thinking_events = set()
        brain._agent_error_streak = {}
        brain._empty_output_retries = {}
        brain._defer_wake_events = set()
        brain._memory_reflex_enabled = False
        brain._dispatch_semaphore = None
        brain._broadcast = AsyncMock()
        brain._idle_timeout = MagicMock()
        brain.cleanup_jarvis_event_state = MagicMock()
        brain._release_task_state = lambda eid: (
            brain._active_tasks.pop(eid, None),
            brain._active_event_sources.pop(eid, None),
        )
        return brain


# ---------------------------------------------------------------------------
# Layer 2: Domain DSL Helpers
# ---------------------------------------------------------------------------

async def admit_interactive_event(
    bb: BlackboardState,
    *,
    eid: str,
    source: str = "chat",
    service: str = "general",
    turns: list[ConversationTurn] | None = None,
) -> EventDocument:
    """Create & persist an active interactive event in FakeRedis."""
    doc = EventDocument(
        id=eid,
        source=source,  # type: ignore[arg-type]
        status=EventStatus.ACTIVE,
        service=service,
        event=EventInput(reason=f"interactive {eid}", evidence="test-evidence"),
        conversation=turns or [
            ConversationTurn(turn=1, actor="user", action="message", thoughts="help", status=MessageStatus.EVALUATED),
        ],
        queued_at=time.time(),
    )
    await bb.redis.set(f"{bb.EVENT_PREFIX}{eid}", json.dumps(doc.model_dump()))
    await bb.redis.sadd(bb.EVENT_ACTIVE, eid)
    return doc


async def park_event_for_user(
    bb: BlackboardState,
    *,
    eid: str,
    source: str = "chat",
    action: str = "wait",
    wait_ts: float | None = None,
) -> EventDocument:
    """Persist an active event whose last turn is parked waiting for user."""
    ts = wait_ts or (time.time() - 3600.0)
    turns = [
        ConversationTurn(turn=1, actor="user", action="message", thoughts="hi", status=MessageStatus.EVALUATED, timestamp=ts - 10),
        ConversationTurn(
            turn=2,
            actor="brain",
            action=action,
            thoughts="Waiting for user input",
            waitingFor="user",
            status=MessageStatus.EVALUATED,
            timestamp=ts,
        ),
    ]
    return await admit_interactive_event(bb, eid=eid, source=source, turns=turns)


def simulate_brain_restart(bb: BlackboardState):
    """Instantiate a fresh Brain against existing Redis state (empty in-memory dicts)."""
    return _make_brain_stub(bb)


async def saturate_pool_to_ratio(pool, ratio: float, *, priority: int | None = None):
    """Consume capacity on a QuotaTracker pool up to `ratio * tpm_limit`."""
    from src.agents.llm.types import PRIORITY_HIGH

    limit = pool.get_stats()["tpm_limit"]
    target = int(limit * ratio)
    if target <= 0:
        return None
    prio = PRIORITY_HIGH if priority is None else priority
    return await pool.acquire(target, max_wait_seconds=1.0, priority=prio)


# ---------------------------------------------------------------------------
# Layer 1: Domain Scenarios (T-2 .. T-24)
# ---------------------------------------------------------------------------

class TestInteractiveEventAndRestartDurability:
    """T-2, T-3, T-4: Chat source, team_id validator, restart _waiting_for_user recovery, and unread reply safety."""

    @pytest.mark.asyncio
    async def test_t2_chat_endpoint_creates_chat_source_and_event_team_id_validator(self):
        with patch("src.main.lifespan") as mock_lifespan:
            mock_lifespan.return_value.__aenter__ = AsyncMock()
            mock_lifespan.return_value.__aexit__ = AsyncMock()
            from src import dependencies
            from src.main import app

            bb, _ = _make_fakeredis_bb()
            orig_bb = dependencies._blackboard
            dependencies._blackboard = bb
            try:
                transport = ASGITransport(app=app)
                with (
                    patch("src.routes.chat.get_brain", AsyncMock(return_value=MagicMock())),
                    patch("src.routes.chat.spawn_event_namer_task"),
                ):
                    async with AsyncClient(transport=transport, base_url="http://test") as client:
                        resp = await client.post("/chat/", json={"message": "check pods", "service": "general"})
                assert resp.status_code == 200
                eid = resp.json()["event_id"]
                doc = await bb.get_event(eid)
                assert doc is not None
                assert doc.source == "chat"
            finally:
                dependencies._blackboard = orig_bb

        # EventDocument.team_id validator + backward compat
        doc_trimmed = EventDocument(
            id="evt-t1", source="chat", service="s", team_id="  team-alpha  ",
            event=EventInput(reason="r", evidence="e"),
        )
        assert doc_trimmed.team_id == "team-alpha"
        doc_blank = EventDocument(
            id="evt-t2", source="chat", service="s", team_id="   ",
            event=EventInput(reason="r", evidence="e"),
        )
        assert doc_blank.team_id is None
        doc_non_str = EventDocument(
            id="evt-t3", source="chat", service="s", team_id=123,  # type: ignore[arg-type]
            event=EventInput(reason="r", evidence="e"),
        )
        assert doc_non_str.team_id is None
        legacy = EventDocument.model_validate({
            "id": "evt-leg", "source": "aligner", "service": "s", "event": {"reason": "r", "evidence": "e"},
        })
        assert legacy.team_id is None

    @pytest.mark.asyncio
    async def test_t3_startup_cleanup_restores_waiting_for_user_and_skips_idle_rewake(self):
        bb, _ = _make_fakeredis_bb()
        old_ts = time.time() - 7200.0
        await park_event_for_user(bb, eid="evt-chat-wait", source="chat", action="wait", wait_ts=old_ts)
        await park_event_for_user(bb, eid="evt-chat-resp", source="chat", action="response", wait_ts=old_ts)
        await park_event_for_user(bb, eid="evt-auto-esc", source="aligner", action="wait", wait_ts=old_ts)

        brain = simulate_brain_restart(bb)
        assert brain._waiting_for_user == {}

        await brain._cleanup_stale_events()

        assert set(brain._waiting_for_user.keys()) == {"evt-chat-wait", "evt-chat-resp", "evt-auto-esc"}
        assert set(brain._last_processed.keys()) == {"evt-chat-wait", "evt-chat-resp", "evt-auto-esc"}
        assert await brain._count_global_wip(include_new=True) == 0

        # Idle safety-net (time_since > 60 on 5s scan) must NOT re-wake parked events
        to_enqueue = await brain._scan_active_for_reconcile()
        assert to_enqueue == []

    @pytest.mark.asyncio
    async def test_t4_startup_preserves_delivered_user_reply_exempts_chat_and_closes_non_parked_stale(self):
        bb, redis = _make_fakeredis_bb()
        old_ts = time.time() - 3600.0

        # 1. Chat event with parked turn + trailing DELIVERED user reply right before restart
        await admit_interactive_event(
            bb,
            eid="evt-chat-unread",
            source="chat",
            turns=[
                ConversationTurn(turn=1, actor="brain", action="wait", waitingFor="user", thoughts="ask?", status=MessageStatus.EVALUATED, timestamp=old_ts),
                ConversationTurn(turn=2, actor="user", action="message", thoughts="here is my reply", status=MessageStatus.DELIVERED, timestamp=old_ts + 5),
            ],
        )

        # 2. Non-parked active automated event with trailing_unread_count == 0 -> must still close as stale
        await admit_interactive_event(
            bb,
            eid="evt-auto-stale",
            source="headhunter",
            turns=[
                ConversationTurn(turn=1, actor="brain", action="thoughts", thoughts="working", status=MessageStatus.EVALUATED, timestamp=old_ts),
            ],
        )

        # 3. Untouched cutoff_idx == 0 event (only unread user turn) -> stays active and lpush once (llen == 1)
        await admit_interactive_event(
            bb,
            eid="evt-untouched",
            source="slack",
            turns=[
                ConversationTurn(turn=1, actor="user", action="message", thoughts="fresh", status=MessageStatus.SENT, timestamp=old_ts),
            ],
        )

        brain = simulate_brain_restart(bb)
        await brain._cleanup_stale_events()

        # Unread DELIVERED user turn preserved & exempted without entering _waiting_for_user
        unread_doc = await bb.get_event("evt-chat-unread")
        assert unread_doc is not None
        assert unread_doc.status == EventStatus.ACTIVE
        assert unread_doc.conversation[0].status == MessageStatus.EVALUATED
        assert unread_doc.conversation[1].status == MessageStatus.DELIVERED
        assert "evt-chat-unread" not in brain._waiting_for_user

        # Non-parked trailing_unread_count == 0 automated event closed as stale
        stale_doc = await bb.get_event("evt-auto-stale")
        assert stale_doc is not None
        assert stale_doc.status == EventStatus.CLOSED

        # Untouched + exempted_unread_eids queued once each (no duplicate lpush)
        queued = await redis.lrange(bb.EVENT_QUEUE, 0, -1)
        assert queued.count("evt-chat-unread") == 1
        assert queued.count("evt-untouched") == 1
        assert "evt-auto-stale" not in queued

    @pytest.mark.asyncio
    async def test_t4b_loop1_mark_turns_failure_exempts_and_prequeued_atomic_dedup(self):
        bb, redis = _make_fakeredis_bb()
        old_ts = time.time() - 3600.0

        await admit_interactive_event(
            bb,
            eid="evt-loop1-fail",
            source="chat",
            turns=[
                ConversationTurn(turn=1, actor="brain", action="wait", waitingFor="user", thoughts="q?", status=MessageStatus.EVALUATED, timestamp=old_ts),
                ConversationTurn(turn=2, actor="user", action="message", thoughts="reply", status=MessageStatus.DELIVERED, timestamp=old_ts + 5),
            ],
        )
        # Pre-populate EVENT_QUEUE with evt-loop1-fail so atomic lrem+lpush deduplicates to llen == 1
        await redis.lpush(bb.EVENT_QUEUE, "evt-loop1-fail")

        orig_mark = bb.mark_turns_evaluated
        calls = {"count": 0}

        async def _flaky_mark(eid: str, up_to_turn: int | None = None):
            calls["count"] += 1
            if calls["count"] == 1:
                raise RuntimeError("transient loop1 error")
            return await orig_mark(eid, up_to_turn=up_to_turn)

        bb.mark_turns_evaluated = _flaky_mark  # type: ignore[method-assign]
        brain = simulate_brain_restart(bb)
        await brain._cleanup_stale_events()

        doc = await bb.get_event("evt-loop1-fail")
        assert doc is not None
        assert doc.status == EventStatus.ACTIVE
        assert "evt-loop1-fail" not in brain._waiting_for_user
        assert await redis.llen(bb.EVENT_QUEUE) == 1
        assert await redis.lrange(bb.EVENT_QUEUE, 0, -1) == ["evt-loop1-fail"]


class TestDispatchSemaphoreBypassAndFix:
    """T-6 & T-7: handlers_dispatch.py:138 scalar log fix and pure interactive semaphore bypass."""

    @pytest.mark.asyncio
    async def test_t6_handle_select_agent_logs_scalar_active_events_and_defers_without_typeerror(self):
        from src.agents.handlers_dispatch import handle_select_agent

        ctx = MagicMock()
        ctx.is_task_running = MagicMock(return_value=False)
        ctx.is_dispatch_locked = MagicMock(return_value=True)
        ctx.dispatch_handler = AsyncMock(return_value=False)

        bb = AsyncMock()
        bb.get_event = AsyncMock(return_value=EventDocument(
            id="evt-auto-lock", source="aligner", service="svc", event=EventInput(reason="alert", evidence="e")
        ))
        bb.get_flow_metrics = AsyncMock(return_value={"queue_depth": 2, "active_events": 4})
        ctx.get_blackboard = MagicMock(return_value=bb)

        result = await handle_select_agent(ctx, "evt-auto-lock", {"agent_name": "developer", "task_instruction": "fix"}, None)
        assert result is False
        ctx.dispatch_handler.assert_awaited_once()
        assert ctx.dispatch_handler.call_args[0][0] == "defer_event"
        assert ctx.dispatch_handler.call_args[0][2]["delay_seconds"] == 30

    @pytest.mark.asyncio
    async def test_t7_interactive_sources_bypass_dispatch_semaphore_and_preserve_balance(self):
        from src.agents.handlers_dispatch import handle_select_agent
        from src.agents.tool_router import HANDLER_REGISTRY

        ask_agent_for_state = HANDLER_REGISTRY["ask_agent_for_state"]

        bb = AsyncMock()
        events_by_id = {
            "evt-auto": EventDocument(id="evt-auto", source="aligner", service="s", event=EventInput(reason="r", evidence="e")),
            "evt-chat": EventDocument(id="evt-chat", source="chat", service="s", event=EventInput(reason="r", evidence="e")),
            "evt-slack": EventDocument(id="evt-slack", source="slack", service="s", event=EventInput(reason="r", evidence="e")),
            "evt-jarvis": EventDocument(id="evt-jarvis", source="jarvis", service="s", event=EventInput(reason="r", evidence="e")),
        }
        bb.get_event = AsyncMock(side_effect=lambda eid: events_by_id.get(eid))
        bb.get_service = AsyncMock(return_value=None)
        bb.get_flow_metrics = AsyncMock(return_value={"queue_depth": 1, "active_events": 1})
        bb.mark_turn_status = AsyncMock()
        bb.append_turn = AsyncMock(return_value=1)

        brain = _make_brain_stub(bb)
        brain._dispatch_semaphore = asyncio.Semaphore(1)
        brain._ws_mode = "legacy"
        brain._ephemeral_provisioner = None
        brain._routing_depth = {}
        brain._active_agent_for_event = {}
        brain._routing_turn_for_event = {}
        brain._agent_sessions = {}
        brain._agent_session_modes = {}
        brain._agent_locks = {k: asyncio.Lock() for k in ("developer", "architect")}
        brain._scheduler = None
        brain._is_event_closed = AsyncMock(return_value=False)
        brain._append_and_broadcast = AsyncMock(return_value=2)
        brain._next_turn_number = AsyncMock(return_value=2)
        brain._emit_executive_pulse = AsyncMock()
        brain._record_event = AsyncMock()

        auto_started = asyncio.Event()
        auto_release = asyncio.Event()
        completion_order: list[str] = []

        class _AutoAgent:
            async def process(self, *args, **kwargs):
                auto_started.set()
                await auto_release.wait()
                completion_order.append("auto")
                return "auto-ok"

        class _InteractiveAgent:
            async def process(self, *args, **kwargs):
                completion_order.append("interactive")
                return "chat-ok"

        brain.agents = {"developer": _AutoAgent(), "architect": _InteractiveAgent()}

        from src.agents.brain import _BrainToolContext
        ctx = _BrainToolContext(brain)

        # 1. Start automated task holding the sole _dispatch_semaphore slot
        auto_task = asyncio.create_task(
            brain._run_agent_task("evt-auto", "developer", brain.agents["developer"], "work", "./m.md", 1)
        )
        await asyncio.wait_for(auto_started.wait(), timeout=2.0)
        assert brain._dispatch_semaphore.locked()

        brain._execute_function_call = AsyncMock(return_value=False)

        # 2. While automated holds semaphore, chat/slack/jarvis MUST NOT block or defer
        for eid, fn in (
            ("evt-chat", handle_select_agent),
            ("evt-slack", ask_agent_for_state),
            ("evt-jarvis", handle_select_agent),
        ):
            await fn(ctx, eid, {"agent_name": "architect", "task_instruction": "quick", "question": "q"}, None)
            brain._execute_function_call.assert_not_awaited()
            t = brain._active_tasks.pop(eid, None)
            if t is not None:
                await asyncio.wait_for(t, timeout=2.0)

        # Run interactive _run_agent_task directly while automated still holds semaphore
        await asyncio.wait_for(
            brain._run_agent_task("evt-chat", "architect", brain.agents["architect"], "fast", "./m.md", 2),
            timeout=2.0,
        )
        assert completion_order[0] == "interactive"

        auto_release.set()
        await asyncio.wait_for(auto_task, timeout=2.0)
        assert brain._dispatch_semaphore._value == 1

        # 3. Exception exit on automated task still releases _dispatch_semaphore cleanly
        class _FailingAgent:
            async def process(self, *args, **kwargs):
                raise RuntimeError("boom")

        await brain._run_agent_task("evt-auto", "developer", _FailingAgent(), "fail", "./m.md", 3)
        assert brain._dispatch_semaphore._value == 1


class TestQuotaPoolRegistryAndClaudeAdapter:
    """T-8, T-9, T-10, T-11, T-12, T-13, T-20: Multi-pool registry, 85%/15% reserve, ClaudeAdapter, 8 callers, team LRU."""

    @pytest.mark.asyncio
    async def test_t8_singleton_unification_and_85_15_priority_reserve(self, monkeypatch):
        import src.agents.llm as llm_pkg
        from src.agents.llm import (
            PRIORITY_HIGH,
            PRIORITY_NORMAL,
            PROVIDER_VERTEX_GEMINI,
            QuotaExhaustedError,
            create_adapter,
            get_quota_registry,
            get_quota_tracker,
            reset_quota_registry,
        )

        monkeypatch.setenv("LLM_TPM_LIMIT", "100000")
        monkeypatch.setenv("LLM_TPM_NORMAL_CEILING_RATIO", "0.85")
        reset_quota_registry()

        try:
            with patch("src.agents.llm.gemini_client.GeminiAdapter") as mock_gem:
                llm_pkg.create_adapter("gemini", "proj", "global", "gemini-4-neon")
                passed_tracker = mock_gem.call_args.kwargs["quota_tracker"]

            assert passed_tracker is get_quota_tracker() is get_quota_registry().get(PROVIDER_VERTEX_GEMINI)

            # Monkeypatch _quota_tracker = None -> resyncs cleanly
            monkeypatch.setattr(llm_pkg, "_quota_tracker", None)
            with patch("src.agents.llm.gemini_client.GeminiAdapter") as mock_gem2:
                create_adapter("gemini", "proj", "global", "gemini-4-neon")
                assert mock_gem2.call_args.kwargs["quota_tracker"] is get_quota_tracker()

            pool = get_quota_registry().get(PROVIDER_VERTEX_GEMINI)
            await saturate_pool_to_ratio(pool, 0.85, priority=PRIORITY_NORMAL)

            # PRIORITY_HIGH acquires immediately inside 15% reserve
            t0 = time.monotonic()
            res_high = await pool.acquire(10_000, max_wait_seconds=1.0, priority=PRIORITY_HIGH)
            assert (time.monotonic() - t0) < 0.05
            assert res_high.tokens == 10_000

            # PRIORITY_NORMAL (<= 85k) cannot cross 85% ceiling and raises QuotaExhaustedError on timeout
            with pytest.raises(QuotaExhaustedError):
                await pool.acquire(5_000, max_wait_seconds=0.05, priority=PRIORITY_NORMAL)
        finally:
            reset_quota_registry()

    def test_t8b_create_adapter_claude_then_gemini_preserves_singleton_identities(self, monkeypatch):
        import src.agents.llm as llm_pkg
        from src.agents.llm import (
            PROVIDER_VERTEX_CLAUDE,
            PROVIDER_VERTEX_GEMINI,
            create_adapter,
            get_quota_registry,
            get_quota_tracker,
            reset_quota_registry,
        )

        reset_quota_registry()
        monkeypatch.setattr(llm_pkg, "_quota_tracker", None)
        try:
            with (
                patch("anthropic.AsyncAnthropicVertex", return_value=MagicMock()),
                patch("google.genai.Client", return_value=MagicMock()),
            ):
                claude_adapter = create_adapter("claude", "proj", "global", "claude-sonnet-5")
                gemini_adapter = create_adapter("gemini", "proj", "global", "gemini-4-neon")

            reg = get_quota_registry()
            assert claude_adapter._tracker is reg.get(PROVIDER_VERTEX_CLAUDE)
            assert gemini_adapter._tracker is get_quota_tracker() is reg.get(PROVIDER_VERTEX_GEMINI)
            assert claude_adapter._tracker is not gemini_adapter._tracker
        finally:
            reset_quota_registry()

    @pytest.mark.asyncio
    async def test_t9_sustained_ceiling_error_vs_physical_burst_limit(self, monkeypatch):
        from src.agents.llm import (
            PRIORITY_HIGH,
            PRIORITY_NORMAL,
            PROVIDER_VERTEX_GEMINI,
            RequestExceedsBurstError,
            get_quota_registry,
            reset_quota_registry,
        )

        monkeypatch.setenv("LLM_TPM_LIMIT", "100000")
        monkeypatch.setenv("LLM_TPM_NORMAL_CEILING_RATIO", "0.85")
        reset_quota_registry()
        try:
            pool = get_quota_registry().get(PROVIDER_VERTEX_GEMINI)

            # 90k in (85%, 100%] -> normal raises RequestExceedsBurstError with sustained ceiling wording
            with pytest.raises(RequestExceedsBurstError, match="sustained ceiling"):
                await pool.acquire(90_000, max_wait_seconds=0.1, priority=PRIORITY_NORMAL)

            # 110k > 100% -> physical burst limit raise comes FIRST
            with pytest.raises(RequestExceedsBurstError, match="exceeds the burst limit"):
                await pool.acquire(110_000, max_wait_seconds=0.1, priority=PRIORITY_NORMAL)

            # Retrying 90k with PRIORITY_HIGH succeeds cleanly
            res = await pool.acquire(90_000, max_wait_seconds=0.1, priority=PRIORITY_HIGH)
            assert res.tokens == 90_000
        finally:
            reset_quota_registry()

    @pytest.mark.asyncio
    async def test_t10_standalone_quota_tracker_preserves_full_60k_normal_capacity(self):
        from src.agents.llm.quota_tracker import PRIORITY_NORMAL, QuotaTracker

        tracker = QuotaTracker(tpm_cap=60000)
        res = await tracker.acquire(60000, max_wait_seconds=0.5, priority=PRIORITY_NORMAL)
        assert res.tokens == 60000
        assert tracker.get_stats()["tokens_used_60s"] == 60000

    def test_t11_claude_adapter_extracts_thinking_tokens_without_double_counting(self):
        from src.agents.llm.claude_client import ClaudeAdapter

        adapter = ClaudeAdapter.__new__(ClaudeAdapter)
        adapter._model_name = "claude-sonnet-5"

        msg_with_thinking = SimpleNamespace(
            usage=SimpleNamespace(
                input_tokens=500,
                output_tokens=1000,
                cache_read_input_tokens=200,
                cache_creation_input_tokens=100,
                output_tokens_details=SimpleNamespace(thinking_tokens=400),
            )
        )
        u1 = adapter._extract_usage(msg_with_thinking)
        assert u1 is not None
        assert u1.thinking_tokens == 400
        assert u1.input_tokens == 800
        assert u1.output_tokens == 1000
        assert u1.total_tokens == 1800

        msg_without_details = SimpleNamespace(
            usage=SimpleNamespace(
                input_tokens=500,
                output_tokens=1000,
                cache_read_input_tokens=200,
                cache_creation_input_tokens=100,
                output_tokens_details=None,
            )
        )
        u2 = adapter._extract_usage(msg_without_details)
        assert u2 is not None
        assert u2.thinking_tokens == 0
        assert u2.total_tokens == 1800

    @pytest.mark.asyncio
    async def test_t12_claude_adapter_preacquired_abort_rollback_and_unary_generate(self):
        from src.agents.llm.claude_client import ClaudeAdapter
        from src.agents.llm.quota_tracker import QuotaTracker
        from src.agents.llm.types import PROVIDER_VERTEX_CLAUDE

        tracker = QuotaTracker(tpm_cap=100_000, burst_factor=0.85, enforce_sustained_for_normal=True)

        # __new__ stub safety (no _tracker / _provider_name attributes set)
        stub = ClaudeAdapter.__new__(ClaudeAdapter)
        stub._model_name = "claude-sonnet-5"
        stub._client = MagicMock()
        stub._client.messages.create = AsyncMock(return_value=SimpleNamespace(
            content=[SimpleNamespace(type="text", text="ok")],
            usage=SimpleNamespace(input_tokens=10, output_tokens=5),
        ))
        resp_stub = await stub.generate("sys", "hello")
        assert resp_stub.text == "ok"

        # Full ClaudeAdapter with QuotaTracker
        adapter = ClaudeAdapter.__new__(ClaudeAdapter)
        adapter._model_name = "claude-sonnet-5"
        adapter._tracker = tracker
        adapter._provider_name = PROVIDER_VERTEX_CLAUDE
        adapter._client = MagicMock()

        # 1. Preacquired mid-stream abort + aclose() -> eager _preacquired[2] = True, single rollback
        class _FakeStreamCtx:
            async def __aenter__(self):
                class _Raw:
                    def __aiter__(self):
                        return self

                    async def __anext__(self):
                        return SimpleNamespace(
                            type="content_block_delta",
                            delta=SimpleNamespace(type="text_delta", text="partial"),
                        )

                    async def get_final_message(self):
                        return SimpleNamespace(content=[], usage=None)

                return _Raw()

            async def __aexit__(self, exc_type, exc, tb):
                return False

        adapter._client.messages.stream = MagicMock(return_value=_FakeStreamCtx())
        pre = await adapter.acquire_stream_reservation("some prompt content")
        assert pre[2] is False
        stream = adapter.generate_stream("sys", "some prompt content", _preacquired=pre)
        first_chunk = await stream.__anext__()
        assert first_chunk.text == "partial"
        assert pre[2] is True  # Eagerly handed off at _stream_chunks entry
        await stream.aclose()
        assert tracker.get_stats()["tokens_used_60s"] == 0
        assert tracker.get_stats()["active_reservations"] == 0

        # 2. Unary generate() exception triggers single rollback
        adapter._client.messages.create = AsyncMock(side_effect=RuntimeError("anthropic 500"))
        with pytest.raises(RuntimeError, match="anthropic 500"):
            await adapter.generate("sys", "hello world")
        assert tracker.get_stats()["tokens_used_60s"] == 0

    @pytest.mark.asyncio
    async def test_t13_all_8_non_brain_callers_metered_and_archivist_embed_excluded(self, monkeypatch):
        from src.agents.llm import (
            PROVIDER_VERTEX_CLAUDE,
            PROVIDER_VERTEX_GEMINI,
            get_quota_registry,
            get_token_meter,
            reset_quota_registry,
        )
        from src.agents.llm.raw_genai_meter import acquire_raw_genai, finalize_raw_genai
        from src.agents.llm.types import LLMResponse, TokenUsage

        monkeypatch.setenv("ENMAAS_ENABLED", "false")
        reset_quota_registry()
        try:
            reg = get_quota_registry()
            meter = get_token_meter()

            # 1. observations_reporter: acquires & finalizes on event loop around asyncio.to_thread
            from src.reports.observations_reporter import _analyze_series

            sync_client = MagicMock()
            sync_client.models.generate_content = MagicMock(
                return_value=SimpleNamespace(
                    text="Analysis ok",
                    usage_metadata=SimpleNamespace(
                        prompt_token_count=120, candidates_token_count=30, total_token_count=150
                    ),
                )
            )
            before_gem = reg.get(PROVIDER_VERTEX_GEMINI).get_stats()["tokens_used_60s"]
            out = await _analyze_series(
                sync_client,
                "gemini-4-hydrogen",
                {"name": "s1", "trend": "stable", "min": 1, "max": 2, "count": 1, "span_minutes": 5, "points": []},
            )
            assert out == "Analysis ok"
            assert reg.get(PROVIDER_VERTEX_GEMINI).get_stats()["tokens_used_60s"] >= before_gem + 150
            assert meter.get_caller_totals().get("observations_reporter", {}).get("total_tokens", 0) >= 150

            # 2. entity_extractor
            from src.agents.entity_extractor import extract_entities

            aio_client = MagicMock()
            aio_client.aio.models.generate_content = AsyncMock(
                return_value=SimpleNamespace(
                    text='{"entities": [], "relationships": []}',
                    usage_metadata=SimpleNamespace(prompt_token_count=80, candidates_token_count=20, total_token_count=100),
                )
            )
            with patch("src.agents.entity_extractor._get_client", return_value=aio_client):
                await extract_entities({"event_id": "evt-ee", "service": "svc"})
            assert meter.get_caller_totals().get("entity_extractor", {}).get("total_tokens", 0) >= 100

            # 3. handlers_lookup.handle_google_web_search
            from src.agents.handlers_lookup import handle_google_web_search

            aio_lookup = MagicMock()
            aio_lookup.aio.models.generate_content = AsyncMock(
                return_value=SimpleNamespace(
                    text="web result",
                    candidates=[],
                    usage_metadata=SimpleNamespace(prompt_token_count=60, candidates_token_count=40, total_token_count=100),
                )
            )
            with patch("google.genai.Client", return_value=aio_lookup):
                ctx = MagicMock()
                ctx.next_turn_number = AsyncMock(return_value=1)
                ctx.append_and_broadcast = AsyncMock()
                await handle_google_web_search(ctx, "evt-ws", {"query": "darwin"}, None)
            assert meter.get_caller_totals().get("web_search", {}).get("total_tokens", 0) >= 100 or any(
                v.get("total_tokens", 0) >= 100 for k, v in meter.get_caller_totals().items() if "search" in k or "lookup" in k
            )

            # 4. LiveAPIAdapter (_tool_google_web_search + _process_message usage_metadata)
            from src.adapters.live_api_adapter import LiveAPIAdapter

            live = LiveAPIAdapter.__new__(LiveAPIAdapter)
            live._last_pulse_event_id = "evt-jarvis"
            live._active_meta_event_id = "evt-jarvis"
            live._broadcast = AsyncMock()
            live._handoff_enabled = False
            live._collecting_handoff = False
            live._text_buffer = []
            live._handoff_buffer = []
            before_jarvis = meter.get_caller_totals().get("jarvis", {}).get("total_tokens", 0)
            await live._process_message(SimpleNamespace(
                text=None, server_content=None, tool_call=None, tool_call_cancellation=None,
                go_away=None, session_resumption_update=None,
                usage_metadata=SimpleNamespace(prompt_token_count=90, candidates_token_count=10, total_token_count=100),
            ))
            after_jarvis = meter.get_caller_totals().get("jarvis", {}).get("total_tokens", 0)
            assert after_jarvis - before_jarvis == 100

            # 5. event_namer (PRIORITY_HIGH + record_token_usage + <=100L)
            from src.agents.event_namer import generate_event_title

            namer_adapter = MagicMock()
            namer_adapter.generate = AsyncMock(return_value=LLMResponse(
                text="Short Title",
                usage=TokenUsage(input_tokens=40, output_tokens=10, total_tokens=50, model_version="gemini-4-hydrogen"),
            ))
            bb_namer = AsyncMock()
            bb_namer.update_event_title_if_not_user = AsyncMock(return_value=True)
            brain_namer = AsyncMock()
            with patch("src.agents.event_namer.get_adapter", return_value=namer_adapter):
                await generate_event_title(bb_namer, brain_namer, "evt-nm", "fix pod", "chat")
            assert namer_adapter.generate.call_args.kwargs.get("priority") == 0
            assert meter.get_caller_totals().get("event_namer", {}).get("total_tokens", 0) >= 50

            # 6. archivist.extract_lessons -> records under archivist + vertex_claude; _embed excluded
            from src.agents.archivist import Archivist

            arch = Archivist()
            arch_adapter = MagicMock()
            arch_adapter.generate = AsyncMock(return_value=LLMResponse(
                text='{"lessons": [], "corrections": []}',
                usage=TokenUsage(input_tokens=300, output_tokens=100, total_tokens=400, model_version="claude-sonnet-5"),
            ))
            arch._claude_adapter = arch_adapter
            arch.search_lessons = AsyncMock(return_value=[])
            await arch.extract_lessons("Short review doc")
            assert meter.get_caller_totals().get("archivist", {}).get("total_tokens", 0) >= 400
            assert PROVIDER_VERTEX_CLAUDE in meter.get_provider_totals()

            # _embed excluded from generative pools
            arch._client = MagicMock()
            arch._client.aio.models.embed_content = AsyncMock(
                return_value=SimpleNamespace(embeddings=[SimpleNamespace(values=[0.1, 0.2])])
            )
            gem_before_embed = reg.get(PROVIDER_VERTEX_GEMINI).get_stats()["total_requests"]
            await arch._embed("hello")
            assert reg.get(PROVIDER_VERTEX_GEMINI).get_stats()["total_requests"] == gem_before_embed

            # 7. headhunter_jira & 8. timekeeper wiring presence + raw_genai_meter exports
            hhj_text = (REPO_ROOT / "src" / "agents" / "headhunter_jira.py").read_text()
            assert "PROVIDER_VERTEX_CLAUDE" in hhj_text
            tk_text = (REPO_ROOT / "src" / "routes" / "timekeeper.py").read_text()
            assert "PRIORITY_HIGH" in tk_text
            assert callable(acquire_raw_genai) and callable(finalize_raw_genai)
        finally:
            reset_quota_registry()

    @pytest.mark.asyncio
    async def test_t13b_execute_headhunter_jira_timekeeper_web_search_summarize_and_fallbacks(self, monkeypatch):
        from src.agents.archivist import Archivist
        from src.agents.headhunter_jira import HeadhunterJira
        from src.agents.llm import (
            PRIORITY_HIGH,
            PROVIDER_VERTEX_CLAUDE,
            PROVIDER_VERTEX_GEMINI,
            QuotaExhaustedError,
            get_quota_registry,
            get_token_meter,
            reset_quota_registry,
        )
        from src.agents.llm.types import FunctionCall, LLMChunk, LLMResponse, TokenUsage
        from src.adapters.live_api_adapter import LiveAPIAdapter
        from src.models import RefineRequest
        from src.reports.observations_reporter import _analyze_series, _summarize
        from src.routes import timekeeper as tk_route

        monkeypatch.setenv("ENMAAS_ENABLED", "false")
        reset_quota_registry()
        try:
            reg = get_quota_registry()
            meter = get_token_meter()

            # 1. HeadhunterJira._run_claude_analysis() + _run_brain_plan() -> PROVIDER_VERTEX_CLAUDE
            hhj = HeadhunterJira.__new__(HeadhunterJira)

            async def _fake_analysis_stream(*a, **kw):
                yield LLMChunk(
                    text="Analysis body",
                    usage=TokenUsage(input_tokens=100, output_tokens=40, total_tokens=140, model_version="claude-sonnet-5"),
                )

            async def _fake_plan_stream(*a, **kw):
                yield LLMChunk(
                    function_call=FunctionCall(
                        name="produce_execution_plan",
                        args={
                            "plan": "Verify pods",
                            "service": "darwin",
                            "repository": "https://github.com/org/repo",
                            "risk": "low",
                            "steps": [{"id": "s1", "agent": "qe", "mode": "test", "summary": "Run tests"}],
                        },
                    ),
                    usage=TokenUsage(input_tokens=160, output_tokens=50, total_tokens=210, model_version="claude-sonnet-5"),
                )

            fake_hhj_adapter = MagicMock()
            fake_hhj_adapter.generate_stream = MagicMock(side_effect=[_fake_analysis_stream(), _fake_plan_stream()])
            hhj._get_claude_adapter = MagicMock(return_value=fake_hhj_adapter)

            before_hhj = meter.get_caller_totals().get("headhunter_jira", {}).get("total_tokens", 0)
            before_claude_prov = meter.get_provider_totals().get(PROVIDER_VERTEX_CLAUDE, {}).get("total_tokens", 0)
            analysis_txt = await hhj._run_claude_analysis("Jira content")
            plan_yaml = await hhj._run_brain_plan("Jira content", analysis_txt)
            assert analysis_txt == "Analysis body"
            assert "Verify pods" in plan_yaml
            assert meter.get_caller_totals()["headhunter_jira"]["total_tokens"] - before_hhj == 350
            assert meter.get_provider_totals()[PROVIDER_VERTEX_CLAUDE]["total_tokens"] - before_claude_prov == 350

            # 2. timekeeper.refine_instructions (PRIORITY_HIGH, PROVIDER_VERTEX_GEMINI)
            tk_adapter = MagicMock()
            tk_adapter.generate = AsyncMock(
                return_value=LLMResponse(
                    text="Refined goal",
                    usage=TokenUsage(input_tokens=70, output_tokens=30, total_tokens=100, model_version="gemini-4-hydrogen"),
                )
            )
            before_tk = meter.get_caller_totals().get("timekeeper", {}).get("total_tokens", 0)
            before_gem_prov = meter.get_provider_totals().get(PROVIDER_VERTEX_GEMINI, {}).get("total_tokens", 0)
            with (
                patch("src.agents.llm.create_adapter", return_value=tk_adapter),
                patch("src.routes.timekeeper._load_brain_context", return_value="ctx"),
            ):
                resp = await tk_route.refine_instructions(
                    RefineRequest(raw_intent="check cluster health"),
                    user=SimpleNamespace(email="ops@redhat.com"),
                )
            assert resp.refined == "Refined goal"
            assert tk_adapter.generate.call_args.kwargs.get("priority") == PRIORITY_HIGH
            assert meter.get_caller_totals()["timekeeper"]["total_tokens"] - before_tk == 100
            assert meter.get_provider_totals()[PROVIDER_VERTEX_GEMINI]["total_tokens"] - before_gem_prov == 100

            # 3. LiveAPIAdapter._tool_google_web_search() (PRIORITY_HIGH)
            live = LiveAPIAdapter.__new__(LiveAPIAdapter)
            live._active_meta_event_id = "evt-live-ws"
            aio_search = MagicMock()
            aio_search.aio.models.generate_content = AsyncMock(
                return_value=SimpleNamespace(
                    text="grounded answer",
                    candidates=[],
                    usage_metadata=SimpleNamespace(prompt_token_count=75, candidates_token_count=25, total_token_count=100),
                )
            )
            before_jws = meter.get_caller_totals().get("jarvis_web_search", {}).get("total_tokens", 0)
            with (
                patch("google.genai.Client", return_value=aio_search),
                patch("src.agents.llm.raw_genai_meter.acquire_raw_genai", wraps=__import__("src.agents.llm.raw_genai_meter", fromlist=["acquire_raw_genai"]).acquire_raw_genai) as spy_acq,
            ):
                ws_out = await live._tool_google_web_search("openshift status")
            assert "grounded answer" in ws_out
            assert spy_acq.call_args.kwargs.get("priority") == PRIORITY_HIGH
            assert meter.get_caller_totals()["jarvis_web_search"]["total_tokens"] - before_jws == 100

            # 4. observations_reporter._summarize + asyncio.CancelledError reservation rollback
            sync_client = MagicMock()
            sync_client.models.generate_content = MagicMock(
                return_value=SimpleNamespace(
                    text="Summary ok",
                    usage_metadata=SimpleNamespace(prompt_token_count=110, candidates_token_count=40, total_token_count=150),
                )
            )
            before_obs = meter.get_caller_totals().get("observations_reporter", {}).get("total_tokens", 0)
            sum_out = await _summarize(sync_client, "gemini-4-hydrogen", ["series analysis"], "ctx")
            assert sum_out == "Summary ok"
            assert meter.get_caller_totals()["observations_reporter"]["total_tokens"] - before_obs == 150

            # CancelledError during _analyze_series rolls back active reservation cleanly
            with patch("src.reports.observations_reporter.asyncio.to_thread", AsyncMock(side_effect=asyncio.CancelledError())):
                with pytest.raises(asyncio.CancelledError):
                    await _analyze_series(
                        sync_client,
                        "gemini-4-hydrogen",
                        {"name": "s1", "trend": "stable", "min": 1, "max": 2, "count": 1, "span_minutes": 5, "points": []},
                    )
            assert reg.get(PROVIDER_VERTEX_GEMINI).get_stats()["active_reservations"] == 0

            # 5. Archivist QuotaExhaustedError -> _archive_event_fallback
            arch = Archivist()
            claude_arch = MagicMock()
            claude_arch.generate = AsyncMock(side_effect=QuotaExhaustedError("claude pool saturated"))
            gemini_arch = MagicMock()
            gemini_arch.generate = AsyncMock(
                return_value=LLMResponse(
                    text='{"symptom":"pod crash","root_cause":"oom","fix_action":"bump","keywords":["oom"],"outcome":"resolved"}',
                    usage=TokenUsage(input_tokens=180, output_tokens=70, total_tokens=250, model_version="gemini-4-neon"),
                )
            )
            arch._ensure_initialized = AsyncMock(return_value=True)
            arch._get_claude_adapter = AsyncMock(return_value=claude_arch)
            arch._get_adapter = AsyncMock(return_value=gemini_arch)
            arch._embed = AsyncMock(return_value=[0.1, 0.2])
            arch._vector_store = MagicMock()
            arch._vector_store.upsert = AsyncMock()
            arch._extract_and_store_graph = AsyncMock()

            evt_arch = EventDocument(
                id="evt-arch-fb",
                source="aligner",
                service="darwin",
                event=EventInput(reason="oom", evidence="ev"),
                conversation=[ConversationTurn(turn=1, actor="brain", action="thoughts", thoughts="done", timestamp=100.0)],
            )
            before_arch = meter.get_caller_totals().get("archivist", {}).get("total_tokens", 0)
            await arch.archive_event(evt_arch)
            gemini_arch.generate.assert_awaited_once()
            assert meter.get_caller_totals()["archivist"]["total_tokens"] - before_arch == 250

            # 6. LiveAPIAdapter._process_message monotonic cumulative usage_metadata (100 -> 250 -> 400 + turn_complete)
            live_cum = LiveAPIAdapter.__new__(LiveAPIAdapter)
            live_cum._last_pulse_event_id = "evt-live-cum"
            live_cum._active_meta_event_id = "evt-live-cum"
            live_cum._broadcast = AsyncMock()
            live_cum._handoff_enabled = False
            live_cum._collecting_handoff = False
            live_cum._text_buffer = []
            live_cum._handoff_buffer = []
            live_cum._last_was_watching = False
            live_cum._awaiting_jarvis_reply = False

            before_cum = meter.get_caller_totals().get("jarvis", {}).get("total_tokens", 0)
            for idx, (prompt_t, cand_t, total_t, done) in enumerate(
                [(90, 10, 100, False), (90, 160, 250, False), (90, 310, 400, True)]
            ):
                sc = SimpleNamespace(
                    turn_complete=done, model_turn=None, output_transcription=None, grounding_metadata=None
                )
                await live_cum._process_message(SimpleNamespace(
                    text=None, server_content=sc, tool_call=None, tool_call_cancellation=None,
                    go_away=None, session_resumption_update=None,
                    usage_metadata=SimpleNamespace(
                        prompt_token_count=prompt_t,
                        candidates_token_count=cand_t,
                        total_token_count=total_t,
                    ),
                ))
                if idx < 2:
                    assert live_cum._live_turn_usage_baseline is not None
            after_cum = meter.get_caller_totals().get("jarvis", {}).get("total_tokens", 0)
            assert after_cum - before_cum == 400
            assert live_cum._live_turn_usage_baseline is None
        finally:
            reset_quota_registry()

    def test_token_meter_negative_int_and_bool_safety(self):
        from src.agents.llm.token_meter import TokenMeter
        from src.agents.llm.types import TokenUsage

        meter = TokenMeter()
        meter.record("brain", "gemini-4-neon", TokenUsage(input_tokens=10, output_tokens=5, total_tokens=-1))
        meter.record("brain", "gemini-4-neon", TokenUsage(input_tokens=10, output_tokens=5, total_tokens=True))  # type: ignore[arg-type]
        assert meter.get_platform_totals()["calls"] == 0
        assert meter.get_platform_totals()["total_tokens"] == 0

        meter.record(
            "brain",
            "gemini-4-neon",
            TokenUsage(
                input_tokens=-5,
                output_tokens=10,
                thinking_tokens=-3,
                cached_tokens=True,  # type: ignore[arg-type]
                total_tokens=10,
            ),
        )
        totals = meter.get_platform_totals()
        assert totals["calls"] == 1
        assert totals["input_tokens"] == 0
        assert totals["thinking_tokens"] == 0
        assert totals["cached_tokens"] == 0
        assert totals["output_tokens"] == 10
        assert totals["total_tokens"] == 10

    @pytest.mark.asyncio
    async def test_quota_tracker_priority_aging_unblocks_normal_while_obeying_85_pct_ceiling(self, monkeypatch):
        from src.agents.llm.quota_tracker import (
            PRIORITY_HIGH,
            PRIORITY_NORMAL,
            QuotaExhaustedError,
            QuotaTracker,
        )

        monkeypatch.setenv("LLM_TPM_PRIORITY_AGING_SEC", "0.05")
        tracker = QuotaTracker(tpm_cap=100, burst_factor=0.85, enforce_sustained_for_normal=True)
        await tracker.acquire(80, max_wait_seconds=0.5, priority=PRIORITY_HIGH)

        # Hold a blocked PRIORITY_HIGH waiter in the queue (wants 30 > remaining 20)
        high_waiter = asyncio.create_task(tracker.acquire(30, max_wait_seconds=0.5, priority=PRIORITY_HIGH))
        await asyncio.sleep(0.01)
        assert tracker.get_stats()["high_priority_waiters"] == 1

        # PRIORITY_NORMAL (5 -> 85 <= 85 ceiling) is initially gated, then unblocks after 0.05s aging
        res_norm = await tracker.acquire(5, max_wait_seconds=0.5, priority=PRIORITY_NORMAL)
        assert res_norm.tokens == 5

        # PRIORITY_NORMAL (5 -> 90 > 85 ceiling) still obeys 85% ceiling even past aging deadline
        with pytest.raises(QuotaExhaustedError):
            await tracker.acquire(5, max_wait_seconds=0.1, priority=PRIORITY_NORMAL)

        with pytest.raises(QuotaExhaustedError):
            await high_waiter
        assert tracker.get_stats()["high_priority_waiters"] == 0

    def test_quota_pool_registry_unknown_provider_warns_and_falls_back(self, caplog):
        import logging
        from src.agents.llm.quota_registry import QuotaPoolRegistry
        from src.agents.llm.types import PROVIDER_VERTEX_GEMINI

        reg = QuotaPoolRegistry()
        with caplog.at_level(logging.WARNING):
            fallback = reg.get("bogus")
        assert fallback is reg.get(PROVIDER_VERTEX_GEMINI)
        assert any("Unknown quota provider" in rec.message for rec in caplog.records)

    def test_brain_system_stability_snapshot_includes_pools_dict(self, monkeypatch):
        from src.agents.llm import PROVIDER_ENMAAS, PROVIDER_VERTEX_CLAUDE, PROVIDER_VERTEX_GEMINI, reset_quota_registry

        monkeypatch.setenv("ENMAAS_ENABLED", "false")
        reset_quota_registry()
        try:
            bb, _ = _make_fakeredis_bb()
            brain = _make_brain_stub(bb)
            brain.pending_jarvis_event_ids = MagicMock(return_value=[])
            brain.pending_stabilization_event_ids = MagicMock(return_value=[])
            snap = brain.get_system_stability_snapshot()
            assert "pools" in snap
            assert set(snap["pools"].keys()) == {PROVIDER_VERTEX_GEMINI, PROVIDER_VERTEX_CLAUDE, PROVIDER_ENMAAS}
            for pool_stats in snap["pools"].values():
                assert {"tokens_used_60s", "tpm_limit", "utilization_pct"} <= set(pool_stats.keys())
            assert "peak_pool_utilization_pct" in snap
        finally:
            reset_quota_registry()

    def test_t20_token_attribution_normalize_and_bounded_lru_spray_eviction(self):
        from src.agents.llm.token_attribution import BoundedTeamCounter, normalize_team_id
        from src.agents.llm.token_meter import TokenMeter
        from src.agents.llm.types import TokenUsage

        assert normalize_team_id(None) == "global"
        assert normalize_team_id("   ") == "global"
        assert normalize_team_id("  Team Alpha/1!  ").startswith("team")
        assert len(normalize_team_id("a" * 100)) <= 64

        counter = BoundedTeamCounter(max_teams=256)
        # Seed active legitimate team
        counter.add("team-alpha", {"total_tokens": 500, "calls": 1})
        # Spray 300 distinct teams while touching team-alpha periodically
        for i in range(300):
            if i == 150:
                counter.add("team-alpha", {"total_tokens": 100, "calls": 1})
            counter.add(f"spray-{i}", {"total_tokens": 10, "calls": 1})

        totals = counter.totals()
        assert len(totals) <= 257  # 256 + "_other"
        assert "team-alpha" in totals
        assert totals["team-alpha"]["total_tokens"] == 600
        assert "_other" in totals
        assert totals["_other"]["total_tokens"] > 0

        # TokenMeter wires team_id cleanly
        meter = TokenMeter()
        meter.record("brain", "gemini-4-neon", TokenUsage(input_tokens=10, output_tokens=5, total_tokens=15), team_id="team-alpha")
        meter.record("brain", "gemini-4-neon", TokenUsage(input_tokens=20, output_tokens=5, total_tokens=25), team_id=None)
        t_totals = meter.get_team_totals()
        assert t_totals["team-alpha"]["total_tokens"] == 15
        assert t_totals["global"]["total_tokens"] == 25


class TestParityAndCacheStability:
    """T-22 & T-24: Per-interface TS/Python parity for +8/+10 fields & VMER-2450 prefix cache stability."""

    def test_t22_flow_snapshot_and_metrics_declare_all_new_fields_with_ts_optionality(self):
        ts_text = (REPO_ROOT / "ui" / "src" / "api" / "types.ts").read_text()

        def _parse_iface(name: str):
            m = re.search(rf"export\s+interface\s+{name}\s*\{{(.+?)^\}}", ts_text, re.DOTALL | re.MULTILINE)
            assert m, f"Missing interface {name}"
            all_fields = set(re.findall(r"^\s+(\w+)\s*\??:", m.group(1), re.MULTILINE))
            opt_fields = set(re.findall(r"^\s+(\w+)\s*\?:", m.group(1), re.MULTILINE))
            return all_fields, opt_fields

        gauge_8 = {
            "active_user_sessions",
            "peak_pool_utilization_pct",
            "gemini_tpm_used",
            "gemini_tpm_limit",
            "claude_tpm_used",
            "claude_tpm_limit",
            "enmaas_tpm_used",
            "enmaas_tpm_limit",
        }
        snap_10 = gauge_8 | {"claude_token_total_delta", "sidecar_token_total_delta"}

        py_metrics = set(FlowMetricsResponse.model_fields.keys())
        ts_metrics, ts_metrics_opt = _parse_iface("FlowMetrics")
        assert gauge_8 <= py_metrics
        assert py_metrics == ts_metrics
        assert gauge_8 <= ts_metrics_opt

        py_snap = set(FlowSnapshot.model_fields.keys())
        ts_snap, ts_snap_opt = _parse_iface("FlowSnapshot")
        assert snap_10 <= py_snap
        assert py_snap == ts_snap
        assert snap_10 <= ts_snap_opt

    def test_t24_prefix_builder_and_event_state_tail_remain_byte_stable(self):
        from src.agents.event_state_tail import format_event_state_tail
        from src.agents.prefix_builder import canonical_wire_tools, compute_prefix_hashes

        tools_a = canonical_wire_tools([{"name": "z_tool"}, {"name": "a_tool"}])
        tools_b = canonical_wire_tools([{"name": "a_tool"}, {"name": "z_tool"}])
        assert tools_a == tools_b
        h1 = compute_prefix_hashes(tools_a, "Global Core SI", "Turn 0 header")
        h2 = compute_prefix_hashes(tools_b, "Global Core SI", "Turn 0 header")
        assert h1 == h2
        assert len(h1["tools_sha8"]) == 8 and len(h1["si_sha8"]) == 8

        tail = format_event_state_tail(status="active", approved_by="alice@redhat.com")
        assert isinstance(tail, str) and "<event_state>" in tail
