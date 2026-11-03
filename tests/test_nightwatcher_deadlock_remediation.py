# tests/test_nightwatcher_deadlock_remediation.py
# @ai-rules:
# 1. [Pattern]: Redis-touching behaviour (lease/restage) runs against REAL fakeredis, not hand-built pipeline mocks.
# 2. [Pattern]: Production code paths are exercised (prompt builders, _sweep, _run_clustering_agent) -- never re-implement an f-string in a test.
# 3. [Constraint]: No real sleeps: asyncio.sleep is patched wherever a cooldown could run; quota tests assert fail-fast timing.
# 4. [Constraint]: Drain-script tests pass --backup-file under tmp_path; never write into the repo CWD.
"""
Acceptance & unit tests for the Nightwatcher deadlock remediation.
Jira: VMER-2236 (Plan: nightwatcher-backlog-and-quota-deadlock)

  T-1  Bounded lease (fakeredis): oldest-N, FIFO, before_ts, limit > pending
  T-2  Quota fail-fast: `>` vs `>=` burst boundary, non-transient error type, no reservation leak
  T-3  restage_orphans (fakeredis): inflight cleanup, score preservation, corrupt/missing staged_at edge cases
  T-4  Lean Phase 1 prompt built by PRODUCTION code (_run_analysis_loop, build_manifest_table)
  T-5  Auto-reconcile wiring in _run_clustering_agent (last attempt only)
  T-6  Drain script: arg validation, Redis target, critical guard, backup, batching
  S-*  _sweep: quota_exhausted report, partial-incident commit vs restage, batch loop, env validation
"""

import json
import re
import time
from unittest.mock import AsyncMock, MagicMock, patch

import fakeredis.aioredis
import pytest

from src.agents.llm.quota_tracker import (
    QuotaExhaustedError,
    QuotaTracker,
    RequestExceedsBurstError,
)
from src.models import ShiftIncident, ShiftReport, StagedEscalation
from src.observers import nightwatcher as nw
from src.observers.nightwatcher import (
    MAX_DECLARE_RETRIES,
    NightwatcherObserver,
    _env_float,
    _env_int,
)
from src.observers.nightwatcher_prompt import build_manifest_table
from src.observers.nightwatcher_tools import NightwatcherContext
from src.state.blackboard import BlackboardState


# ==============================================================================
# Helpers
# ==============================================================================

def make_escalation(event_id: str, staged_at: float = 1000.0, summary="CI test failure",
                    description="Traceback (most recent call last):\n ...", service="test-service",
                    platform="kargo", priority="Normal") -> StagedEscalation:
    return StagedEscalation(
        event_id=event_id, service=service, source="aligner", reason="ci_failure",
        summary=summary, platform=platform, description=description,
        staged_at=staged_at, priority=priority,
    )


@pytest.fixture
async def bb():
    redis = fakeredis.aioredis.FakeRedis()
    board = BlackboardState.__new__(BlackboardState)  # skip __init__ (Lua script registration)
    board.redis = redis
    yield board
    await redis.aclose()


async def stage_many(board: BlackboardState, count: int, base_ts: float = 1000.0):
    escs = [make_escalation(f"evt-{i:03d}", staged_at=base_ts + i) for i in range(count)]
    for e in escs:
        await board.stage_escalation(e)
    return escs


class MockFunctionCall:
    def __init__(self, name, args):
        self.name = name
        self.args = args


class MockResponse:
    def __init__(self, function_call=None, text=None):
        self.function_call = function_call
        self.text = text or ""
        self.raw_parts = None
        self.usage = None


def fc(name, args):
    return MockResponse(function_call=MockFunctionCall(name, args))


def make_observer(**overrides) -> NightwatcherObserver:
    defaults = dict(
        blackboard=AsyncMock(), registry=AsyncMock(), bridge=AsyncMock(),
        provisioner=AsyncMock(), incident_adapter=AsyncMock(), archivist=AsyncMock(),
        slack_notify=AsyncMock(),
    )
    defaults.update(overrides)
    return NightwatcherObserver(**defaults)


def make_ctx(escalations, created=None) -> NightwatcherContext:
    return NightwatcherContext(
        blackboard=AsyncMock(), archivist=AsyncMock(), provisioner=AsyncMock(),
        registry=AsyncMock(), bridge=AsyncMock(), incident_adapter=AsyncMock(),
        slack_notify=AsyncMock(),
        manifest_services={e.service for e in escalations},
        manifest_ids={e.event_id for e in escalations},
        escalations_by_id={e.event_id: e for e in escalations},
        created_incidents=list(created or []),
    )


def incident(*event_ids, key="VMER-1") -> ShiftIncident:
    return ShiftIncident(platform="kargo", summary="s", affected_events=list(event_ids), jira_issue_key=key)


# ==============================================================================
# T-1: Bounded lease (real Redis semantics via fakeredis)
# ==============================================================================

@pytest.mark.asyncio
async def test_t1_lease_takes_only_oldest_limit_in_fifo_order(bb):
    """Given 60 pending, lease(limit=25) leases exactly the 25 OLDEST, in order,
    and leaves 35 pending / 25 inflight."""
    await stage_many(bb, 60)

    leased, raw = await bb.lease_pending_escalations(before_ts=1e12, limit=25)

    assert [e.event_id for e in leased] == [f"evt-{i:03d}" for i in range(25)]
    assert len(raw) == 25
    assert await bb.redis.zcard(bb.NIGHTWATCHER_PENDING) == 35
    assert await bb.redis.scard(bb.NIGHTWATCHER_INFLIGHT) == 25
    inflight = {m.decode() for m in await bb.redis.smembers(bb.NIGHTWATCHER_INFLIGHT)}
    assert inflight == set(raw)
    assert await bb.redis.ttl(bb.NIGHTWATCHER_INFLIGHT) > 0


@pytest.mark.asyncio
async def test_t1_successive_leases_walk_the_queue_without_overlap(bb):
    await stage_many(bb, 60)
    seen: list[str] = []
    while True:
        leased, _ = await bb.lease_pending_escalations(before_ts=1e12, limit=25)
        if not leased:
            break
        seen.extend(e.event_id for e in leased)
    assert seen == [f"evt-{i:03d}" for i in range(60)]  # 25 + 25 + 10, no duplicates


@pytest.mark.asyncio
async def test_t1_lease_respects_before_ts_and_limit_larger_than_pending(bb):
    await stage_many(bb, 10)  # staged_at 1000..1009
    leased, _ = await bb.lease_pending_escalations(before_ts=1004.0, limit=25)
    assert [e.event_id for e in leased] == [f"evt-{i:03d}" for i in range(5)]  # inclusive upper bound
    assert await bb.redis.zcard(bb.NIGHTWATCHER_PENDING) == 5


@pytest.mark.asyncio
async def test_t1_lease_empty_queue(bb):
    assert await bb.lease_pending_escalations(before_ts=1e12, limit=25) == ([], [])


@pytest.mark.parametrize("raw,expected", [
    ("25", 25), ("1", 1), ("100", 100),
    ("0", 1), ("-1", 1), ("-50", 1),      # would otherwise be empty / LIMIT 0 -1 == unbounded
    ("abc", 25), ("2.5", 25), ("", 25),   # unparsable -> default
])
def test_t1_batch_size_env_validation(monkeypatch, raw, expected):
    monkeypatch.setenv("NIGHTWATCHER_BATCH_SIZE", raw)
    assert _env_int("NIGHTWATCHER_BATCH_SIZE", nw.DEFAULT_BATCH_SIZE) == expected


def test_t1_env_helpers_unset_and_float(monkeypatch):
    monkeypatch.delenv("NIGHTWATCHER_BATCH_SIZE", raising=False)
    assert _env_int("NIGHTWATCHER_BATCH_SIZE", 25) == 25
    monkeypatch.setenv("NIGHTWATCHER_BATCH_COOLDOWN_SECONDS", "-5")
    assert _env_float("NIGHTWATCHER_BATCH_COOLDOWN_SECONDS", 30.0) == 0.0
    monkeypatch.setenv("NIGHTWATCHER_BATCH_COOLDOWN_SECONDS", "x")
    assert _env_float("NIGHTWATCHER_BATCH_COOLDOWN_SECONDS", 30.0) == 30.0


@pytest.mark.parametrize("raw,expected_limit", [("0", 1), ("-1", 1), ("abc", 25), ("7", 7)])
@pytest.mark.asyncio
async def test_t1_sweep_passes_validated_limit_to_lease(monkeypatch, raw, expected_limit):
    """_sweep never forwards a raw/invalid NIGHTWATCHER_BATCH_SIZE to the lease."""
    monkeypatch.setenv("NIGHTWATCHER_BATCH_SIZE", raw)
    obs = make_observer()
    obs.blackboard.lease_pending_escalations = AsyncMock(return_value=([], []))
    obs.blackboard.persist_shift_report = AsyncMock()
    await obs._sweep()
    assert obs.blackboard.lease_pending_escalations.call_args.kwargs["limit"] == expected_limit


@pytest.mark.asyncio
async def test_t1_min_pending_is_clamped_to_batch_size(monkeypatch):
    """MIN_PENDING larger than the batch can never be met -> must be clamped, not report 'empty' forever."""
    monkeypatch.setenv("NIGHTWATCHER_BATCH_SIZE", "2")
    monkeypatch.setenv("NIGHTWATCHER_MIN_PENDING", "50")
    obs = make_observer()
    escs = [make_escalation("evt-1"), make_escalation("evt-2")]
    obs.blackboard.lease_pending_escalations = AsyncMock(
        return_value=(escs, [e.model_dump_json() for e in escs]))
    obs.blackboard.persist_shift_report = AsyncMock()
    obs._get_adapter = AsyncMock(return_value=None)  # stop right after the min_pending gate
    obs.blackboard.requeue_inflight = AsyncMock()

    await obs._sweep()

    # Reached the adapter check (i.e. did NOT take the 'below min_pending -> empty report' branch)
    obs._get_adapter.assert_awaited()
    obs.blackboard.persist_shift_report.assert_not_called()


# ==============================================================================
# T-2: Quota fail-fast
# ==============================================================================

@pytest.mark.asyncio
async def test_t2_oversize_request_fails_fast_with_nontransient_error():
    tracker = QuotaTracker(tpm_limit=500_000, burst_factor=0.8)
    with patch("src.agents.llm.quota_tracker.asyncio.sleep", side_effect=AssertionError("must not sleep")):
        t0 = time.monotonic()
        with pytest.raises(RequestExceedsBurstError) as exc_info:
            await tracker.acquire(500_001, max_wait_seconds=120.0)
        assert time.monotonic() - t0 < 0.2
    assert isinstance(exc_info.value, QuotaExhaustedError)  # still caught by Nightwatcher's handler
    msg = str(exc_info.value)
    assert "500001" in msg and "500000" in msg and "burst" in msg.lower()
    assert "batch" not in msg.lower()  # generic wording: shared by non-Nightwatcher callers
    assert tracker.get_stats()["active_reservations"] == 0  # no reservation leaked by the guard


@pytest.mark.asyncio
async def test_t2_exactly_burst_limit_is_admitted():
    """Boundary: estimated == burst_limit is `>` not `>=` -> admitted."""
    tracker = QuotaTracker(tpm_limit=500_000)
    res = await tracker.acquire(500_000, max_wait_seconds=0.01)
    assert res.tokens == 500_000
    assert tracker.get_stats()["active_reservations"] == 1


@pytest.mark.asyncio
async def test_t2_window_timeout_is_still_plain_quota_error():
    """A full bucket (not an oversize request) must NOT be the non-transient subclass."""
    tracker = QuotaTracker(tpm_limit=1000)
    await tracker.acquire(1000, max_wait_seconds=0.01)
    with pytest.raises(QuotaExhaustedError) as exc_info:
        await tracker.acquire(10, max_wait_seconds=0.01)
    assert not isinstance(exc_info.value, RequestExceedsBurstError)
    assert "Quota exhausted" in str(exc_info.value)


def test_t2_brain_is_transient_classification():
    """M4: oversize-request error must not be retried by Brain; real rate limits still are."""
    from src.agents.brain import Brain
    assert Brain._is_transient(RequestExceedsBurstError("Request of 9 tokens exceeds the burst limit (5)")) is False
    assert Brain._is_transient(QuotaExhaustedError("Quota exhausted: 10/10 tokens in window, waited 120s")) is True
    assert Brain._is_transient(Exception("429 RESOURCE_EXHAUSTED")) is True
    assert Brain._is_transient(Exception("400 INVALID_ARGUMENT")) is False


# ==============================================================================
# T-3: restage_orphans (fakeredis)
# ==============================================================================

@pytest.mark.asyncio
async def test_t3_restage_returns_members_with_original_scores_and_clears_inflight(bb):
    escs = await stage_many(bb, 5)
    leased, raw = await bb.lease_pending_escalations(before_ts=1e12, limit=5)
    assert await bb.redis.zcard(bb.NIGHTWATCHER_PENDING) == 0

    count = await bb.restage_orphans(raw[:3])

    assert count == 3
    pending = await bb.redis.zrange(bb.NIGHTWATCHER_PENDING, 0, -1, withscores=True)
    assert [(m.decode(), s) for m, s in pending] == [(raw[i], 1000.0 + i) for i in range(3)]
    assert {m.decode() for m in await bb.redis.smembers(bb.NIGHTWATCHER_INFLIGHT)} == set(raw[3:])


@pytest.mark.asyncio
async def test_t3_restage_all_corrupt_drops_them_and_clears_inflight(bb):
    await bb.redis.sadd(bb.NIGHTWATCHER_INFLIGHT, "not-json", "{broken")
    count = await bb.restage_orphans(["not-json", "{broken"])
    assert count == 0
    assert await bb.redis.zcard(bb.NIGHTWATCHER_PENDING) == 0
    assert await bb.redis.scard(bb.NIGHTWATCHER_INFLIGHT) == 0  # no zombie leak


@pytest.mark.asyncio
async def test_t3_restage_missing_null_and_zero_staged_at(bb):
    no_ts = json.dumps({"event_id": "a"})
    null_ts = json.dumps({"event_id": "b", "staged_at": None})
    zero_ts = json.dumps({"event_id": "c", "staged_at": 0.0})
    await bb.redis.sadd(bb.NIGHTWATCHER_INFLIGHT, no_ts, null_ts, zero_ts)
    with patch("src.state.blackboard.time.time", return_value=5000.0):
        assert await bb.restage_orphans([no_ts, null_ts, zero_ts]) == 3
    scores = {m.decode(): s for m, s in await bb.redis.zrange(bb.NIGHTWATCHER_PENDING, 0, -1, withscores=True)}
    assert scores[no_ts] == 5000.0
    assert scores[null_ts] == 5000.0
    assert scores[zero_ts] == 0.0  # explicit 0.0 is preserved, not replaced by "now"


@pytest.mark.asyncio
async def test_t3_restage_mixed_valid_and_corrupt(bb):
    good = make_escalation("evt-good", staged_at=42.5).model_dump_json()
    await bb.redis.sadd(bb.NIGHTWATCHER_INFLIGHT, good, "garbage")
    assert await bb.restage_orphans([good, "garbage"]) == 1
    assert await bb.redis.zscore(bb.NIGHTWATCHER_PENDING, good) == 42.5
    assert await bb.redis.scard(bb.NIGHTWATCHER_INFLIGHT) == 0


@pytest.mark.asyncio
async def test_t3_restage_empty_is_noop_and_roundtrips_through_lease(bb):
    assert await bb.restage_orphans([]) == 0
    await stage_many(bb, 3)
    _, raw = await bb.lease_pending_escalations(1e12, limit=3)
    await bb.restage_orphans(raw)
    again, _ = await bb.lease_pending_escalations(1e12, limit=3)
    assert [e.event_id for e in again] == ["evt-000", "evt-001", "evt-002"]  # FIFO preserved


# ==============================================================================
# T-4: Lean Phase 1 prompt via PRODUCTION code
# ==============================================================================

@pytest.mark.asyncio
async def test_t4_analysis_loop_user_prompt_is_lean_and_null_safe():
    big_trace = "Traceback (most recent call last):\n" + ("  File 'foo.py', line 1, in bar\n" * 500)
    escs = [
        make_escalation("evt-short", summary="Short summary", description=big_trace),
        make_escalation("evt-long", summary="A" * 200, description=big_trace),
        make_escalation("evt-null", summary=None, description=big_trace),
    ]
    obs = make_observer()
    adapter = AsyncMock()
    adapter.generate = AsyncMock(side_effect=[
        fc("set_phase", {"phase": "investigate"}), fc("set_phase", {"phase": "report"}),
    ])
    obs._get_adapter = AsyncMock(return_value=adapter)

    await obs._run_analysis_loop(escs, [e.model_dump_json() for e in escs], "SYSTEM",
                                 "ws", "we", "2026-01-01", "morning", time.time(), 3)

    user_text = adapter.generate.call_args_list[0].kwargs["contents"][0]["parts"][0]["text"]
    assert "Traceback" not in user_text and "foo.py" not in user_text  # description never sent
    lines = user_text.split("\n")
    assert len(lines) == 3
    assert lines[0].endswith("| Short summary")
    assert nw.SUMMARY_PROMPT_CHARS == 140                               # pinned: prompt-size budget (VMER-2236)
    assert lines[1].endswith("| " + "A" * 140)                          # capped at exactly 140
    assert "A" * 141 not in user_text
    assert lines[2].endswith("| ")                                      # None -> empty, not "None"
    assert "None" not in user_text
    assert len(user_text) < 1000


def test_t4_manifest_table_is_null_safe():
    """M12: nullable summary must not render the literal 'None' in the system-prompt manifest."""
    table = build_manifest_table([make_escalation("evt-null", summary=None), make_escalation("evt-ok", summary="ok")])
    assert "None" not in table
    assert "| ok |" in table


@pytest.mark.asyncio
async def test_t4_handle_report_incident_tolerates_explicit_null_summary():
    """ai-review MEDIUM: args.get('summary', '') is None when the LLM sends null -> TypeError."""
    from src.agents import handlers_dispatch
    from src.models import EventDocument, EventEvidence, EventInput

    bb = AsyncMock(spec=BlackboardState)
    bb.get_active_events.return_value = []
    bb.get_event.return_value = EventDocument(
        id="evt-null-sum", source="aligner", service="svc-a", subject_type="service",
        event=EventInput(reason="cpu", evidence=EventEvidence(
            display_text="cpu", source_type="aligner")),
    )
    ctx = MagicMock()
    ctx.get_blackboard.return_value = bb
    ctx.has_incident_been_created.return_value = False
    ctx.next_turn_number = AsyncMock(return_value=1)
    ctx.append_and_broadcast = AsyncMock()
    ctx.emit_pulse = AsyncMock()

    with patch.dict("os.environ", {"NIGHTWATCHER_ENABLED": "true"}):
        res = await handlers_dispatch.handle_report_incident(
            ctx, "evt-null-sum",
            {"summary": None, "description": "d", "priority": "Normal"}, None,
        )

    assert res is True
    bb.stage_escalation.assert_awaited_once()
    assert bb.stage_escalation.call_args[0][0].summary == ""


# ==============================================================================
# T-5: Auto-reconcile wiring (_run_clustering_agent) + validator behaviour
# ==============================================================================

@pytest.mark.asyncio
async def test_t5_auto_reconcile_enabled_only_on_final_attempt():
    ctx = make_ctx([make_escalation("evt-1")])
    adapter = AsyncMock()
    adapter.generate = AsyncMock(side_effect=[fc("declare_clusters", {"clusters": []})] * (MAX_DECLARE_RETRIES + 1))
    obs = make_observer()

    with patch("src.observers.nightwatcher_tools._handle_declare_clusters",
               new=AsyncMock(return_value="Cluster plan validation failed: x")) as handler:
        with pytest.raises(RuntimeError, match="cluster declaration failed"):
            await obs._run_clustering_agent(adapter, ctx, "SYS", [], 0.3, 8192, "high")

    flags = [c.kwargs["auto_reconcile"] for c in handler.call_args_list]
    assert flags == [False] * MAX_DECLARE_RETRIES + [True]
    assert adapter.generate.await_count == MAX_DECLARE_RETRIES + 1


@pytest.mark.asyncio
async def test_t5_accepted_on_first_attempt_never_reconciles():
    escs = [make_escalation("evt-1"), make_escalation("evt-2")]
    ctx = make_ctx(escs)
    plan = {"clusters": [{"events": ["evt-1", "evt-2"], "root_cause": "r", "platform": "kargo", "services": []}]}
    adapter = AsyncMock()
    adapter.generate = AsyncMock(return_value=fc("declare_clusters", plan))
    await make_observer()._run_clustering_agent(adapter, ctx, "SYS", [], 0.3, 8192, "high")
    assert adapter.generate.await_count == 1
    assert len(ctx.declared_clusters) == 1
    assert not ctx.declared_clusters[0].get("auto_reconciled")


@pytest.mark.asyncio
async def test_t5_incomplete_plan_rejected_with_feedback_until_final_attempt_then_reconciled():
    """End-to-end with the real validator: attempts 1..N reject (feedback appended), last accepts a fallback."""
    escs = [make_escalation("evt-1"), make_escalation("evt-2"), make_escalation("evt-3")]
    ctx = make_ctx(escs)
    incomplete = {"clusters": [{"events": ["evt-1"], "root_cause": "r", "platform": "kargo", "services": []}]}
    adapter = AsyncMock()
    seen_declared: list[int] = []

    async def generate(**kwargs):
        seen_declared.append(len(ctx.declared_clusters))  # empty until accepted
        return fc("declare_clusters", incomplete)
    adapter.generate = AsyncMock(side_effect=generate)
    contents: list = []

    await make_observer()._run_clustering_agent(adapter, ctx, "SYS", contents, 0.3, 8192, "high")

    assert seen_declared == [0] * (MAX_DECLARE_RETRIES + 1)
    assert adapter.generate.await_count == MAX_DECLARE_RETRIES + 1
    feedback = [c["parts"][0]["text"] for c in contents if c["role"] == "user"]
    assert all("Events not assigned" in f for f in feedback[:MAX_DECLARE_RETRIES])  # model told what it missed
    assert "accepted" in feedback[-1]
    assert len(ctx.declared_clusters) == 2
    fallback = ctx.declared_clusters[1]
    assert fallback["auto_reconciled"] is True and fallback["events"] == ["evt-2", "evt-3"]


@pytest.mark.asyncio
async def test_t5_no_tool_call_consumes_an_attempt_and_nudges():
    ctx = make_ctx([make_escalation("evt-1")])
    adapter = AsyncMock()
    adapter.generate = AsyncMock(return_value=MockResponse(text="thinking..."))
    contents: list = []
    with pytest.raises(RuntimeError):
        await make_observer()._run_clustering_agent(adapter, ctx, "SYS", contents, 0.3, 8192, "high")
    assert adapter.generate.await_count == MAX_DECLARE_RETRIES + 1
    assert any("must call declare_clusters" in c["parts"][0]["text"] for c in contents if c["role"] == "user")


# ==============================================================================
# T-6: Drain script
# ==============================================================================

def test_t6_parser_defaults_and_validation(capsys):
    from scripts.drain_nightwatcher_backlog import build_parser
    parser = build_parser()
    args = parser.parse_args(["--dry-run", "--age-off-days", "7", "--batch-size", "25", "--delay-seconds", "45"])
    assert (args.dry_run, args.age_off_days, args.batch_size, args.delay_seconds) == (True, 7, 25, 45)
    for bad in (["--age-off-days", "0"], ["--age-off-days", "-3"], ["--batch-size", "0"],
                ["--batch-size", "-1"], ["--delay-seconds", "-1"], ["--age-off-days", "x"]):
        with pytest.raises(SystemExit) as exc:
            parser.parse_args(bad)
        assert exc.value.code == 2, bad


def test_t6_get_redis_client_target_resolution(monkeypatch):
    import scripts.drain_nightwatcher_backlog as drain
    fake_cls = MagicMock()
    monkeypatch.setattr(drain, "Redis", fake_cls)
    for var in ("REDIS_URL", "REDIS_HOST", "REDIS_PORT", "REDIS_PASSWORD"):
        monkeypatch.delenv(var, raising=False)

    monkeypatch.setenv("REDIS_HOST", "redis.darwin.svc")
    monkeypatch.setenv("REDIS_PORT", "6380")
    monkeypatch.setenv("REDIS_PASSWORD", "pw")
    drain.get_redis_client()
    fake_cls.assert_called_once_with(host="redis.darwin.svc", port=6380, password="pw", socket_timeout=30)
    assert drain._redis_target().startswith("redis.darwin.svc:6380")

    fake_cls.reset_mock()
    monkeypatch.setenv("REDIS_URL", "redis://user:secret@url-host:6390/2")
    drain.get_redis_client()
    fake_cls.from_url.assert_called_once()
    target = drain._redis_target()
    assert target.startswith("url-host:6390") and "secret" not in target  # credentials never logged

    monkeypatch.delenv("REDIS_URL")
    monkeypatch.setenv("REDIS_PORT", "notaport")
    with pytest.raises(RuntimeError, match="REDIS_PORT"):
        drain.get_redis_client()


def _drain_redis(items):
    """Real (sync) fakeredis seeded with (member, score) pairs on the pending ZSET."""
    import fakeredis
    r = fakeredis.FakeRedis()
    if items:
        r.zadd("darwin:nightwatcher:pending", {m: sc for m, sc in items})
    return r


def _pending_members(r):
    return {m.decode() for m in r.zrange("darwin:nightwatcher:pending", 0, -1)}


def test_t6_prune_is_bounded_windowed_and_protects_critical(tmp_path):
    """MEDIUM: never loads the whole ZSET -- every ZRANGEBYSCORE has a LIMIT of batch_size -- and
    Critical members sitting at the head of the range do not stall or get removed."""
    from scripts import drain_nightwatcher_backlog as drain
    now = 1_000_000.0
    crit = [json.dumps({"event_id": f"c{i}", "priority": "Critical"}) for i in range(3)]
    stale = [json.dumps({"event_id": f"s{i}", "priority": "Normal"}) for i in range(7)]
    fresh = [json.dumps({"event_id": "fresh", "priority": "Normal"})]
    items = ([(m, now - 40 * 86400 + i) for i, m in enumerate(crit)]       # oldest -> head of window
             + [(m, now - 30 * 86400 + i) for i, m in enumerate(stale)]
             + [(m, now - 86400) for m in fresh])
    r = _drain_redis(items)
    calls = []
    real = r.zrangebyscore

    def spy(*a, **kw):
        calls.append(kw)
        return real(*a, **kw)
    r.zrangebyscore = spy
    backup = tmp_path / "b.jsonl"

    with patch("time.time", return_value=now):
        removable, protected = drain.prune_stale(r, 7, 2, protect_critical=True, execute=True,
                                                 backup_path=str(backup))

    assert (removable, protected) == (7, 3)
    assert _pending_members(r) == set(crit) | set(fresh)
    assert calls and all(c.get("num") == 2 and "start" in c for c in calls)   # bounded windows only
    assert {json.loads(l)["member"] for l in backup.read_text().splitlines()} == set(stale)
    assert (backup.stat().st_mode & 0o777) == 0o600                            # LOW: owner-only


def test_t6_backup_permissions_are_enforced_on_preexisting_file(tmp_path):
    from scripts import drain_nightwatcher_backlog as drain
    path = tmp_path / "pre.jsonl"
    path.write_text("")
    path.chmod(0o644)
    drain._open_backup(str(path)).close()
    assert (path.stat().st_mode & 0o777) == 0o600


def test_t6_include_critical_removes_everything_stale(tmp_path):
    from scripts import drain_nightwatcher_backlog as drain
    now = 1_000_000.0
    crit = json.dumps({"event_id": "c", "priority": "Critical"})
    r = _drain_redis([(crit, now - 30 * 86400), ("junk-not-json", now - 30 * 86400), ("fresh", now - 86400)])
    with patch("time.time", return_value=now):
        removable, protected = drain.prune_stale(r, 7, 10, protect_critical=False, execute=True,
                                                 backup_path=str(tmp_path / "b.jsonl"))
    assert (removable, protected) == (2, 0)
    assert _pending_members(r) == {"fresh"}


def test_t6_age_boundary_is_exclusive():
    """score == cutoff is NOT stale (matches `score < cutoff`)."""
    from scripts import drain_nightwatcher_backlog as drain
    now = 1_000_000.0
    r = _drain_redis([("edge", now - 7 * 86400), ("just-older", now - 7 * 86400 - 1)])
    with patch("time.time", return_value=now):
        removable, _ = drain.prune_stale(r, 7, 10, execute=False)
    assert removable == 1


def test_t6_dry_run_and_default_do_not_mutate_or_create_backup(tmp_path, monkeypatch):
    from scripts import drain_nightwatcher_backlog as drain
    monkeypatch.chdir(tmp_path)
    now = 1_000_000.0
    items = [(f"stale-{i}", now - (10 + i) * 86400) for i in range(5)] + [("active", now - 86400)]
    r = _drain_redis(items)
    with patch("time.time", return_value=now), patch.object(drain, "get_redis_client", return_value=r):
        assert drain.main(["--dry-run", "--age-off-days", "7"]) == 0
        assert drain.main(["--age-off-days", "7", "--execute", "--dry-run"]) == 0   # dry-run wins
        assert drain.main(["--age-off-days", "7"]) == 0                             # no --execute
    assert len(_pending_members(r)) == 6
    assert list(tmp_path.iterdir()) == []


def test_t6_execute_batches_and_backs_up_before_zrem(tmp_path):
    from scripts import drain_nightwatcher_backlog as drain
    now = 1_000_000.0
    items = [(f"stale-{i}", now - (10 + i) * 86400) for i in range(5)] + [("active", now - 86400)]
    r = _drain_redis(items)
    backup = tmp_path / "backup.jsonl"
    order: list[int] = []
    real_pipeline = r.pipeline

    def pipeline(*a, **kw):
        pipe = real_pipeline(*a, **kw)
        real_exec = pipe.execute

        def execute(*ea, **ek):
            order.append(len(backup.read_text().splitlines()))   # backup lines present at ZREM time
            return real_exec(*ea, **ek)
        pipe.execute = execute
        return pipe
    r.pipeline = pipeline

    with patch("time.time", return_value=now), patch.object(drain, "get_redis_client", return_value=r), \
            patch.object(drain.time, "sleep") as sleep:
        assert drain.main(["--execute", "--age-off-days", "7", "--batch-size", "2",
                           "--delay-seconds", "3", "--backup-file", str(backup)]) == 0

    assert _pending_members(r) == {"active"}
    assert order == [2, 4, 5]                                     # each ZREM preceded by its backup lines
    assert sleep.call_count == 2                                  # between full windows only


# ==============================================================================
# S: _sweep behaviour
# ==============================================================================

def test_s_shift_report_accepts_quota_exhausted_status():
    """H1: no ValidationError, and it round-trips through JSON (as persist/get does)."""
    report = ShiftReport(shift_date="2026-01-01", window="morning", window_start="a", window_end="b",
                         status="quota_exhausted")
    assert ShiftReport.model_validate_json(report.model_dump_json()).status == "quota_exhausted"
    with pytest.raises(Exception):
        ShiftReport(shift_date="2026-01-01", window="morning", window_start="a", window_end="b", status="bogus")


def test_s_ui_types_and_colors_know_quota_exhausted():
    import pathlib
    root = pathlib.Path(__file__).resolve().parent.parent / "ui" / "src"
    types_ts = (root / "api" / "types.ts").read_text()
    assert types_ts.count("'quota_exhausted'") >= 2   # ShiftReportSummary + ShiftReportFull
    assert "quota_exhausted:" in (root / "constants" / "colors.ts").read_text()


def _sweep_obs(escs, *, raise_in_cart=None, raise_in_analysis=None, created=None):
    """Observer whose analysis/cart stages are stubbed so _sweep's failure handling is isolated."""
    obs = make_observer()
    raw = [e.model_dump_json() for e in escs]
    bb = obs.blackboard
    bb.lease_pending_escalations = AsyncMock(return_value=(escs, raw))
    for name in ("commit_inflight", "restage_orphans", "requeue_inflight",
                 "persist_shift_report", "clear_escalation_flag", "count_pending_escalations"):
        setattr(bb, name, AsyncMock())
    obs._get_adapter = AsyncMock(return_value=AsyncMock())

    async def fake_analysis(*a, **kw):
        if raise_in_analysis:
            raise raise_in_analysis
        ctx = make_ctx(escs, created=created)
        obs._batch_ctx = ctx
        return [], ctx

    async def fake_cart(*a, **kw):
        raise raise_in_cart
    obs._run_analysis_loop = fake_analysis
    obs._run_report_cart = fake_cart
    return obs, raw


@pytest.mark.asyncio
async def test_s_quota_exhausted_before_any_incident_restages_everything_and_persists_report():
    escs = [make_escalation(f"evt-{i}") for i in range(3)]
    obs, raw = _sweep_obs(escs, raise_in_analysis=QuotaExhaustedError("Quota exhausted"))
    with patch("src.observers.nightwatcher.asyncio.sleep", new=AsyncMock()) as sleep:
        await obs._sweep()                         # must not raise (H1)

    bb = obs.blackboard
    bb.restage_orphans.assert_awaited_once_with(raw)
    bb.commit_inflight.assert_not_called()
    bb.requeue_inflight.assert_not_called()
    sleep.assert_not_called()                      # no pointless 60s sleep inside a cron-driven sweep
    bb.persist_shift_report.assert_awaited_once()
    report = bb.persist_shift_report.call_args[0][0]
    assert isinstance(report, ShiftReport) and report.status == "quota_exhausted"
    assert report.incidents == []


@pytest.mark.asyncio
async def test_s_quota_exhausted_mid_cart_commits_incidented_events_and_restages_only_rest():
    """H2: events whose Jira incident exists are committed, never restaged."""
    escs = [make_escalation(f"evt-{i}") for i in (1, 2, 3, 4)]
    obs, raw = _sweep_obs(escs, raise_in_cart=QuotaExhaustedError("summary call"),
                          created=[incident("evt-1", "evt-2", key="VMER-7")])
    await obs._sweep()

    bb = obs.blackboard
    bb.commit_inflight.assert_awaited_once_with([raw[0], raw[1]])
    bb.restage_orphans.assert_awaited_once_with([raw[2], raw[3]])
    assert not set(bb.restage_orphans.call_args[0][0]) & set(bb.commit_inflight.call_args[0][0])
    cleared = {c.kwargs["expected_event_id"] for c in bb.clear_escalation_flag.call_args_list}
    assert cleared == {"evt-1", "evt-2"}
    report = bb.persist_shift_report.call_args[0][0]
    assert report.status == "quota_exhausted"
    assert [i.jira_issue_key for i in report.incidents] == ["VMER-7"]
    assert [e.event_id for e in report.manifest] == ["evt-1", "evt-2"]


@pytest.mark.asyncio
async def test_s_all_events_incidented_then_quota_error_restages_nothing():
    escs = [make_escalation("evt-1"), make_escalation("evt-2")]
    obs, raw = _sweep_obs(escs, raise_in_cart=QuotaExhaustedError("x"),
                          created=[incident("evt-1", "evt-2")])
    await obs._sweep()
    obs.blackboard.commit_inflight.assert_awaited_once_with(raw)
    obs.blackboard.restage_orphans.assert_not_called()


@pytest.mark.asyncio
async def test_s_generic_failure_with_partial_incidents_commits_and_restages_remainder():
    escs = [make_escalation(f"evt-{i}") for i in (1, 2, 3)]
    obs, raw = _sweep_obs(escs, raise_in_cart=RuntimeError("boom"), created=[incident("evt-2")])
    await obs._sweep()
    bb = obs.blackboard
    bb.commit_inflight.assert_awaited_once_with([raw[1]])
    bb.restage_orphans.assert_awaited_once_with([raw[0], raw[2]])
    bb.requeue_inflight.assert_not_called()
    assert bb.persist_shift_report.call_args[0][0].status == "failed"


@pytest.mark.asyncio
async def test_s_generic_failure_without_incidents_requeues_inflight():
    escs = [make_escalation("evt-1")]
    obs, raw = _sweep_obs(escs, raise_in_analysis=RuntimeError("boom"))
    await obs._sweep()
    bb = obs.blackboard
    bb.requeue_inflight.assert_awaited_once()
    bb.commit_inflight.assert_not_called()
    assert bb.persist_shift_report.call_args[0][0].status == "failed"


@pytest.mark.asyncio
async def test_s_failure_in_settle_still_persists_report():
    escs = [make_escalation("evt-1")]
    obs, raw = _sweep_obs(escs, raise_in_analysis=QuotaExhaustedError("x"))
    obs.blackboard.restage_orphans = AsyncMock(side_effect=ConnectionError("redis down"))
    await obs._sweep()
    assert obs.blackboard.persist_shift_report.call_args[0][0].status == "quota_exhausted"


# ---- batch loop (H3) --------------------------------------------------------

def _scripted_batches(n_batches):
    """LLM responses for n full batches (1 event each): analysis x2, declare, write_incident, summary."""
    out = []
    for i in range(1, n_batches + 1):
        out += [
            fc("set_phase", {"phase": "investigate"}), fc("set_phase", {"phase": "report"}),
            fc("declare_clusters", {"clusters": [{"events": [f"evt-b{i}"], "root_cause": f"rc{i}",
                                                  "platform": "Konflux", "services": ["svc"]}]}),
            fc("write_incident", {"summary": f"incident {i}", "description": "d", "priority": "Normal", "status": "New"}),
            fc("post_shift_summary", {"summary": f"batch {i} done"}),
        ]
    return out


def _batch_obs(n_leases, pending_after, *, adapter_responses=None):
    obs = make_observer()
    batches = []
    for i in range(1, n_leases + 1):
        e = make_escalation(f"evt-b{i}", service="svc", platform="Konflux")
        batches.append(([e], [e.model_dump_json()]))
    bb = obs.blackboard
    bb.lease_pending_escalations = AsyncMock(side_effect=batches + [([], [])])
    bb.count_pending_escalations = AsyncMock(side_effect=pending_after)
    for name in ("commit_inflight", "restage_orphans", "requeue_inflight", "persist_shift_report",
                 "clear_escalation_flag"):
        setattr(bb, name, AsyncMock())
    adapter = AsyncMock()
    adapter.generate = AsyncMock(side_effect=adapter_responses or _scripted_batches(n_leases))
    obs._get_adapter = AsyncMock(return_value=adapter)
    obs._incident_adapter.create_incident = AsyncMock(
        side_effect=[{"issue_key": f"VMER-{i}", "issue_url": f"u{i}"} for i in range(1, 20)])
    obs._incident_adapter.search_open_incidents = AsyncMock(return_value=[])
    return obs


@pytest.fixture
def fast_batches(monkeypatch):
    monkeypatch.setenv("NIGHTWATCHER_BATCH_SIZE", "1")
    monkeypatch.setenv("NIGHTWATCHER_MIN_PENDING", "1")
    monkeypatch.setenv("NIGHTWATCHER_BATCH_COOLDOWN_SECONDS", "0")
    monkeypatch.setenv("NIGHTWATCHER_MAX_BATCHES", "5")


@pytest.mark.asyncio
async def test_s_sweep_drains_multiple_batches_into_one_cumulative_report(fast_batches):
    obs = _batch_obs(3, pending_after=[2, 1, 0])
    await obs._sweep()

    bb = obs.blackboard
    assert bb.lease_pending_escalations.await_count == 3
    assert all(c.kwargs["limit"] == 1 for c in bb.lease_pending_escalations.call_args_list)
    assert bb.commit_inflight.await_count == 3
    assert bb.persist_shift_report.await_count == 3         # same date:window key, overwritten cumulatively
    final = bb.persist_shift_report.call_args[0][0]
    assert final.status == "completed"
    assert [i.jira_issue_key for i in final.incidents] == ["VMER-1", "VMER-2", "VMER-3"]
    assert [e.event_id for e in final.manifest] == ["evt-b1", "evt-b2", "evt-b3"]
    assert final.metrics["escalation_count"] == 3 and final.metrics["incident_count"] == 3
    assert "batch 1 done" in final.summary_text and "batch 3 done" in final.summary_text
    first = bb.persist_shift_report.call_args_list[0][0][0]
    assert len(first.incidents) == 1                         # progress visible after each batch


@pytest.mark.asyncio
async def test_s_sweep_stops_at_max_batches(fast_batches, monkeypatch):
    monkeypatch.setenv("NIGHTWATCHER_MAX_BATCHES", "2")
    obs = _batch_obs(3, pending_after=[99, 99, 99])
    await obs._sweep()
    assert obs.blackboard.lease_pending_escalations.await_count == 2   # cap, even with backlog left
    assert len(obs.blackboard.persist_shift_report.call_args[0][0].incidents) == 2


@pytest.mark.asyncio
async def test_s_sweep_stops_when_remaining_below_min_pending(fast_batches, monkeypatch):
    monkeypatch.setenv("NIGHTWATCHER_MIN_PENDING", "1")
    obs = _batch_obs(3, pending_after=[0])
    await obs._sweep()
    assert obs.blackboard.lease_pending_escalations.await_count == 1


@pytest.mark.asyncio
async def test_s_sweep_cools_down_between_batches_only(fast_batches, monkeypatch):
    monkeypatch.setenv("NIGHTWATCHER_BATCH_COOLDOWN_SECONDS", "12")
    obs = _batch_obs(2, pending_after=[1, 0])
    with patch("src.observers.nightwatcher.asyncio.sleep", new=AsyncMock()) as sleep:
        await obs._sweep()
    assert [c.args[0] for c in sleep.call_args_list] == [12.0]       # once, between batch 1 and 2


@pytest.mark.asyncio
async def test_s_quota_exhausted_on_second_batch_keeps_first_batch_results(fast_batches):
    responses = _scripted_batches(1) + [fc("set_phase", {"phase": "investigate"}),
                                        QuotaExhaustedError("Quota exhausted: 1/1")]
    obs = _batch_obs(2, pending_after=[1], adapter_responses=None)
    adapter = AsyncMock()

    async def gen(**kw):
        r = responses.pop(0)
        if isinstance(r, Exception):
            raise r
        return r
    adapter.generate = AsyncMock(side_effect=gen)
    obs._get_adapter = AsyncMock(return_value=adapter)

    await obs._sweep()

    bb = obs.blackboard
    final = bb.persist_shift_report.call_args[0][0]
    assert final.status == "quota_exhausted"
    assert [i.jira_issue_key for i in final.incidents] == ["VMER-1"]  # batch 1 survives in the report
    bb.commit_inflight.assert_awaited_once()                          # batch 1 committed, batch 2 not
    bb.restage_orphans.assert_awaited_once()                          # batch 2 restaged
    assert bb.lease_pending_escalations.await_count == 2              # and the drain stopped


@pytest.mark.asyncio
async def test_s_batch_without_incidents_stops_drain(fast_batches):
    """Poison-batch guard: do not re-lease the same oldest items within a sweep."""
    obs = _batch_obs(2, pending_after=[5, 5], adapter_responses=[
        fc("set_phase", {"phase": "investigate"}), fc("set_phase", {"phase": "report"}),
        fc("declare_clusters", {"clusters": [{"events": ["evt-b1"], "root_cause": "r",
                                              "platform": "Konflux", "services": []}]}),
    ] + [MockResponse(text="no tool")] * 3 + [fc("post_shift_summary", {"summary": "s"})])
    await obs._sweep()
    assert obs.blackboard.lease_pending_escalations.await_count == 1
    obs.blackboard.restage_orphans.assert_awaited()                  # failed cluster restaged


def test_s_merge_reports_recomputes_noise_and_handles_none():
    base = dict(shift_date="d", window="morning", window_start="a", window_end="b")
    a = ShiftReport(**base, status="completed", manifest=[make_escalation("e1"), make_escalation("e2")],
                    incidents=[incident("e1", "e2")], summary_text="one", started_at=100.0,
                    metrics={"escalation_count": 2, "incident_count": 1})
    b = ShiftReport(**base, status="completed", manifest=[make_escalation("e3")],
                    incidents=[incident("e3", key="VMER-2")], summary_text="two", started_at=200.0,
                    completed_at=300.0, metrics={"escalation_count": 1, "incident_count": 1})
    assert NightwatcherObserver._merge_reports(None, b) is b
    m = NightwatcherObserver._merge_reports(a, b)
    assert m.metrics["escalation_count"] == 3 and m.metrics["incident_count"] == 2
    assert m.metrics["noise_reduction_pct"] == 33.3
    assert m.started_at == 100.0 and m.completed_at == 300.0
    assert m.summary_text == "one\n\ntwo"
    assert NightwatcherObserver._merge_reports(a, b, status="failed").status == "failed"


def test_s_ports_signature_matches_implementation():
    """M8: the EscalationRepository port must expose the `limit` parameter."""
    import inspect
    from src.state.ports import EscalationRepository
    port = inspect.signature(EscalationRepository.lease_pending_escalations).parameters
    impl = inspect.signature(BlackboardState.lease_pending_escalations).parameters
    assert list(port) == list(impl) == ["self", "before_ts", "limit"]
    assert port["limit"].default == impl["limit"].default == 25


# ==============================================================================
# E2E: REAL Redis (fakeredis) + scripted LLM/Jira, integrated from QE's probe suite
# (/data/workspace/results/pr305-qe/test_nightwatcher_sweep_e2e_qe.py)
# ==============================================================================

PENDING = BlackboardState.NIGHTWATCHER_PENDING
INFLIGHT = BlackboardState.NIGHTWATCHER_INFLIGHT


def e2e_esc(i):
    return StagedEscalation(event_id=f"evt-{i:03d}", service=f"svc-{i}", source="aligner", reason="ci",
                            summary="s", platform="Konflux", description="d", staged_at=1000.0 + i,
                            priority="Normal")


@pytest.fixture
def e2e_env(monkeypatch):
    monkeypatch.setenv("NIGHTWATCHER_BATCH_SIZE", "2")
    monkeypatch.setenv("NIGHTWATCHER_MIN_PENDING", "1")
    monkeypatch.setenv("NIGHTWATCHER_MAX_BATCHES", "10")
    monkeypatch.setenv("NIGHTWATCHER_BATCH_COOLDOWN_SECONDS", "0")


@pytest.fixture
async def board(e2e_env):
    r = fakeredis.aioredis.FakeRedis()
    b = BlackboardState.__new__(BlackboardState)  # skip __init__ (Lua registration)
    b.redis = r
    b.clear_escalation_flag = AsyncMock()
    yield b
    await r.aclose()


class ScriptedLLM:
    """Dispatches on the call shape so it works for any batch composition.

    one_cluster_per_event: declare one cluster per leased event (else one cluster for the batch).
    hooks: callables run at specific (batch_no, stage) points; may raise.
    """

    def __init__(self, one_cluster_per_event=False, boom=None, skip_write_for=()):
        self.batch = 0
        self.stage = "analysis"
        self.events: list[str] = []
        self.clusters: list[list[str]] = []
        self.cluster_idx = 0
        self.one = one_cluster_per_event
        self.boom = boom or {}            # {(batch_no, stage[, cluster_idx]): Exception}
        self.skip_write_for = set(skip_write_for)
        self.analysis_calls = 0

    async def generate(self, **kw):
        tools = kw.get("tools")
        names = [t.get("name") for t in (tools if isinstance(tools, list) else [])] if tools else []
        flat = str(tools)
        contents = kw["contents"]
        text0 = contents[0]["parts"][0]["text"]
        if "post_shift_summary" in flat:
            self._maybe_boom("summary")
            return fc("post_shift_summary", {"summary": f"batch {self.batch} done"})
        if "declare_clusters" in flat and "write_incident" not in flat:
            self._maybe_boom("declare")
            evs = self.events
            self.clusters = [[e] for e in evs] if self.one else [evs]
            self.cluster_idx = 0
            return fc("declare_clusters", {"clusters": [
                {"events": c, "root_cause": f"rc-{c[0]}", "platform": "Konflux", "services": ["svc"]}
                for c in self.clusters]})
        if "write_incident" in flat:
            cl = self.clusters[self.cluster_idx]
            self._maybe_boom("write", self.cluster_idx)
            self.cluster_idx += 1
            if cl[0] in self.skip_write_for:
                return MockResponse(text="no tool call")
            return fc("write_incident", {"summary": f"inc {cl[0]}", "description": "d",
                                          "priority": "Normal", "status": "New"})
        # analysis phase (set_phase) -- first call of a new batch carries the manifest as contents[0]
        found = re.findall(r"\*\*(evt-\d+)\*\*", text0)
        if len(contents) == 1:
            self.batch += 1
            self.stage = "analysis"
            self.events = found
            self.analysis_calls = 0
        self._maybe_boom("analysis")
        self.analysis_calls += 1
        phase = "investigate" if self.analysis_calls == 1 else "report"
        return fc("set_phase", {"phase": phase})

    def _maybe_boom(self, stage, idx=None):
        for key in ((self.batch, stage, idx), (self.batch, stage)):
            if key in self.boom:
                raise self.boom.pop(key)


def e2e_observer(board, llm, jira=None):
    obs = NightwatcherObserver(
        blackboard=board, registry=AsyncMock(), bridge=AsyncMock(), provisioner=AsyncMock(),
        incident_adapter=AsyncMock(), archivist=AsyncMock(), slack_notify=AsyncMock(),
    )
    adapter = AsyncMock()
    adapter.generate = llm.generate
    obs._get_adapter = AsyncMock(return_value=adapter)
    n = iter(range(1, 100))
    obs._incident_adapter.create_incident = jira or AsyncMock(
        side_effect=lambda f: {"issue_key": f"VMER-{next(n)}", "issue_url": "u"})
    obs._incident_adapter.search_open_incidents = AsyncMock(return_value=[])
    return obs


async def e2e_stage(board, n):
    for i in range(1, n + 1):
        await board.stage_escalation(e2e_esc(i))


async def e2e_snapshot(board):
    pend = {StagedEscalation.model_validate_json(m).event_id for m in await board.redis.zrange(PENDING, 0, -1)}
    infl = {StagedEscalation.model_validate_json(m).event_id for m in await board.redis.smembers(INFLIGHT)}
    return pend, infl


async def e2e_latest_report(board):
    keys = [k async for k in board.redis.scan_iter(match=f"{BlackboardState.SHIFT_PREFIX}*")]
    assert len(keys) == 1, keys                      # one cumulative report key per sweep (date:window)
    from src.models import ShiftReport
    return ShiftReport.model_validate_json(await board.redis.get(keys[0]))


@pytest.mark.asyncio
async def test_e2e_multi_batch_drain_empties_backlog_into_one_cumulative_report(board):
    await e2e_stage(board, 5)
    obs = e2e_observer(board, ScriptedLLM())
    await obs._sweep()
    pend, infl = await e2e_snapshot(board)
    assert pend == set() and infl == set()
    rep = await e2e_latest_report(board)
    assert rep.status == "completed"
    assert len(rep.incidents) == 3                                  # batches of 2,2,1
    assert sorted(e.event_id for e in rep.manifest) == [f"evt-{i:03d}" for i in range(1, 6)]
    assert rep.metrics["escalation_count"] == 5 and rep.metrics["incident_count"] == 3


@pytest.mark.asyncio
async def test_e2e_quota_exhausted_on_batch2_keeps_batch1_committed_and_restages_batch2(board):
    await e2e_stage(board, 5)
    llm = ScriptedLLM(boom={(2, "analysis"): QuotaExhaustedError("Quota exhausted")})
    obs = e2e_observer(board, llm)
    await obs._sweep()                                               # must not raise
    pend, infl = await e2e_snapshot(board)
    assert infl == set()                                             # no zombie inflight
    assert pend == {"evt-003", "evt-004", "evt-005"}                 # batch 2 restaged + batch 3 never leased
    assert not pend & {"evt-001", "evt-002"}                         # batch 1 never restaged -> no dup Jira
    rep = await e2e_latest_report(board)
    assert rep.status == "quota_exhausted"
    assert [i.jira_issue_key for i in rep.incidents] == ["VMER-1"]
    assert sorted(e.event_id for e in rep.manifest) == ["evt-001", "evt-002"]
    assert obs._incident_adapter.create_incident.await_count == 1


@pytest.mark.asyncio
async def test_e2e_quota_exhausted_mid_cart_commits_incidented_cluster_only(board):
    """Batch 1: 2 clusters; 1st incident created, QuotaExhausted on the 2nd cluster's LLM call."""
    await e2e_stage(board, 2)
    llm = ScriptedLLM(one_cluster_per_event=True,
                      boom={(1, "write", 1): QuotaExhaustedError("Quota exhausted")})
    obs = e2e_observer(board, llm)
    await obs._sweep()
    pend, infl = await e2e_snapshot(board)
    assert pend == {"evt-002"} and infl == set()
    rep = await e2e_latest_report(board)
    assert rep.status == "quota_exhausted"
    assert [e.event_id for e in rep.manifest] == ["evt-001"]


@pytest.mark.asyncio
async def test_e2e_no_duplicate_incidents_across_sweeps_after_quota_failure(board):
    """Sweep 1 dies mid-batch-2; sweep 2 (healthy) finishes. Every event must get exactly one incident."""
    await e2e_stage(board, 5)
    obs1 = e2e_observer(board, ScriptedLLM(boom={(2, "analysis"): QuotaExhaustedError("q")}))
    await obs1._sweep()
    obs2 = e2e_observer(board, ScriptedLLM())
    await obs2._sweep()
    pend, infl = await e2e_snapshot(board)
    assert pend == set() and infl == set()
    covered = []
    for obs in (obs1, obs2):
        for call in obs._incident_adapter.create_incident.await_args_list:
            covered.append(call.args[0]["summary"])
    ev_in_summaries = [re.search(r"evt-\d+", s).group(0) for s in covered]
    assert len(ev_in_summaries) == len(set(ev_in_summaries))        # no event had 2 incidents
    assert len(covered) == 1 + 2                                     # b1 (evt1,2) + {3,4},{5} in sweep 2


@pytest.mark.asyncio
async def test_e2e_generic_failure_after_partial_incident_does_not_duplicate(board):
    await e2e_stage(board, 2)
    llm = ScriptedLLM(one_cluster_per_event=True, boom={(1, "write", 1): RuntimeError("boom")})
    obs = e2e_observer(board, llm)
    await obs._sweep()
    pend, infl = await e2e_snapshot(board)
    assert pend == {"evt-002"} and infl == set()
    assert (await e2e_latest_report(board)).status == "failed"


@pytest.mark.asyncio
async def test_e2e_failure_before_any_incident_requeues_all(board):
    await e2e_stage(board, 3)
    obs = e2e_observer(board, ScriptedLLM(boom={(1, "declare"): RuntimeError("boom")}))
    await obs._sweep()
    pend, infl = await e2e_snapshot(board)
    assert pend == {"evt-001", "evt-002", "evt-003"} and infl == set()


@pytest.mark.asyncio
async def test_e2e_max_batches_leaves_remainder_pending(board, monkeypatch):
    monkeypatch.setenv("NIGHTWATCHER_MAX_BATCHES", "2")
    await e2e_stage(board, 7)
    obs = e2e_observer(board, ScriptedLLM())
    await obs._sweep()
    pend, infl = await e2e_snapshot(board)
    assert pend == {"evt-005", "evt-006", "evt-007"} and infl == set()
    assert (await e2e_latest_report(board)).status == "completed"


@pytest.mark.asyncio
async def test_e2e_failed_cluster_is_restaged_and_not_leased_again_in_same_sweep(board):
    """A refused cluster is restaged (original staged_at, so FIFO puts it at the front of the next lease).
    Known trade-off: it can be re-leased by a later batch of the same sweep (bounded by MAX_BATCHES).
    Invariants asserted: terminates, nothing lost, nothing duplicated, no zombie inflight."""
    await e2e_stage(board, 4)
    llm = ScriptedLLM(one_cluster_per_event=True, skip_write_for={"evt-001"})
    obs = e2e_observer(board, llm)
    with patch("src.observers.nightwatcher.MAX_CART_RETRIES", 0):
        await obs._sweep()
    seen = [c.args[0]["summary"] for c in obs._incident_adapter.create_incident.await_args_list]
    # evt-001 never gets an incident (LLM refuses) -- assert the sweep terminates and nothing is lost/duplicated.
    assert len(seen) == len(set(seen))
    pend, infl = await e2e_snapshot(board)
    assert infl == set()
    assert "evt-001" in pend                                         # still pending for next sweep, not lost


@pytest.mark.asyncio
async def test_e2e_no_cooldown_sleep_after_final_allowed_batch(board, monkeypatch):
    """Kills the `batch_no >= max_batches` -> `>` mutant: no wasted cooldown/count after the last batch."""
    monkeypatch.setenv("NIGHTWATCHER_MAX_BATCHES", "2")
    monkeypatch.setenv("NIGHTWATCHER_BATCH_COOLDOWN_SECONDS", "12")
    await e2e_stage(board, 7)
    obs = e2e_observer(board, ScriptedLLM())
    with patch("src.observers.nightwatcher.asyncio.sleep", new=AsyncMock()) as sleep:
        await obs._sweep()
    assert [c.args[0] for c in sleep.call_args_list] == [12.0]       # between batch 1 and 2 only


# ---- Round-2 regressions (ai-review HIGH findings on fbdd08f5) ----

@pytest.mark.asyncio
async def test_probe_high1_incidented_events_survive_hard_stop_before_commit(board):
    """HIGH #1 (crash window). Pod SIGTERM => CancelledError (BaseException, not caught by `except Exception`)
    after the Jira incident is written but before the end-of-sweep commit. Per-cluster commit means the
    incidented events are already out of inflight, so requeue_inflight() on restart cannot re-file them."""
    import asyncio
    await _stage_board(board, 2)
    llm = ScriptedLLM(boom={(1, "summary"): asyncio.CancelledError()})
    obs = e2e_observer(board, llm)
    with pytest.raises(asyncio.CancelledError):
        await obs._sweep()
    assert obs._incident_adapter.create_incident.await_count == 1    # Jira incident exists for evt-001+002
    assert await board.requeue_inflight() == 0, "incidented events were still inflight -> would be re-filed after restart"
    pend, infl = await e2e_snapshot(board)
    assert pend == set() and infl == set()


@pytest.mark.asyncio
async def test_round2_cancel_mid_cart_commits_finished_clusters_only(board):
    """CancelledError while cluster 2 is being written: cluster 1 is committed (never requeued),
    cluster 2 (no incident yet) stays inflight and is safely recovered by requeue_inflight()."""
    import asyncio
    await _stage_board(board, 2)
    llm = ScriptedLLM(one_cluster_per_event=True, boom={(1, "write", 1): asyncio.CancelledError()})
    obs = e2e_observer(board, llm)
    with pytest.raises(asyncio.CancelledError):
        await obs._sweep()
    pend, infl = await e2e_snapshot(board)
    assert infl == {"evt-002"} and pend == set()
    assert await board.requeue_inflight() == 1
    pend, infl = await e2e_snapshot(board)
    assert pend == {"evt-002"} and infl == set()                     # evt-001 (incidented) is never requeued
    assert obs._incident_adapter.create_incident.await_count == 1


@pytest.mark.asyncio
async def test_round2_commit_happens_per_cluster_before_next_cluster_is_written(board):
    """Directly pins the ordering: when cluster 2's incident is created, cluster 1 is already out of inflight."""
    await _stage_board(board, 2)
    inflight_seen: list[set[str]] = []

    async def create(fields):
        _, infl = await e2e_snapshot(board)
        inflight_seen.append(infl)
        return {"issue_key": f"VMER-{len(inflight_seen)}", "issue_url": "u"}
    obs = e2e_observer(board, ScriptedLLM(one_cluster_per_event=True), jira=AsyncMock(side_effect=create))
    await obs._sweep()
    assert inflight_seen == [{"evt-001", "evt-002"}, {"evt-002"}]    # cluster 1 committed before cluster 2 write
    assert (await e2e_snapshot(board)) == (set(), set())


@pytest.mark.asyncio
async def test_probe_high2_settle_double_fault_strands_inflight(board):
    """HIGH #2: restage itself raises inside _settle_failed_batch -> fall back to requeue_inflight()
    so nothing is stranded in inflight (where the 1h TTL would DELETE it)."""
    await _stage_board(board, 2)
    obs = e2e_observer(board, ScriptedLLM(boom={(1, "analysis"): QuotaExhaustedError("q")}))
    real = board.restage_orphans
    board.restage_orphans = AsyncMock(side_effect=ConnectionError("redis blip"))
    await obs._sweep()
    board.restage_orphans = real
    pend, infl = await e2e_snapshot(board)
    assert infl == set(), f"stranded inflight (never auto-recovered in a running pod): {infl}"
    assert pend == {"evt-001", "evt-002"}
    assert (await e2e_latest_report(board)).status == "quota_exhausted"


@pytest.mark.asyncio
async def test_round2_commit_failure_does_not_block_restage(board):
    """HIGH #2: commit of incidented events fails, but the non-incidented remainder is still restaged."""
    await _stage_board(board, 2)
    llm = ScriptedLLM(one_cluster_per_event=True, boom={(1, "write", 1): QuotaExhaustedError("q")})
    obs = e2e_observer(board, llm)
    real_commit = board.commit_inflight
    board.commit_inflight = AsyncMock(side_effect=ConnectionError("redis blip"))
    await obs._sweep()                                               # must not raise
    board.commit_inflight = real_commit
    pend, infl = await e2e_snapshot(board)
    assert "evt-002" in pend                                         # restage ran despite the commit fault
    assert "evt-001" not in pend                                     # incidented event must NOT be re-queued
    # the per-cluster commit fault aborts the cart as a generic failure (safe: remainder restaged)
    assert (await e2e_latest_report(board)).status == "failed"


@pytest.mark.asyncio
async def test_round2_double_fault_with_failed_commit_never_requeues_everything():
    """If commit failed AND restage failed, requeue_inflight() would re-file existing incidents -> must not run."""
    escs = [make_escalation("evt-1"), make_escalation("evt-2")]
    obs, raw = _sweep_obs(escs, raise_in_cart=QuotaExhaustedError("x"), created=[incident("evt-1")])
    obs.blackboard.commit_inflight = AsyncMock(side_effect=ConnectionError("blip"))
    obs.blackboard.restage_orphans = AsyncMock(side_effect=ConnectionError("blip"))
    await obs._sweep()
    obs.blackboard.requeue_inflight.assert_not_called()
    assert obs.blackboard.persist_shift_report.call_args[0][0].status == "quota_exhausted"


@pytest.mark.asyncio
async def test_round2_double_fault_requeue_fallback_failure_is_survivable():
    escs = [make_escalation("evt-1")]
    obs, raw = _sweep_obs(escs, raise_in_analysis=QuotaExhaustedError("x"))
    obs.blackboard.restage_orphans = AsyncMock(side_effect=ConnectionError("blip"))
    obs.blackboard.requeue_inflight = AsyncMock(side_effect=ConnectionError("blip"))
    await obs._sweep()                                               # no exception escapes
    obs.blackboard.requeue_inflight.assert_awaited_once()
    assert obs.blackboard.persist_shift_report.call_args[0][0].status == "quota_exhausted"


@pytest.mark.asyncio
async def test_round2_commit_processed_is_incremental_and_idempotent():
    escs = [make_escalation("evt-1"), make_escalation("evt-2")]
    raw = [e.model_dump_json() for e in escs]
    obs = make_observer()
    obs.blackboard.commit_inflight = AsyncMock()
    obs.blackboard.clear_escalation_flag = AsyncMock()
    ctx = make_ctx(escs, created=[incident("evt-1")])
    assert await obs._commit_processed(ctx, raw, escs) == {"evt-1"}
    ctx.created_incidents.append(incident("evt-2", key="VMER-2"))
    assert await obs._commit_processed(ctx, raw, escs) == {"evt-1", "evt-2"}
    assert await obs._commit_processed(ctx, raw, escs) == {"evt-1", "evt-2"}   # no-op
    assert [c.args[0] for c in obs.blackboard.commit_inflight.call_args_list] == [[raw[0]], [raw[1]]]
    assert obs.blackboard.clear_escalation_flag.await_count == 2
    # a failed commit is NOT marked committed, so it is retried
    ctx2 = make_ctx(escs, created=[incident("evt-1")])
    obs.blackboard.commit_inflight = AsyncMock(side_effect=[ConnectionError("x"), None])
    with pytest.raises(ConnectionError):
        await obs._commit_processed(ctx2, raw, escs)
    assert ctx2.committed_event_ids == set()
    await obs._commit_processed(ctx2, raw, escs)
    assert obs.blackboard.commit_inflight.await_count == 2


@pytest.mark.asyncio
@pytest.mark.parametrize("enabled", ["false", "true"])
async def test_probe_high3_report_incident_null_summary_both_branches(enabled):
    """HIGH #3: explicit `summary: null` must not raise on the direct-Jira (false) or staging (true) branch,
    including the set_escalation_flag summary (lines 483/532)."""
    from unittest.mock import MagicMock
    from src.agents import handlers_dispatch
    from src.models import EventDocument, EventEvidence, EventInput
    bb = AsyncMock(spec=BlackboardState)
    bb.get_active_events.return_value = []
    bb.get_event.return_value = EventDocument(
        id="evt-x", source="aligner", service="svc-a", subject_type="service",
        event=EventInput(reason="cpu", evidence=EventEvidence(display_text="cpu", source_type="aligner")))
    ctx = MagicMock()
    ctx.get_blackboard.return_value = bb
    ctx.has_incident_been_created.return_value = False
    ctx.next_turn_number = AsyncMock(return_value=1)
    ctx.append_and_broadcast = AsyncMock()
    ctx.emit_pulse = AsyncMock()
    adapter = AsyncMock(create_incident=AsyncMock(return_value={"issue_key": "VMER-1", "issue_url": "u"}))
    ctx.get_incident_adapter.return_value = adapter
    with patch.dict("os.environ", {"NIGHTWATCHER_ENABLED": enabled}):
        res = await handlers_dispatch.handle_report_incident(
            ctx, "evt-x", {"summary": None, "description": "d", "priority": "Normal"}, None)
    assert res is True
    if enabled == "false":
        assert adapter.create_incident.call_args[0][0]["summary"] == ""
    bb.set_escalation_flag.assert_awaited_once()
    assert bb.set_escalation_flag.call_args[0][2] == "escalated"     # null summary -> default text, not a crash


async def _stage_board(board, n):
    await e2e_stage(board, n)
